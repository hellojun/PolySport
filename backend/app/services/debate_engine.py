"""
辩论引擎
3轮 x 6分析师，同一轮内并行调用LLM
"""

import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable

from ..utils.logger import get_logger
from ..utils.llm_client import LLMClient
from ..config import Config
from .analyst_agents import (
    AnalystPrediction,
    AnalystRole,
    get_analyst_roles,
    build_analyst_prompt,
)

logger = get_logger('mirofish.debate_engine')


@dataclass
class DebateRound:
    """单轮辩论结果"""
    round_num: int
    predictions: List[AnalystPrediction] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "round_num": self.round_num,
            "predictions": [p.to_dict() for p in self.predictions],
        }


@dataclass
class DebateResult:
    """辩论总结果"""
    matchup_id: str
    rounds: List[DebateRound] = field(default_factory=list)
    total_llm_calls: int = 0
    total_duration_seconds: float = 0.0
    round_timings: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "matchup_id": self.matchup_id,
            "rounds": [r.to_dict() for r in self.rounds],
            "total_llm_calls": self.total_llm_calls,
            "total_duration_seconds": self.total_duration_seconds,
            "round_timings": self.round_timings,
        }


class DebateEngine:
    """
    辩论引擎
    编排 3 轮 x 6 分析师，同一轮内并行调用 LLM
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or LLMClient()
        self.roles = get_analyst_roles()
        self.num_rounds = Config.DEBATE_NUM_ROUNDS
        self.temperature = Config.DEBATE_LLM_TEMPERATURE
        self.max_tokens = Config.DEBATE_LLM_MAX_TOKENS

    def run_debate(
        self,
        matchup_text: str,
        matchup_id: str,
        graph_context: str = "",
        progress_callback: Optional[Callable[[str, float], None]] = None,
        lang: str = "en",
        smart_money_context: Optional[str] = None,
    ) -> DebateResult:
        """
        运行完整辩论流程（同一轮内并行调用）

        Args:
            matchup_text: 对阵数据自然语言文本
            matchup_id: 对阵ID
            graph_context: 图谱检索的上下文信息
            progress_callback: 进度回调 (message, percent 0-1)
            lang: 输出语言
            smart_money_context: 聪明钱持仓数据文本（仅传给聪明钱分析师）

        Returns:
            DebateResult
        """
        start_time = time.time()
        result = DebateResult(matchup_id=matchup_id)
        total_calls = self.num_rounds * len(self.roles)
        completed_calls = 0

        logger.info(f"开始辩论: matchup={matchup_id}, rounds={self.num_rounds}, analysts={len(self.roles)}")

        previous_round_predictions: Optional[List[Dict[str, Any]]] = None

        round_timings = []

        for round_num in range(1, self.num_rounds + 1):
            round_start = time.time()
            round_result = DebateRound(round_num=round_num)

            if progress_callback:
                analyst_count = len(self.roles)
                msg = (f"Round {round_num}/{self.num_rounds} - {analyst_count}位分析师并行分析中..."
                       if lang == "zh"
                       else f"Round {round_num}/{self.num_rounds} - {analyst_count} analysts running...")
                progress_callback(msg, completed_calls / total_calls)

            # 同一轮内的分析师并行调用
            futures = {}
            with ThreadPoolExecutor(max_workers=len(self.roles)) as executor:
                for role in self.roles:
                    extra = smart_money_context if role.id == "smart_money_analyst" else None
                    future = executor.submit(
                        self._call_analyst,
                        role=role,
                        matchup_text=matchup_text,
                        graph_context=graph_context,
                        round_num=round_num,
                        previous_predictions=previous_round_predictions,
                        lang=lang,
                        extra_context=extra,
                    )
                    futures[future] = role

                for future in as_completed(futures):
                    role = futures[future]
                    completed_calls += 1

                    try:
                        prediction = future.result()
                        round_result.predictions.append(prediction)
                        result.total_llm_calls += 1
                        logger.info(
                            f"Round {round_num} - {role.id}: "
                            f"ML={prediction.moneyline_pick}({prediction.moneyline_confidence:.0%})"
                        )
                    except Exception as e:
                        logger.error(f"Round {round_num} - {role.id} 失败: {e}\n{traceback.format_exc()}")
                        continue

                    if progress_callback:
                        rname = role.name if lang == "zh" else role.name_en
                        done_msg = (f"Round {round_num} - {rname} 完成 ({completed_calls}/{total_calls})"
                                    if lang == "zh"
                                    else f"Round {round_num} - {rname} done ({completed_calls}/{total_calls})")
                        progress_callback(done_msg, completed_calls / total_calls)

            # 按 analyst_id 排序保证结果顺序一致
            round_result.predictions.sort(key=lambda p: p.analyst_id)
            result.rounds.append(round_result)

            round_elapsed = round(time.time() - round_start, 1)
            round_timings.append(round_elapsed)
            logger.info(f"Round {round_num} 完成: {round_elapsed}s")

            # 收集本轮预测供下一轮使用
            previous_round_predictions = [p.to_dict() for p in round_result.predictions]

        result.total_duration_seconds = time.time() - start_time
        result.round_timings = round_timings
        logger.info(
            f"辩论完成: {result.total_llm_calls} calls, "
            f"{result.total_duration_seconds:.1f}s, "
            f"per-round: {round_timings}"
        )

        return result

    def _call_analyst(
        self,
        role: AnalystRole,
        matchup_text: str,
        graph_context: str,
        round_num: int,
        previous_predictions: Optional[List[Dict[str, Any]]],
        lang: str = "en",
        extra_context: Optional[str] = None,
    ) -> AnalystPrediction:
        """调用单个分析师LLM"""
        messages = build_analyst_prompt(
            role=role,
            matchup_text=matchup_text,
            graph_context=graph_context,
            round_num=round_num,
            previous_predictions=previous_predictions,
            lang=lang,
            extra_context=extra_context,
        )

        response = self.llm.chat_json(
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

        return AnalystPrediction(
            analyst_id=role.id,
            round_num=round_num,
            moneyline_pick=response.get("moneyline_pick", ""),
            moneyline_confidence=float(response.get("moneyline_confidence", 0.5)),
            spread_pick=response.get("spread_pick", ""),
            spread_confidence=float(response.get("spread_confidence", 0.5)),
            total_pick=response.get("total_pick", ""),
            total_confidence=float(response.get("total_confidence", 0.5)),
            reasoning=response.get("reasoning", ""),
            key_factors=response.get("key_factors", []),
            changed_from_previous=response.get("changed_from_previous", False),
            change_reasoning=response.get("change_reasoning", ""),
        )
