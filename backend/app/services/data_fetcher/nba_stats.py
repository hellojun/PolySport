"""
NBA Stats API 数据拉取服务
使用 nba_api 获取球队战绩、高级统计、球员数据和近期比赛
"""

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional, List, Dict, Any

from nba_api.stats.static import teams as static_teams
from nba_api.stats.endpoints import (
    LeagueStandings,
    LeagueDashTeamStats,
    TeamPlayerDashboard,
    TeamGameLog,
    scoreboardv3,
)

from ...config import Config
from ...utils.logger import get_logger

logger = get_logger('mirofish.data_fetcher.nba_stats')


def _current_season() -> str:
    """推断当前 NBA 赛季字符串，如 '2025-26'"""
    now = datetime.now()
    year = now.year if now.month >= 10 else now.year - 1
    return f"{year}-{str(year + 1)[-2:]}"


class NBAStatsService:
    """从 nba_api 拉取球队和球员数据"""

    def __init__(self):
        self._team_map: Dict[str, int] = {}  # abbreviation → team_id
        self._delay = Config.NBA_API_DELAY
        self._timeout = Config.NBA_API_TIMEOUT
        self._proxy = Config.NBA_API_PROXY or None

    def _get_team_id(self, abbreviation: str) -> Optional[int]:
        """缩写 → team_id，使用 nba_api.stats.static.teams"""
        if not self._team_map:
            for t in static_teams.get_teams():
                self._team_map[t['abbreviation']] = t['id']

        abbr = abbreviation.upper()
        team_id = self._team_map.get(abbr)
        if team_id is None:
            logger.warning(f"未找到球队缩写: {abbr}")
        return team_id

    def _sleep(self):
        time.sleep(self._delay)

    # ------------------------------------------------------------------
    # 数据拉取方法 — 每个方法独立 try/except，失败返回 None
    # ------------------------------------------------------------------

    def _fetch_standings(self, season: str) -> Dict[int, dict]:
        """LeagueStandings，返回 team_id → standings 映射"""
        try:
            data = LeagueStandings(
                season=season,
                timeout=self._timeout,
                proxy=self._proxy,
            ).get_normalized_dict()
            rows = data.get('Standings', [])
            result = {}
            for row in rows:
                tid = row.get('TeamID')
                if tid is None:
                    continue
                result[tid] = {
                    'wins': row.get('WINS', 0),
                    'losses': row.get('LOSSES', 0),
                    'win_pct': row.get('WinPCT', 0.0),
                    'conference': row.get('Conference', ''),
                    'conference_rank': row.get('PlayoffRank', 0),
                    'streak': row.get('strCurrentStreak', ''),
                    'last_10': row.get('L10', ''),
                }
            return result
        except Exception as e:
            logger.warning(f"拉取联盟排名失败: {e}")
            return {}

    def _fetch_advanced_stats(self, team_id: int, season: str) -> Optional[dict]:
        """LeagueDashTeamStats(MeasureType='Advanced')"""
        try:
            data = LeagueDashTeamStats(
                team_id_nullable=team_id,
                measure_type_detailed_defense='Advanced',
                season=season,
                timeout=self._timeout,
                proxy=self._proxy,
            ).get_normalized_dict()
            rows = data.get('LeagueDashTeamStats', [])
            for row in rows:
                if row.get('TEAM_ID') == team_id:
                    return {
                        'off_rating': row.get('OFF_RATING'),
                        'def_rating': row.get('DEF_RATING'),
                        'net_rating': row.get('NET_RATING'),
                        'pace': row.get('PACE'),
                        'ts_pct': row.get('TS_PCT'),
                        'efg_pct': row.get('EFG_PCT'),
                    }
            return None
        except Exception as e:
            logger.warning(f"拉取高级统计失败 (team_id={team_id}): {e}")
            return None

    def _fetch_players(self, team_id: int, season: str) -> Optional[List[dict]]:
        """TeamPlayerDashboard，取前 8 球员"""
        try:
            data = TeamPlayerDashboard(
                team_id=team_id,
                season=season,
                timeout=self._timeout,
                proxy=self._proxy,
            ).get_normalized_dict()
            rows = data.get('PlayersSeasonTotals', [])
            # 按分钟排序取前 8
            rows.sort(key=lambda r: r.get('MIN', 0), reverse=True)
            players = []
            for row in rows[:8]:
                players.append({
                    'name': row.get('PLAYER_NAME', ''),
                    'gp': row.get('GP', 0),
                    'min': round(row.get('MIN', 0), 1),
                    'ppg': round(row.get('PTS', 0), 1),
                    'rpg': round(row.get('REB', 0), 1),
                    'apg': round(row.get('AST', 0), 1),
                    'fg_pct': row.get('FG_PCT'),
                    'fg3_pct': row.get('FG3_PCT'),
                })
            return players if players else None
        except Exception as e:
            logger.warning(f"拉取球员数据失败 (team_id={team_id}): {e}")
            return None

    def _fetch_recent_games(self, team_id: int, season: str, last_n: int = 10) -> Optional[List[dict]]:
        """TeamGameLog，近 N 场"""
        try:
            data = TeamGameLog(
                team_id=team_id,
                season=season,
                timeout=self._timeout,
                proxy=self._proxy,
            ).get_normalized_dict()
            rows = data.get('TeamGameLog', [])
            games = []
            for row in rows[:last_n]:
                games.append({
                    'date': row.get('GAME_DATE', ''),
                    'matchup': row.get('MATCHUP', ''),
                    'result': row.get('WL', ''),
                    'pts': row.get('PTS', 0),
                    'opp_pts': row.get('PTS', 0),  # 对手得分需从 PLUS_MINUS 推算
                    'plus_minus': row.get('PLUS_MINUS', 0),
                    'reb': row.get('REB', 0),
                    'ast': row.get('AST', 0),
                    'fg_pct': row.get('FG_PCT'),
                })
            return games if games else None
        except Exception as e:
            logger.warning(f"拉取近期比赛失败 (team_id={team_id}): {e}")
            return None

    # ------------------------------------------------------------------
    # 比赛结果查询
    # ------------------------------------------------------------------

    def fetch_game_result(self, home_abbr: str, away_abbr: str, game_date: str) -> Optional[dict]:
        """
        查询指定日期比赛的状态和比分。
        使用 ScoreboardV3 获取当日所有比赛，按主客队 tricode 匹配。
        返回结构化 dict，未找到返回 None。
        """
        try:
            board = scoreboardv3.ScoreboardV3(
                game_date=game_date,
                timeout=self._timeout,
                proxy=self._proxy,
            )
            data = board.get_dict()
            games = data.get('scoreboard', {}).get('games', [])

            home_upper = home_abbr.upper()
            away_upper = away_abbr.upper()

            for g in games:
                ht = g.get('homeTeam', {})
                at = g.get('awayTeam', {})
                if ht.get('teamTricode') == home_upper and at.get('teamTricode') == away_upper:
                    game_status_id = g.get('gameStatus')
                    game_status_text = (g.get('gameStatusText') or '').strip()
                    home_score = ht.get('score')
                    away_score = at.get('score')

                    return {
                        'game_status_id': game_status_id,
                        'game_status_text': game_status_text or (
                            'Final' if game_status_id == 3
                            else 'In Progress' if game_status_id == 2
                            else 'Not Started'
                        ),
                        'home_score': home_score,
                        'away_score': away_score,
                        'home_abbr': home_upper,
                        'away_abbr': away_upper,
                    }

            logger.info(f"fetch_game_result: 未找到比赛 {away_upper}@{home_upper} on {game_date}")
            return None

        except Exception as e:
            logger.warning(f"fetch_game_result 失败: {e}")
            return None

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------

    def fetch_matchup_data(self, home_abbr: str, away_abbr: str, season: str = None) -> dict:
        """
        拉取双方数据，返回结构化字典。
        任何单个 API 调用失败不中断整体，对应字段返回 None。
        """
        season = season or Config.NBA_API_SEASON or _current_season()
        logger.info(f"开始拉取 NBA 数据: {away_abbr} @ {home_abbr}, season={season}")

        home_id = self._get_team_id(home_abbr)
        away_id = self._get_team_id(away_abbr)

        if home_id is None or away_id is None:
            logger.error(f"无法找到球队: home={home_abbr}({home_id}), away={away_abbr}({away_id})")
            return {
                'home': None, 'away': None,
                'fetch_time': datetime.now().isoformat(), 'season': season,
                'error': f"Unknown team abbreviation: {home_abbr if home_id is None else away_abbr}",
            }

        # 1) 联盟排名（一次 API 拉取所有球队）
        standings_map = self._fetch_standings(season)
        self._sleep()

        def _fetch_team_data(team_id: int) -> dict:
            adv = self._fetch_advanced_stats(team_id, season)
            self._sleep()
            players = self._fetch_players(team_id, season)
            self._sleep()
            games = self._fetch_recent_games(team_id, season)
            return {
                'standings': standings_map.get(team_id),
                'advanced': adv,
                'players': players,
                'recent_games': games,
            }

        # 主客队数据并行拉取
        with ThreadPoolExecutor(max_workers=2) as pool:
            home_future = pool.submit(_fetch_team_data, home_id)
            away_future = pool.submit(_fetch_team_data, away_id)
            home_data = home_future.result()
            away_data = away_future.result()

        result = {
            'home': home_data,
            'away': away_data,
            'fetch_time': datetime.now().isoformat(),
            'season': season,
        }
        logger.info(f"NBA 数据拉取完成: {away_abbr} @ {home_abbr}")
        return result

    # ------------------------------------------------------------------
    # 文本化
    # ------------------------------------------------------------------

    def to_enrichment_text(self, data: dict, home_abbr: str, away_abbr: str) -> str:
        """将结构化数据转为自然语言文本，供注入图谱和辩论引擎使用"""
        parts = [f"=== NBA Stats Data (Season {data.get('season', 'N/A')}) ===\n"]

        for label, abbr, side in [('Home', home_abbr, 'home'), ('Away', away_abbr, 'away')]:
            team_data = data.get(side)
            if not team_data:
                parts.append(f"[{label}] {abbr}: No data available.\n")
                continue

            parts.append(f"--- {label} Team: {abbr} ---")
            self._append_standings_text(parts, team_data.get('standings'), abbr)
            self._append_advanced_text(parts, team_data.get('advanced'), abbr)
            self._append_players_text(parts, team_data.get('players'), abbr)
            self._append_games_text(parts, team_data.get('recent_games'), abbr)
            parts.append("")

        return "\n".join(parts)

    @staticmethod
    def _append_standings_text(parts: list, standings: Optional[dict], abbr: str):
        if not standings:
            return
        w, l = standings.get('wins', '?'), standings.get('losses', '?')
        pct = standings.get('win_pct', 0)
        conf = standings.get('conference', '?')
        rank = standings.get('conference_rank', '?')
        streak = standings.get('streak', '')
        l10 = standings.get('last_10', '')
        parts.append(
            f"{abbr} Record: {w}-{l} ({pct:.3f}), "
            f"{conf} Conference #{rank}. "
            f"Streak: {streak}. Last 10: {l10}."
        )

    @staticmethod
    def _append_advanced_text(parts: list, adv: Optional[dict], abbr: str):
        if not adv:
            return
        off = adv.get('off_rating', '?')
        dfn = adv.get('def_rating', '?')
        net = adv.get('net_rating', '?')
        pace = adv.get('pace', '?')
        parts.append(
            f"{abbr} Advanced: OffRtg {off}, DefRtg {dfn}, "
            f"NetRtg {net}, Pace {pace}."
        )

    @staticmethod
    def _append_players_text(parts: list, players: Optional[List[dict]], abbr: str):
        if not players:
            return
        parts.append(f"{abbr} Key Players:")
        for p in players:
            name = p.get('name', '?')
            ppg = p.get('ppg', 0)
            rpg = p.get('rpg', 0)
            apg = p.get('apg', 0)
            parts.append(f"  - {name}: {ppg} PPG, {rpg} RPG, {apg} APG")

    @staticmethod
    def _append_games_text(parts: list, games: Optional[List[dict]], abbr: str):
        if not games:
            return
        parts.append(f"{abbr} Recent Games:")
        for g in games:
            date = g.get('date', '?')
            matchup = g.get('matchup', '?')
            result = g.get('result', '?')
            pts = g.get('pts', '?')
            pm = g.get('plus_minus', 0)
            sign = '+' if pm >= 0 else ''
            parts.append(f"  - {date}: {matchup} {result} ({pts} pts, {sign}{pm})")
