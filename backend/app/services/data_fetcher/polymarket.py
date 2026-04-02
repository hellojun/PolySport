"""
Polymarket Gamma API 数据拉取服务
从 Polymarket 获取 NBA 比赛盘口数据（moneyline / spread / total）
"""

import re
import requests
from typing import List, Optional, Tuple, Dict

from ...config import Config
from ...utils.logger import get_logger

logger = get_logger('mirofish.data_fetcher.polymarket')

# 缩写 → 全名 映射（硬编码，不走网络）
_ABBR_TO_TEAM: Dict[str, dict] = {}


def _ensure_team_map():
    global _ABBR_TO_TEAM
    if not _ABBR_TO_TEAM:
        from .nba_stats import _TEAM_FULLNAME
        for abbr, full_name in _TEAM_FULLNAME.items():
            _ABBR_TO_TEAM[abbr] = {
                'name': full_name,
                'abbreviation': abbr,
            }


class PolymarketService:
    """从 Polymarket Gamma API 获取 NBA 盘口"""

    BASE_URL = "https://gamma-api.polymarket.com"
    TIMEOUT = 15  # seconds

    def fetch_nba_events(self, game_date: str) -> List[dict]:
        """
        获取指定日期的 NBA 盘口列表

        Args:
            game_date: YYYY-MM-DD 格式的日期

        Returns:
            解析后的盘口列表
        """
        _ensure_team_map()

        try:
            resp = requests.get(
                f"{self.BASE_URL}/events",
                params={
                    "active": "true",
                    "closed": "false",
                    "limit": 100,
                    "tag_slug": "nba",
                },
                timeout=self.TIMEOUT,
            )
            resp.raise_for_status()
            raw_events = resp.json()
        except requests.RequestException as e:
            logger.error(f"Polymarket API 请求失败: {e}")
            raise RuntimeError(f"Polymarket API 请求失败: {e}")

        results = []
        for raw in raw_events:
            parsed = self._parse_event(raw, game_date)
            if parsed:
                results.append(parsed)

        # 用 NBA API ScoreboardV2 补充真实比赛开始时间
        if results:
            game_times = self._fetch_nba_game_times(game_date)
            for event in results:
                key = f"{event['away_team']['abbreviation']}_{event['home_team']['abbreviation']}"
                event['game_time'] = game_times.get(key, '')

        logger.info(f"Polymarket: 日期 {game_date} 找到 {len(results)} 场 NBA 比赛")
        return results

    def _parse_event(self, raw: dict, target_date: str) -> Optional[dict]:
        """解析单个 event，按日期过滤，返回结构化字典"""
        try:
            ticker = raw.get("ticker", "")
            if not ticker.startswith("nba-"):
                return None

            # 从 ticker 提取球队和日期
            extracted = self._extract_teams_from_ticker(ticker)
            if not extracted:
                return None
            away_abbr, home_abbr, event_date = extracted

            # 日期过滤
            if event_date != target_date:
                return None

            # 查找球队全名
            home_info = _ABBR_TO_TEAM.get(home_abbr.upper())
            away_info = _ABBR_TO_TEAM.get(away_abbr.upper())
            if not home_info or not away_info:
                logger.warning(f"未知球队缩写: {home_abbr} 或 {away_abbr}, ticker={ticker}")
                return None

            # 解析市场赔率
            markets = raw.get("markets", [])
            market_odds = self._extract_market_odds(markets, away_abbr.upper(), home_abbr.upper())

            # 提取 moneyline 市场的 conditionId / clobTokenIds 供聪明钱服务使用
            ml_condition_id = ""
            ml_token_ids = []
            for mkt in markets:
                if (mkt.get("sportsMarketType") or "").lower() == "moneyline":
                    ml_condition_id = mkt.get("conditionId") or mkt.get("condition_id") or ""
                    raw_tokens = mkt.get("clobTokenIds") or mkt.get("clob_token_ids") or "[]"
                    if isinstance(raw_tokens, str):
                        import json as _json
                        try:
                            ml_token_ids = _json.loads(raw_tokens)
                        except (ValueError, TypeError):
                            ml_token_ids = []
                    else:
                        ml_token_ids = list(raw_tokens)
                    break

            return {
                "event_id": str(raw.get("id", "")),
                "title": raw.get("title", f"{away_info['name']} vs. {home_info['name']}"),
                "game_date": event_date,
                "game_time": "",  # 由 _fetch_nba_game_times 统一填充
                "home_team": {
                    "name": home_info["name"],
                    "abbreviation": home_info["abbreviation"],
                },
                "away_team": {
                    "name": away_info["name"],
                    "abbreviation": away_info["abbreviation"],
                },
                "market_odds": market_odds,
                "condition_id": ml_condition_id,
                "token_ids": ml_token_ids,
            }

        except Exception as e:
            logger.warning(f"解析 event 失败: {e}, ticker={raw.get('ticker', '?')}")
            return None

    def _fetch_nba_game_times(self, game_date: str) -> Dict[str, str]:
        """
        从 CDN schedule 获取指定日期所有比赛的开赛时间。
        返回 {"PHX_ORL": "2026-03-25T19:00:00Z", ...} (ISO UTC)
        """
        if not Config.NBA_API_ENABLED:
            return {}

        try:
            from .nba_stats import NBAStatsService
            svc = NBAStatsService()
            schedule = svc._fetch_schedule()
            if not schedule:
                return {}

            result = {}
            game_dates = schedule.get('leagueSchedule', {}).get('gameDates', [])
            for gd in game_dates:
                for g in gd.get('games', []):
                    g_date = (g.get('gameDateEst', '') or '')[:10]
                    if g_date != game_date:
                        continue
                    away_abbr = g.get('awayTeam', {}).get('teamTricode', '')
                    home_abbr = g.get('homeTeam', {}).get('teamTricode', '')
                    if not away_abbr or not home_abbr:
                        continue
                    game_time = g.get('gameDateTimeUTC', '')
                    if game_time:
                        result[f"{away_abbr}_{home_abbr}"] = game_time

            logger.info(f"NBA CDN schedule: 日期 {game_date} 获取到 {len(result)} 场比赛时间")
            return result
        except Exception as e:
            logger.warning(f"获取NBA赛程时间失败: {e}")
            return {}

    def _extract_teams_from_ticker(self, ticker: str) -> Optional[Tuple[str, str, str]]:
        """
        'nba-phi-mia-2026-03-30' → ('PHI', 'MIA', '2026-03-30')
        返回 (away_abbr, home_abbr, date) 或 None
        """
        # 格式: nba-{away}-{home}-{YYYY}-{MM}-{DD}
        match = re.match(
            r'^nba-([a-z]{2,3})-([a-z]{2,3})-(\d{4}-\d{2}-\d{2})$',
            ticker,
            re.IGNORECASE,
        )
        if not match:
            return None
        away = match.group(1).upper()
        home = match.group(2).upper()
        date = match.group(3)
        return away, home, date

    def _extract_market_odds(self, markets: list, away_abbr: str, home_abbr: str) -> dict:
        """
        从 markets 数组中按 sportsMarketType 提取赔率

        实际 API 返回:
        - sportsMarketType: "moneyline", "spreads", "totals"
          (跳过 "first_half_*", "points", "rebounds", "assists" 等)
        - outcomePrices: JSON string "[0.55, 0.45]"
        - outcomes: JSON string '["76ers", "Heat"]' 或 '["Over", "Under"]'
        - 可能有多条 spread/total 线，取成交量最大的
        """
        import json

        odds = {
            "moneyline_home": None,
            "moneyline_away": None,
            "spread_line": None,
            "spread_home": None,
            "spread_away": None,
            "total_line": None,
            "total_over": None,
            "total_under": None,
            "volume": None,
        }

        total_volume = 0.0
        best_spread_vol = -1.0
        best_total_vol = -1.0

        for mkt in markets:
            sport_type = (mkt.get("sportsMarketType") or "").lower()

            # 跳过半场盘、球员盘等
            if sport_type.startswith("first_half") or sport_type in (
                "points", "rebounds", "assists",
            ):
                continue

            # 解析价格和结果
            try:
                prices_raw = mkt.get("outcomePrices", "[]")
                prices = json.loads(prices_raw) if isinstance(prices_raw, str) else prices_raw
                prices = [float(p) for p in prices]

                outcomes_raw = mkt.get("outcomes", "[]")
                outcomes = json.loads(outcomes_raw) if isinstance(outcomes_raw, str) else outcomes_raw
            except (json.JSONDecodeError, ValueError, TypeError):
                continue

            if len(prices) < 2 or len(outcomes) < 2:
                continue

            # 成交量
            vol = 0.0
            try:
                vol = float(mkt.get("volume") or mkt.get("volumeNum") or 0)
            except (ValueError, TypeError):
                pass
            total_volume += vol

            # === Moneyline ===
            if sport_type == "moneyline":
                idx_home, idx_away = self._match_outcome_indices(
                    outcomes, home_abbr, away_abbr
                )
                if idx_home is not None and idx_away is not None:
                    odds["moneyline_home"] = prices[idx_home]
                    odds["moneyline_away"] = prices[idx_away]

            # === Spreads (取成交量最大的一条线) ===
            elif sport_type == "spreads":
                if vol > best_spread_vol:
                    spread_val = self._parse_spread_line(mkt, outcomes, home_abbr, away_abbr)
                    if spread_val is not None:
                        odds["spread_line"] = spread_val["line"]
                        odds["spread_home"] = spread_val["home_price"]
                        odds["spread_away"] = spread_val["away_price"]
                        best_spread_vol = vol

            # === Totals (取成交量最大的一条线) ===
            elif sport_type == "totals":
                if vol > best_total_vol:
                    total_val = self._parse_total_line(mkt, outcomes)
                    if total_val is not None:
                        odds["total_line"] = total_val["line"]
                        odds["total_over"] = total_val["over_price"]
                        odds["total_under"] = total_val["under_price"]
                        best_total_vol = vol

        odds["volume"] = round(total_volume, 2) if total_volume > 0 else None
        return odds

    def _match_outcome_indices(
        self, outcomes: list, home_abbr: str, away_abbr: str
    ) -> Tuple[Optional[int], Optional[int]]:
        """
        在 outcomes 列表中找到主队和客队的索引。
        Polymarket outcomes 通常是球队昵称，如 "76ers"、"Heat"。
        """
        idx_home = None
        idx_away = None

        home_info = _ABBR_TO_TEAM.get(home_abbr) or {}
        away_info = _ABBR_TO_TEAM.get(away_abbr) or {}
        home_name = home_info.get("name", "").lower()  # "Miami Heat"
        away_name = away_info.get("name", "").lower()  # "Philadelphia 76ers"
        # 提取昵称: "76ers", "Heat"
        home_nickname = home_name.split()[-1] if home_name else ""
        away_nickname = away_name.split()[-1] if away_name else ""

        for i, outcome in enumerate(outcomes):
            o_lower = outcome.lower().strip()
            # 检查是否匹配主队（缩写、全名、昵称）
            if (home_abbr.lower() in o_lower
                    or (home_name and home_name in o_lower)
                    or (home_nickname and home_nickname == o_lower)):
                idx_home = i
            # 检查是否匹配客队
            elif (away_abbr.lower() in o_lower
                  or (away_name and away_name in o_lower)
                  or (away_nickname and away_nickname == o_lower)):
                idx_away = i

        # 如果没精确匹配，假设第一个是 Away，第二个是 Home（Polymarket 惯例：先客后主）
        if idx_home is None and idx_away is None and len(outcomes) == 2:
            idx_away = 0
            idx_home = 1

        return idx_home, idx_away

    def _parse_spread_line(
        self, mkt: dict, outcomes: list, home_abbr: str, away_abbr: str
    ) -> Optional[dict]:
        """
        解析让分盘。
        Polymarket 的 spread 通常以客队视角给出。
        需要转换为主队视角: spread_line = -(客队让分线)
        """
        import json

        try:
            prices_raw = mkt.get("outcomePrices", "[]")
            prices = json.loads(prices_raw) if isinstance(prices_raw, str) else prices_raw
            prices = [float(p) for p in prices]
        except (json.JSONDecodeError, ValueError, TypeError):
            return None

        if len(prices) < 2:
            return None

        # 尝试从 market question/title 中提取让分值
        # 实际格式: "Spread: 76ers (-2.5)" 或 groupItemTitle "Spread -2.5"
        question = mkt.get("question", "") or ""
        group_title = mkt.get("groupItemTitle", "") or ""

        # 优先从括号中提取，如 "(-2.5)" — 避免匹配到球队名中的数字(如76ers)
        spread_match = re.search(r'\(([+-]?\d+\.?\d*)\)', question)
        if not spread_match:
            # 尝试 groupItemTitle 格式: "Spread -2.5"
            spread_match = re.search(r'[Ss]pread\s+([+-]?\d+\.?\d*)', group_title)
        if not spread_match:
            spread_match = re.search(r'[Ss]pread\s+([+-]?\d+\.?\d*)', question)
        if not spread_match:
            return None

        spread_num = float(spread_match.group(1))

        # 判断让分线是针对哪个队
        # question 格式如 "Spread: 76ers (-2.5)" — 用的是昵称
        q_lower = question.lower()
        home_info = _ABBR_TO_TEAM.get(home_abbr) or {}
        away_info = _ABBR_TO_TEAM.get(away_abbr) or {}
        home_name_lower = home_info.get("name", "").lower()
        away_name_lower = away_info.get("name", "").lower()
        home_nickname = home_name_lower.split()[-1] if home_name_lower else ""
        away_nickname = away_name_lower.split()[-1] if away_name_lower else ""

        # 默认认为 spread 给的是客队视角
        is_home_perspective = False
        if (home_abbr.lower() in q_lower
                or (home_name_lower and home_name_lower in q_lower)
                or (home_nickname and home_nickname in q_lower)):
            is_home_perspective = True

        if is_home_perspective:
            home_line = spread_num
        else:
            # 客队视角，取反得主队
            home_line = -spread_num

        # 找出哪个价格对应主/客
        idx_home, idx_away = self._match_outcome_indices(outcomes, home_abbr, away_abbr)
        if idx_home is not None and idx_away is not None:
            return {
                "line": home_line,
                "home_price": prices[idx_home],
                "away_price": prices[idx_away],
            }

        # fallback: 假设 prices[0] = 客队, prices[1] = 主队
        return {
            "line": home_line,
            "home_price": prices[1],
            "away_price": prices[0],
        }

    def _parse_total_line(self, mkt: dict, outcomes: list) -> Optional[dict]:
        """解析总分盘"""
        import json

        try:
            prices_raw = mkt.get("outcomePrices", "[]")
            prices = json.loads(prices_raw) if isinstance(prices_raw, str) else prices_raw
            prices = [float(p) for p in prices]
        except (json.JSONDecodeError, ValueError, TypeError):
            return None

        if len(prices) < 2:
            return None

        # 从 question/title 中提取总分线
        # 格式: "76ers vs. Heat: O/U 246.5" 或 groupItemTitle "O/U 246.5"
        question = mkt.get("question", "") or ""
        group_title = mkt.get("groupItemTitle", "") or ""

        # 优先匹配 "O/U 246.5" 格式
        total_match = re.search(r'O/U\s+(\d+\.?\d*)', question, re.IGNORECASE)
        if not total_match:
            total_match = re.search(r'O/U\s+(\d+\.?\d*)', group_title, re.IGNORECASE)
        if not total_match:
            # 回退: 匹配大于100的数字（总分线一般 >150）
            total_match = re.search(r'(\d{3}\.?\d*)', question)
        if not total_match:
            return None

        total_line = float(total_match.group(1))

        # 判断 Over/Under 对应哪个价格
        idx_over = None
        idx_under = None
        for i, outcome in enumerate(outcomes):
            o_lower = outcome.lower()
            if "over" in o_lower or "more" in o_lower:
                idx_over = i
            elif "under" in o_lower or "less" in o_lower or "fewer" in o_lower:
                idx_under = i

        if idx_over is None and idx_under is None and len(outcomes) == 2:
            # 默认: 第一个是 Over，第二个是 Under
            idx_over = 0
            idx_under = 1

        if idx_over is not None and idx_under is not None:
            return {
                "line": total_line,
                "over_price": prices[idx_over],
                "under_price": prices[idx_under],
            }
        return None
