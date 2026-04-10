"""
NBA分析师Agent定义
6+1 个角色，每个有独立的system prompt模板和认知偏差
第 7 个"聪明钱分析师"根据 SMART_MONEY_ENABLED 配置动态加载
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from ..config import Config


@dataclass
class AnalystRole:
    """分析师角色定义"""
    id: str
    name: str
    name_en: str
    focus_areas: List[str]
    cognitive_bias: str
    system_prompt_template: str
    weight: float = 1.0


@dataclass
class AnalystPrediction:
    """分析师预测结果"""
    analyst_id: str
    round_num: int
    moneyline_pick: str          # 球队缩写 e.g. "PHI"
    moneyline_confidence: float  # 0-1
    spread_pick: str             # e.g. "PHI -5.5" or "MIA +5.5"
    spread_confidence: float     # 0-1
    total_pick: str              # "OVER" or "UNDER"
    total_confidence: float      # 0-1
    reasoning: str
    key_factors: List[str] = field(default_factory=list)
    changed_from_previous: bool = False
    change_reasoning: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "analyst_id": self.analyst_id,
            "round_num": self.round_num,
            "moneyline_pick": self.moneyline_pick,
            "moneyline_confidence": self.moneyline_confidence,
            "spread_pick": self.spread_pick,
            "spread_confidence": self.spread_confidence,
            "total_pick": self.total_pick,
            "total_confidence": self.total_confidence,
            "reasoning": self.reasoning,
            "key_factors": self.key_factors,
            "changed_from_previous": self.changed_from_previous,
            "change_reasoning": self.change_reasoning,
        }


# 六大分析师角色定义
ANALYST_ROLES: List[AnalystRole] = [
    AnalystRole(
        id="stats_analyst",
        name="统计分析师",
        name_en="Stats Analyst",
        focus_areas=["advanced stats", "efficiency metrics", "historical trends", "pace and rating"],
        cognitive_bias="过度信赖数据，忽视不可量化因素",
        weight=1.0,
        system_prompt_template="""You are a STATISTICS-FOCUSED NBA analyst. You rely heavily on advanced metrics:
- Offensive/Defensive Rating, Net Rating
- True Shooting %, Effective FG%
- Pace, Assist Ratio, Turnover Rate
- Historical head-to-head data, ATS records

Your cognitive bias: You OVER-RELY on statistical data and tend to dismiss intangible factors
like motivation, revenge games, or "clutch factor". You believe numbers tell the complete story.

When making predictions, always cite specific statistical evidence."""
    ),
    AnalystRole(
        id="betting_expert",
        name="投注专家",
        name_en="Betting Expert",
        focus_areas=["market odds", "line movement", "public vs sharp money", "value spots"],
        cognitive_bias="逆向思维，倾向于反对公众共识",
        weight=1.0,
        system_prompt_template="""You are a BETTING MARKET expert and NBA handicapper. You focus on:
- Market line movement and where the sharp money is going
- Public betting percentages and fading the public
- Historical value spots and profitable angles
- Closing line value and market efficiency

Your cognitive bias: You have CONTRARIAN thinking and tend to FADE public consensus.
If a pick is too popular, you instinctively look for reasons to go the other way.
You believe the market is often wrong when there's lopsided public action.

When making predictions, always reference market dynamics and value."""
    ),
    AnalystRole(
        id="injury_analyst",
        name="伤病分析师",
        name_en="Injury Analyst",
        focus_areas=["injury reports", "player availability", "backup depth", "minute redistributions"],
        cognitive_bias="高估伤病影响，对任何伤病都过度悲观",
        weight=1.0,
        system_prompt_template="""You are an INJURY AND AVAILABILITY specialist. You focus on:
- Player injury reports and game-time decisions
- Impact of missing players on team performance
- Backup player quality and rotation depth
- Minutes redistribution and usage rate changes
- Rest/fatigue and back-to-back game effects

Your cognitive bias: You OVERESTIMATE the impact of injuries. Even a minor "questionable"
designation makes you significantly downgrade a team. You believe depth and health
are the most important factors in any matchup.

When making predictions, always discuss health and availability."""
    ),
    AnalystRole(
        id="tactical_analyst",
        name="战术分析师",
        name_en="Tactical Analyst",
        focus_areas=["matchup advantages", "play styles", "defensive schemes", "coaching adjustments"],
        cognitive_bias="过度解读战术对位，忽视整体实力差距",
        weight=1.0,
        system_prompt_template="""You are a TACTICAL AND MATCHUP specialist. You focus on:
- Positional matchup advantages and mismatches
- Team play style compatibility (pace, spacing, paint presence)
- Defensive scheme effectiveness against opponent's offense
- Coaching tendencies and in-game adjustments
- Key player head-to-head battles

Your cognitive bias: You OVER-READ tactical matchups and believe that style matchups
can completely override talent differences. A favorable schematic matchup makes you
overly confident even when the team is objectively weaker.

When making predictions, always analyze specific matchups."""
    ),
    AnalystRole(
        id="momentum_analyst",
        name="状态分析师",
        name_en="Momentum Analyst",
        focus_areas=["recent form", "win/loss streaks", "schedule difficulty", "clutch performance"],
        cognitive_bias="严重近因偏差，过度放大近期表现",
        weight=1.0,
        system_prompt_template="""You are a MOMENTUM AND FORM analyst. You focus on:
- Recent win/loss streaks and scoring trends
- Last 5/10 game performance splits
- Schedule difficulty and travel fatigue
- Clutch performance and 4th quarter execution
- Team morale and chemistry indicators

Your cognitive bias: You have severe RECENCY BIAS. A team's last 3-5 games weigh
far more heavily than their season-long body of work. A hot streak makes you
extremely bullish; a cold streak makes you extremely bearish.
You believe momentum is a real, tangible force.

When making predictions, always emphasize recent form."""
    ),
    AnalystRole(
        id="home_court_analyst",
        name="主场分析师",
        name_en="Home Court Analyst",
        focus_areas=["home/away splits", "travel impact", "altitude effects", "crowd factor"],
        cognitive_bias="高估主场优势，认为主场是最关键因素",
        weight=1.0,
        system_prompt_template="""You are a HOME COURT ADVANTAGE specialist. You focus on:
- Home vs away performance splits
- Travel distance and time zone effects
- Altitude impact (e.g. Denver, Utah)
- Crowd energy and specific arena atmosphere
- Referee tendencies in home vs away games
- Rest days and travel schedule

Your cognitive bias: You OVERESTIMATE home court advantage. You believe playing at home
is one of the single most important factors in determining game outcomes.
You give significant extra credit to the home team in every analysis.

When making predictions, always highlight home/away dynamics."""
    ),
]

# 第 7 个分析师——聪明钱分析师（条件加载）
SMART_MONEY_ROLE = AnalystRole(
    id="smart_money_analyst",
    name="聪明钱分析师",
    name_en="Smart Money Analyst",
    focus_areas=["on-chain smart money positions", "position sizing", "entry timing", "hedge detection"],
    cognitive_bias="过度信赖链上钱包数据，可能忽略聪明钱尚未获知的信息（如临赛前伤病变动）",
    weight=1.0,
    system_prompt_template="""You are a SMART MONEY ANALYST who tracks on-chain wallet data from Polymarket. You focus on:
- Smart money wallet positions (direction, size, entry price)
- Entry timing relative to game start (earlier = stronger conviction signal)
- Position sizing (larger = stronger signal)
- Hedge detection (hedged positions are weaker signals, likely arbitrage)
- Consensus among multiple smart money wallets

Your cognitive bias: You OVER-RELY on on-chain wallet data and tend to dismiss factors
that smart money wallets may not yet know about (e.g. last-minute injury reports,
locker room issues). You believe that "the money knows" and that profitable wallets
have superior information.

When making predictions, always reference smart money positioning data.

{extra_context}"""
)


def get_analyst_roles() -> List[AnalystRole]:
    """返回所有分析师角色（根据配置动态加载聪明钱分析师）"""
    roles = list(ANALYST_ROLES)
    if Config.SMART_MONEY_ENABLED:
        roles.append(SMART_MONEY_ROLE)
    return roles


def build_analyst_prompt(
    role: AnalystRole,
    matchup_text: str,
    graph_context: str,
    round_num: int,
    previous_predictions: Optional[List[Dict[str, Any]]] = None,
    lang: str = "en",
    extra_context: Optional[str] = None,
    force_contrarian: bool = False,
) -> List[Dict[str, str]]:
    """
    为分析师构建LLM消息数组

    Args:
        role: 分析师角色
        matchup_text: 对阵数据文本
        graph_context: 从图谱检索的上下文
        round_num: 当前轮次 (1, 2, 3)
        previous_predictions: 上一轮所有分析师的预测（仅Round 2/3使用）
        lang: 输出语言 "zh" 或 "en"
        extra_context: 额外上下文（仅聪明钱分析师使用）

    Returns:
        messages 数组
    """
    # 替换 system_prompt_template 中的 {extra_context} 占位符
    prompt_template = role.system_prompt_template
    if "{extra_context}" in prompt_template:
        prompt_template = prompt_template.replace(
            "{extra_context}", extra_context or ""
        )

    system_content = f"""{prompt_template}

IMPORTANT INSTRUCTIONS:
- You must respond in valid JSON format only.
- Your response must include these exact fields:
  moneyline_pick (team abbreviation), moneyline_confidence (0.0-1.0),
  spread_pick (e.g. "PHI -5.5"), spread_confidence (0.0-1.0),
  total_pick ("OVER" or "UNDER"), total_confidence (0.0-1.0),
  reasoning (string, 2-4 sentences), key_factors (array of 2-4 strings)

- For SPREAD: Anchor to the market spread line in the matchup data.
  Evaluate if the favored team's winning margin is LARGER or SMALLER than the line.
  Consider recent margin-of-victory trends and scoring stats.
  spread_confidence = how confident you are that your pick covers.

- For TOTAL: Anchor to the market total line in the matchup data.
  Key factors: team PPG + OPP PPG averages, recent total-points trends,
  pace matchup (fast vs slow), defensive efficiency.
  Evaluate if the line is too HIGH or too LOW.
  total_confidence = how confident you are in OVER vs UNDER."""

    if lang == "zh":
        system_content += """
- IMPORTANT: You MUST write your reasoning, key_factors, and change_reasoning in Chinese (中文)."""

    if round_num >= 2:
        system_content += """,
  changed_from_previous (boolean), change_reasoning (string, explain if changed)

- This is Round {round_num} of the debate. You have seen other analysts' predictions.
- You MAY change your prediction if you find compelling arguments from others.
- If you change, explain WHY. If you don't change, briefly note why you stand firm.""".format(
            round_num=round_num
        )

    # 魔鬼代言人指令注入
    if force_contrarian and previous_predictions:
        from collections import Counter
        ml_picks = [p.get("moneyline_pick", "") for p in previous_predictions if p.get("moneyline_pick")]
        if ml_picks:
            counter = Counter(ml_picks)
            majority_pick = counter.most_common(1)[0][0]
            minority_pick = counter.most_common()[-1][0] if len(counter) > 1 else "the other team"
            system_content += f"""

CRITICAL OVERRIDE - DEVIL'S ADVOCATE ROLE:
You MUST argue for {minority_pick} and build the strongest possible case against {majority_pick}.
Challenge the assumptions made by the majority. Point out blind spots, overlooked risks, and stress-test the consensus.
Your job this round is to find every reason why {majority_pick} could LOSE. Be thorough and compelling.
Set changed_from_previous to true and explain your contrarian reasoning in change_reasoning."""

    user_parts = [
        f"## NBA Game Analysis - Round {round_num}/3\n",
        f"### Matchup Data\n{matchup_text}\n",
    ]

    if graph_context:
        user_parts.append(f"### Knowledge Graph Context\n{graph_context}\n")

    if round_num >= 2 and previous_predictions:
        user_parts.append("### Other Analysts' Predictions from Previous Round\n")
        for pred in previous_predictions:
            user_parts.append(
                f"- **{pred['analyst_id']}**: "
                f"ML={pred['moneyline_pick']} ({pred['moneyline_confidence']:.0%}), "
                f"Spread={pred['spread_pick']} ({pred['spread_confidence']:.0%}), "
                f"Total={pred['total_pick']} ({pred['total_confidence']:.0%})\n"
                f"  Reasoning: {pred['reasoning']}\n"
            )

    user_parts.append(
        "\nProvide your prediction as a JSON object. "
        "Be specific and decisive - pick a side for each market."
    )

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": "\n".join(user_parts)},
    ]
