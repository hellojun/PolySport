"""
NBA对阵数据模型
"""

import uuid
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List


@dataclass
class TeamInfo:
    """球队信息"""
    name: str           # "Philadelphia 76ers"
    abbreviation: str   # "PHI"


@dataclass
class MarketOdds:
    """市场赔率"""
    moneyline_home: Optional[float] = None   # 主队胜率 0-1
    moneyline_away: Optional[float] = None   # 客队胜率 0-1
    spread_line: Optional[float] = None      # 让分线 (e.g. -5.5)
    spread_home: Optional[float] = None      # 主队让分赔率
    spread_away: Optional[float] = None      # 客队让分赔率
    total_line: Optional[float] = None       # 总分线 (e.g. 215.5)
    total_over: Optional[float] = None       # 大分赔率
    total_under: Optional[float] = None      # 小分赔率
    volume: Optional[float] = None           # 投注量

    def to_dict(self) -> Dict[str, Any]:
        return {
            "moneyline_home": self.moneyline_home,
            "moneyline_away": self.moneyline_away,
            "spread_line": self.spread_line,
            "spread_home": self.spread_home,
            "spread_away": self.spread_away,
            "total_line": self.total_line,
            "total_over": self.total_over,
            "total_under": self.total_under,
            "volume": self.volume,
        }


@dataclass
class MatchupInput:
    """对阵输入"""
    matchup_id: str = ""
    home_team: TeamInfo = field(default_factory=lambda: TeamInfo("", ""))
    away_team: TeamInfo = field(default_factory=lambda: TeamInfo("", ""))
    market_odds: Optional[MarketOdds] = None
    game_date: Optional[str] = None
    notes: Optional[str] = None
    source: str = "manual"
    nba_stats: Optional[Dict[str, Any]] = None
    enriched_text: Optional[str] = None
    smart_money_data: Optional[Dict[str, Any]] = None
    smart_money_context: Optional[str] = None
    condition_id: Optional[str] = None
    token_ids: Optional[List[str]] = None

    def __post_init__(self):
        if not self.matchup_id:
            self.matchup_id = str(uuid.uuid4())[:8]

    def to_graph_text(self) -> str:
        """转为自然语言文本，用于喂给 Zep 图谱"""
        parts = [
            f"NBA Game Matchup: {self.away_team.name} ({self.away_team.abbreviation}) "
            f"at {self.home_team.name} ({self.home_team.abbreviation}).",
        ]

        if self.game_date:
            parts.append(f"Game Date: {self.game_date}.")

        if self.market_odds:
            odds = self.market_odds
            if odds.moneyline_home is not None and odds.moneyline_away is not None:
                parts.append(
                    f"Moneyline odds: {self.home_team.abbreviation} "
                    f"{odds.moneyline_home:.1%} implied probability, "
                    f"{self.away_team.abbreviation} "
                    f"{odds.moneyline_away:.1%} implied probability."
                )
            if odds.spread_line is not None:
                parts.append(
                    f"Spread: {self.home_team.abbreviation} {odds.spread_line:+.1f}."
                )
            if odds.total_line is not None:
                parts.append(
                    f"Total (Over/Under): {odds.total_line:.1f}."
                )

        if self.notes:
            parts.append(f"Additional context: {self.notes}")

        return " ".join(parts)

    def to_full_text(self) -> str:
        """返回完整文本（手动输入 + 自动拉取数据），用于注入图谱和辩论"""
        base = self.to_graph_text()
        if self.enriched_text:
            return f"{base}\n\n{self.enriched_text}"
        return base

    def to_dict(self) -> Dict[str, Any]:
        return {
            "matchup_id": self.matchup_id,
            "home_team": {"name": self.home_team.name, "abbreviation": self.home_team.abbreviation},
            "away_team": {"name": self.away_team.name, "abbreviation": self.away_team.abbreviation},
            "market_odds": self.market_odds.to_dict() if self.market_odds else None,
            "game_date": self.game_date,
            "notes": self.notes,
            "source": self.source,
        }

    @classmethod
    def from_request(cls, data: dict) -> 'MatchupInput':
        """从API请求数据构建"""
        home = data.get("home_team", {})
        away = data.get("away_team", {})

        home_team = TeamInfo(
            name=home.get("name", ""),
            abbreviation=home.get("abbreviation", ""),
        )
        away_team = TeamInfo(
            name=away.get("name", ""),
            abbreviation=away.get("abbreviation", ""),
        )

        market_odds = None
        odds_data = data.get("market_odds")
        if odds_data:
            market_odds = MarketOdds(
                moneyline_home=odds_data.get("moneyline_home"),
                moneyline_away=odds_data.get("moneyline_away"),
                spread_line=odds_data.get("spread_line"),
                spread_home=odds_data.get("spread_home"),
                spread_away=odds_data.get("spread_away"),
                total_line=odds_data.get("total_line"),
                total_over=odds_data.get("total_over"),
                total_under=odds_data.get("total_under"),
                volume=odds_data.get("volume"),
            )

        return cls(
            matchup_id=data.get("matchup_id", ""),
            home_team=home_team,
            away_team=away_team,
            market_odds=market_odds,
            game_date=data.get("game_date"),
            notes=data.get("notes"),
            source=data.get("source", "manual"),
            condition_id=data.get("condition_id"),
            token_ids=data.get("token_ids"),
        )
