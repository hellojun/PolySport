"""
预测结果生成器
从辩论结果生成L1/L2/L3三层输出
所有市场固定主队视角，同时展示客队数据
"""

import traceback
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from ..utils.logger import get_logger
from ..utils.llm_client import LLMClient
from .debate_engine import DebateResult
from .analyst_agents import get_analyst_roles

logger = get_logger('mirofish.prediction_generator')


@dataclass
class BettingAdvice:
    """单个市场的投注建议（主队视角）"""
    market: str              # "moneyline", "spread", "total"
    pick: str                # 主队标签 e.g. "ORL", "ORL -2.5", "OVER"
    model_probability: float # 主队/OVER 模型概率
    market_probability: Optional[float] = None  # 主队/OVER 市场概率
    edge: Optional[float] = None                # model - market
    recommendation: str = "no_edge"             # value_bet / lean / no_edge / fade
    confidence: float = 0.5
    opponent_pick: str = ""                     # 客队标签 e.g. "PHX", "PHX +2.5", "UNDER"
    opponent_probability: Optional[float] = None  # 客队/UNDER 模型概率

    def to_dict(self) -> Dict[str, Any]:
        return {
            "market": self.market,
            "pick": self.pick,
            "model_probability": round(self.model_probability, 4),
            "market_probability": round(self.market_probability, 4) if self.market_probability is not None else None,
            "edge": round(self.edge, 4) if self.edge is not None else None,
            "recommendation": self.recommendation,
            "confidence": round(self.confidence, 4),
            "opponent_pick": self.opponent_pick,
            "opponent_probability": round(self.opponent_probability, 4) if self.opponent_probability is not None else None,
        }


@dataclass
class PredictionOutput:
    """预测输出"""
    matchup_id: str
    betting_card: List[BettingAdvice] = field(default_factory=list)   # L1
    key_factors: List[str] = field(default_factory=list)              # L2
    consensus: Optional[str] = None                                    # L2
    debate_log: Optional[Dict[str, Any]] = None                       # L3

    def to_dict(self, level: str = "L1") -> Dict[str, Any]:
        """按层级返回"""
        result = {
            "matchup_id": self.matchup_id,
            "betting_card": [b.to_dict() for b in self.betting_card],
        }
        if level in ("L2", "L3"):
            result["key_factors"] = self.key_factors
            result["consensus"] = self.consensus
        if level == "L3":
            result["debate_log"] = self.debate_log
        return result


def _classify_recommendation(edge: Optional[float]) -> str:
    """根据edge分类推荐级别"""
    if edge is None:
        return "no_edge"
    if edge >= 0.08:
        return "value_bet"
    if edge >= 0.03:
        return "lean"
    if edge <= -0.08:
        return "fade"
    return "no_edge"


class PredictionGenerator:
    """
    预测生成器
    从DebateResult聚合出L1/L2/L3预测输出
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or LLMClient()
        self._roles = {r.id: r for r in get_analyst_roles()}

    def generate(
        self,
        debate_result: DebateResult,
        market_odds: Optional[Dict[str, Any]] = None,
        home_abbr: str = "",
        away_abbr: str = "",
        lang: str = "en",
    ) -> PredictionOutput:
        """
        生成预测输出

        Args:
            debate_result: 辩论结果
            market_odds: 市场赔率（可选），用于计算edge
            home_abbr: 主队缩写
            away_abbr: 客队缩写

        Returns:
            PredictionOutput
        """
        output = PredictionOutput(matchup_id=debate_result.matchup_id)

        # 取 Round 3（最终轮）的预测
        final_round = None
        for r in debate_result.rounds:
            if r.round_num == len(debate_result.rounds):
                final_round = r
                break

        if not final_round or not final_round.predictions:
            logger.warning("No final round predictions available")
            return output

        predictions = final_round.predictions

        # ---- L1: Betting Card (固定主队视角) ----
        output.betting_card = self._aggregate_betting_card(
            predictions, market_odds, home_abbr, away_abbr
        )

        # ---- L2: Key Factors + Consensus ----
        output.key_factors = self._extract_key_factors(predictions, lang=lang)
        output.consensus = self._compute_consensus(predictions, lang=lang)

        # ---- L3: Full debate log ----
        output.debate_log = debate_result.to_dict()

        return output

    def _aggregate_betting_card(
        self,
        predictions: list,
        market_odds: Optional[Dict[str, Any]],
        home_abbr: str,
        away_abbr: str,
    ) -> List[BettingAdvice]:
        """固定主队视角聚合三个市场"""
        mo = market_odds or {}
        cards = []

        # --- Moneyline (主队视角) ---
        home_prob = self._compute_home_probability(
            predictions, "moneyline_pick", "moneyline_confidence", home_abbr
        )
        market_home = mo.get("moneyline_home")
        ml_edge = (home_prob - market_home) if market_home is not None else None
        cards.append(BettingAdvice(
            market="moneyline",
            pick=home_abbr,
            model_probability=home_prob,
            market_probability=market_home,
            edge=ml_edge,
            recommendation=_classify_recommendation(ml_edge),
            confidence=home_prob,
            opponent_pick=away_abbr,
            opponent_probability=1 - home_prob,
        ))

        # --- Spread (主队视角) ---
        spread_line = mo.get("spread_line")
        home_spread_prob = self._compute_home_probability(
            predictions, "spread_pick", "spread_confidence", home_abbr
        )
        market_spread = mo.get("spread_home")
        sp_edge = (home_spread_prob - market_spread) if market_spread is not None else None
        home_label = f"{home_abbr} {spread_line:+.1f}" if spread_line is not None else home_abbr
        away_label = f"{away_abbr} {-spread_line:+.1f}" if spread_line is not None else away_abbr
        cards.append(BettingAdvice(
            market="spread",
            pick=home_label,
            model_probability=home_spread_prob,
            market_probability=market_spread,
            edge=sp_edge,
            recommendation=_classify_recommendation(sp_edge),
            confidence=home_spread_prob,
            opponent_pick=away_label,
            opponent_probability=1 - home_spread_prob,
        ))

        # --- Total (OVER/UNDER 视角, 不需要主客区分) ---
        over_prob = self._compute_over_probability(predictions)
        market_over = mo.get("total_over")
        total_line = mo.get("total_line")
        tot_edge = (over_prob - market_over) if market_over is not None else None
        over_label = f"OVER {total_line}" if total_line is not None else "OVER"
        under_label = f"UNDER {total_line}" if total_line is not None else "UNDER"
        cards.append(BettingAdvice(
            market="total",
            pick=over_label,
            model_probability=over_prob,
            market_probability=market_over,
            edge=tot_edge,
            recommendation=_classify_recommendation(tot_edge),
            confidence=over_prob,
            opponent_pick=under_label,
            opponent_probability=1 - over_prob,
        ))

        return cards

    def _compute_home_probability(
        self, predictions: list, pick_key: str, conf_key: str, home_abbr: str,
    ) -> float:
        """
        从分析师投票计算主队概率（加权平均）。
        - 分析师选主队 + confidence c → P(home) += c * weight
        - 分析师选客队 + confidence c → P(home) += (1-c) * weight
        """
        weighted_sum = 0.0
        total_weight = 0.0

        for pred in predictions:
            pick = getattr(pred, pick_key, "")
            conf = getattr(pred, conf_key, 0.5)
            role = self._roles.get(pred.analyst_id)
            weight = role.weight if role else 1.0

            if not pick:
                continue

            if home_abbr.upper() in pick.upper():
                weighted_sum += conf * weight
            else:
                weighted_sum += (1 - conf) * weight
            total_weight += weight

        if total_weight == 0:
            return 0.5
        return max(0.01, min(0.99, weighted_sum / total_weight))

    def _compute_over_probability(self, predictions: list) -> float:
        """从分析师投票计算 OVER 概率"""
        weighted_sum = 0.0
        total_weight = 0.0

        for pred in predictions:
            pick = getattr(pred, "total_pick", "")
            conf = getattr(pred, "total_confidence", 0.5)
            role = self._roles.get(pred.analyst_id)
            weight = role.weight if role else 1.0

            if not pick:
                continue

            if "OVER" in pick.upper():
                weighted_sum += conf * weight
            else:
                weighted_sum += (1 - conf) * weight
            total_weight += weight

        if total_weight == 0:
            return 0.5
        return max(0.01, min(0.99, weighted_sum / total_weight))

    def _extract_key_factors(self, predictions: list, lang: str = "en") -> List[str]:
        """通过一次LLM调用从所有reasoning中提取3-5个关键因素"""
        all_reasoning = "\n".join(
            f"- [{p.analyst_id}]: {p.reasoning}" for p in predictions if p.reasoning
        )

        if not all_reasoning.strip():
            return []

        system_prompt = (
            "You are a sports analysis summarizer. "
            "Extract the 3-5 most important KEY FACTORS from the analysts' reasoning below. "
            "Return JSON: {\"key_factors\": [\"factor1\", \"factor2\", ...]}"
        )
        if lang == "zh":
            system_prompt += " Write the factors in Chinese (中文)."

        try:
            response = self.llm.chat_json(
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": f"Analysts' reasoning:\n{all_reasoning}",
                    },
                ],
                temperature=0.2,
                max_tokens=512,
            )
            factors = response.get("key_factors", [])
            return [str(f) for f in factors[:5]]
        except Exception as e:
            logger.warning(f"Key factors extraction failed: {e}")
            # 降级: 从每个分析师取第一个key_factor
            fallback = []
            for p in predictions:
                if p.key_factors:
                    fallback.append(p.key_factors[0])
                    if len(fallback) >= 4:
                        break
            return fallback

    def _compute_consensus(self, predictions: list, lang: str = "en") -> str:
        """计算共识度"""
        if not predictions:
            return "N/A"

        # 统计moneyline一致性
        ml_picks = [p.moneyline_pick for p in predictions if p.moneyline_pick]
        if not ml_picks:
            return "N/A"

        from collections import Counter
        counts = Counter(ml_picks)
        most_common_pick, most_common_count = counts.most_common(1)[0]
        ratio = most_common_count / len(ml_picks)

        if lang == "zh":
            if ratio >= 0.83:
                return f"强烈共识 ({most_common_count}/{len(ml_picks)}) 选择 {most_common_pick}"
            elif ratio >= 0.67:
                return f"温和共识 ({most_common_count}/{len(ml_picks)}) 选择 {most_common_pick}"
            else:
                return f"意见分歧 ({most_common_count}/{len(ml_picks)}) 倾向 {most_common_pick}"
        else:
            if ratio >= 0.83:
                return f"Strong consensus ({most_common_count}/{len(ml_picks)}) for {most_common_pick}"
            elif ratio >= 0.67:
                return f"Moderate consensus ({most_common_count}/{len(ml_picks)}) for {most_common_pick}"
            else:
                return f"Split opinion ({most_common_count}/{len(ml_picks)}) leaning {most_common_pick}"
