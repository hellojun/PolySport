"""
NBA 数据拉取服务 — cdn.nba.com 版
使用免费 CDN 端点获取赛程、boxscore、球员统计和伤病报告。
替代旧版 stats.nba.com (nba_api) 方案，解决云服务器 IP 被封问题。
"""

import json
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

import requests

from ...config import Config
from ...utils.logger import get_logger

logger = get_logger('mirofish.data_fetcher.nba_stats')

# ── CDN 端点 ──
_CDN_SCHEDULE_URL = 'https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json'
_CDN_SCOREBOARD_URL = 'https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json'
_CDN_BOXSCORE_URL = 'https://cdn.nba.com/static/json/liveData/boxscore/boxscore_{game_id}.json'

# ── Redis 缓存 key 前缀 ──
_CACHE_SCHEDULE = 'nba:cdn:schedule'
_CACHE_BOXSCORE = 'nba:cdn:boxscore:{game_id}'

# ── 30 队 → 分区映射 ──
_TEAM_CONFERENCE: Dict[str, str] = {
    # Eastern
    'ATL': 'East', 'BOS': 'East', 'BKN': 'East', 'CHA': 'East', 'CHI': 'East',
    'CLE': 'East', 'DET': 'East', 'IND': 'East', 'MIA': 'East', 'MIL': 'East',
    'NYK': 'East', 'ORL': 'East', 'PHI': 'East', 'TOR': 'East', 'WAS': 'East',
    # Western
    'DAL': 'West', 'DEN': 'West', 'GSW': 'West', 'HOU': 'West', 'LAC': 'West',
    'LAL': 'West', 'MEM': 'West', 'MIN': 'West', 'NOP': 'West', 'OKC': 'West',
    'PHX': 'West', 'POR': 'West', 'SAC': 'West', 'SAS': 'West', 'UTA': 'West',
}

# ── 缩写 → 全名映射（纯本地数据，不走网络） ──
_TEAM_FULLNAME: Dict[str, str] = {
    'ATL': 'Atlanta Hawks', 'BOS': 'Boston Celtics', 'BKN': 'Brooklyn Nets',
    'CHA': 'Charlotte Hornets', 'CHI': 'Chicago Bulls', 'CLE': 'Cleveland Cavaliers',
    'DAL': 'Dallas Mavericks', 'DEN': 'Denver Nuggets', 'DET': 'Detroit Pistons',
    'GSW': 'Golden State Warriors', 'HOU': 'Houston Rockets', 'IND': 'Indiana Pacers',
    'LAC': 'LA Clippers', 'LAL': 'Los Angeles Lakers', 'MEM': 'Memphis Grizzlies',
    'MIA': 'Miami Heat', 'MIL': 'Milwaukee Bucks', 'MIN': 'Minnesota Timberwolves',
    'NOP': 'New Orleans Pelicans', 'NYK': 'New York Knicks', 'OKC': 'Oklahoma City Thunder',
    'ORL': 'Orlando Magic', 'PHI': 'Philadelphia 76ers', 'PHX': 'Phoenix Suns',
    'POR': 'Portland Trail Blazers', 'SAC': 'Sacramento Kings', 'SAS': 'San Antonio Spurs',
    'TOR': 'Toronto Raptors', 'UTA': 'Utah Jazz', 'WAS': 'Washington Wizards',
}


def _current_season() -> str:
    """推断当前 NBA 赛季字符串，如 '2025-26'"""
    now = datetime.now()
    year = now.year if now.month >= 10 else now.year - 1
    return f"{year}-{str(year + 1)[-2:]}"


# ── 通用工具函数 ──

def _cdn_get(url: str, timeout: int = None) -> Optional[dict]:
    """统一 CDN GET 请求，返回 JSON dict 或 None"""
    timeout = timeout or Config.NBA_CDN_REQUEST_TIMEOUT
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
                       '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Referer': 'https://www.nba.com/',
        'Accept': 'application/json',
    }
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        logger.warning(f"CDN GET 失败 ({url}): {e}")
        return None


def _cache_get(key: str) -> Optional[Any]:
    """Redis JSON 缓存读取，失败返回 None"""
    try:
        from ...utils.redis_client import get_redis
        r = get_redis()
        raw = r.get(key)
        if raw:
            return json.loads(raw)
    except Exception as e:
        logger.debug(f"Redis cache get 失败 ({key}): {e}")
    return None


def _cache_set(key: str, data: Any, ttl: int):
    """Redis JSON 缓存写入"""
    try:
        from ...utils.redis_client import get_redis
        r = get_redis()
        r.set(key, json.dumps(data, ensure_ascii=False), ex=ttl)
    except Exception as e:
        logger.debug(f"Redis cache set 失败 ({key}): {e}")


def _parse_minutes(iso_duration: str) -> float:
    """
    解析 ISO 8601 duration 或 CDN 分钟格式 → 浮点分钟数
    'PT32M15.00S' → 32.25
    'PT05M' → 5.0
    '32:15' → 32.25
    """
    if not iso_duration:
        return 0.0
    s = str(iso_duration).strip()
    # ISO: PT32M15.00S
    m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:([\d.]+)S)?', s)
    if m:
        hours = int(m.group(1) or 0)
        mins = int(m.group(2) or 0)
        secs = float(m.group(3) or 0)
        return hours * 60 + mins + round(secs / 60, 2)
    # mm:ss
    m2 = re.match(r'(\d+):(\d+)', s)
    if m2:
        return int(m2.group(1)) + round(int(m2.group(2)) / 60, 2)
    return 0.0


class NBAStatsService:
    """从 cdn.nba.com 拉取球队和球员数据"""

    def __init__(self):
        self._timeout = Config.NBA_CDN_REQUEST_TIMEOUT
        self._boxscore_count = Config.NBA_CDN_BOXSCORE_COUNT

    # ------------------------------------------------------------------
    # 赛程 (schedule)
    # ------------------------------------------------------------------

    def _fetch_schedule(self) -> Optional[dict]:
        """获取 scheduleLeagueV2.json（Redis 缓存）"""
        cached = _cache_get(_CACHE_SCHEDULE)
        if cached:
            return cached
        data = _cdn_get(_CDN_SCHEDULE_URL, timeout=self._timeout)
        if data:
            _cache_set(_CACHE_SCHEDULE, data, Config.NBA_CDN_SCHEDULE_TTL)
        return data

    def _parse_team_games(self, schedule: dict, tricode: str) -> List[dict]:
        """
        从赛程提取指定球队已完成的常规赛比赛，按日期降序。
        返回列表中每项包含完整 game 对象。
        """
        tricode = tricode.upper()
        games = []
        game_dates = schedule.get('leagueSchedule', {}).get('gameDates', [])
        for gd in game_dates:
            for g in gd.get('games', []):
                # 只取已结束的比赛 (gameStatus=3)
                if g.get('gameStatus') != 3:
                    continue
                # 跳过季前赛和全明星 — 只取常规赛(gameSubtype 为空)
                if g.get('gameSubtype'):
                    continue
                ht = g.get('homeTeam', {})
                at = g.get('awayTeam', {})
                if ht.get('teamTricode') == tricode or at.get('teamTricode') == tricode:
                    games.append(g)
        # 按 gameDateTimeUTC 降序排列
        games.sort(key=lambda x: x.get('gameDateTimeUTC', ''), reverse=True)
        return games

    def _build_all_team_records(self, schedule: dict) -> Dict[str, dict]:
        """
        遍历赛程获取全部 30 队最新 W/L。
        赛程中每场比赛的 homeTeam/awayTeam 包含累积 wins/losses。
        我们取每队最后一场已完成比赛的 wins/losses。
        """
        records: Dict[str, dict] = {}
        game_dates = schedule.get('leagueSchedule', {}).get('gameDates', [])
        for gd in game_dates:
            for g in gd.get('games', []):
                if g.get('gameStatus') != 3:
                    continue
                if g.get('gameSubtype'):
                    continue
                for side in ('homeTeam', 'awayTeam'):
                    t = g.get(side, {})
                    tc = t.get('teamTricode', '')
                    if tc:
                        records[tc] = {
                            'wins': t.get('wins', 0),
                            'losses': t.get('losses', 0),
                        }
        return records

    def _derive_standings(self, team_games: List[dict], tricode: str,
                          all_records: Dict[str, dict]) -> Optional[dict]:
        """派生战绩：W/L/win_pct/conference/rank/streak/last_10"""
        tricode = tricode.upper()
        rec = all_records.get(tricode)
        if not rec:
            return None

        wins = rec['wins']
        losses = rec['losses']
        total = wins + losses
        win_pct = round(wins / total, 3) if total > 0 else 0.0

        conference = _TEAM_CONFERENCE.get(tricode, '?')

        # 计算联盟排名：同分区按 win_pct 排序
        conf_teams = []
        for tc, r in all_records.items():
            if _TEAM_CONFERENCE.get(tc) == conference:
                t_total = r['wins'] + r['losses']
                t_pct = round(r['wins'] / t_total, 3) if t_total > 0 else 0.0
                conf_teams.append((tc, t_pct, r['wins']))
        conf_teams.sort(key=lambda x: (x[1], x[2]), reverse=True)
        rank = 1
        for i, (tc, _, _) in enumerate(conf_teams):
            if tc == tricode:
                rank = i + 1
                break

        # streak: 从最近比赛往回计算
        streak = ''
        if team_games:
            streak_type = None
            streak_count = 0
            for g in team_games:
                ht = g.get('homeTeam', {})
                at = g.get('awayTeam', {})
                if ht.get('teamTricode') == tricode:
                    won = (ht.get('score', 0) or 0) > (at.get('score', 0) or 0)
                else:
                    won = (at.get('score', 0) or 0) > (ht.get('score', 0) or 0)
                wl = 'W' if won else 'L'
                if streak_type is None:
                    streak_type = wl
                    streak_count = 1
                elif wl == streak_type:
                    streak_count += 1
                else:
                    break
            streak = f"{streak_type}{streak_count}" if streak_type else ''

        # last_10
        last_10_w = 0
        for g in team_games[:10]:
            ht = g.get('homeTeam', {})
            at = g.get('awayTeam', {})
            if ht.get('teamTricode') == tricode:
                if (ht.get('score', 0) or 0) > (at.get('score', 0) or 0):
                    last_10_w += 1
            else:
                if (at.get('score', 0) or 0) > (ht.get('score', 0) or 0):
                    last_10_w += 1
        last_10_games = min(len(team_games), 10)
        last_10 = f"{last_10_w}-{last_10_games - last_10_w}"

        return {
            'wins': wins,
            'losses': losses,
            'win_pct': win_pct,
            'conference': conference,
            'conference_rank': rank,
            'streak': streak,
            'last_10': last_10,
        }

    # ------------------------------------------------------------------
    # Boxscore
    # ------------------------------------------------------------------

    def _fetch_boxscore(self, game_id: str) -> Optional[dict]:
        """获取单场 boxscore（Redis 缓存）"""
        cache_key = _CACHE_BOXSCORE.format(game_id=game_id)
        cached = _cache_get(cache_key)
        if cached:
            return cached
        url = _CDN_BOXSCORE_URL.format(game_id=game_id)
        data = _cdn_get(url, timeout=self._timeout)
        if data:
            _cache_set(cache_key, data, Config.NBA_CDN_BOXSCORE_TTL)
        return data

    def _derive_players_from_boxscores(self, game_ids: List[str], tricode: str) -> Optional[List[dict]]:
        """
        并行拉取 N 场 boxscore，聚合球员场均数据（前 8 名按分钟排序）。
        """
        tricode = tricode.upper()
        if not game_ids:
            return None

        # 并行拉取 boxscores
        boxscores = []
        with ThreadPoolExecutor(max_workers=min(len(game_ids), 5)) as pool:
            futures = {pool.submit(self._fetch_boxscore, gid): gid for gid in game_ids}
            for future in as_completed(futures):
                try:
                    bs = future.result()
                    if bs:
                        boxscores.append(bs)
                except Exception as e:
                    logger.debug(f"Boxscore 拉取异常: {e}")

        if not boxscores:
            return None

        # 聚合球员数据
        player_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            'name': '', 'gp': 0, 'total_min': 0.0, 'total_pts': 0, 'total_reb': 0,
            'total_ast': 0, 'total_fgm': 0, 'total_fga': 0,
            'total_fg3m': 0, 'total_fg3a': 0,
        })

        for bs in boxscores:
            game = bs.get('game', {})
            for side in ('homeTeam', 'awayTeam'):
                team = game.get(side, {})
                if team.get('teamTricode') != tricode:
                    continue
                for p in team.get('players', []):
                    if p.get('status') != 'ACTIVE' or not p.get('played', ''):
                        continue
                    name = p.get('name', '') or f"{p.get('firstName', '')} {p.get('familyName', '')}".strip()
                    if not name:
                        continue
                    stats = p.get('statistics', {})
                    ps = player_stats[name]
                    ps['name'] = name
                    ps['gp'] += 1
                    ps['total_min'] += _parse_minutes(stats.get('minutesCalculated', '') or stats.get('minutes', ''))
                    ps['total_pts'] += stats.get('points', 0) or 0
                    ps['total_reb'] += stats.get('reboundsTotal', 0) or 0
                    ps['total_ast'] += stats.get('assists', 0) or 0
                    ps['total_fgm'] += stats.get('fieldGoalsMade', 0) or 0
                    ps['total_fga'] += stats.get('fieldGoalsAttempted', 0) or 0
                    ps['total_fg3m'] += stats.get('threePointersMade', 0) or 0
                    ps['total_fg3a'] += stats.get('threePointersAttempted', 0) or 0

        # 计算场均并排序
        players = []
        for ps in player_stats.values():
            gp = ps['gp']
            if gp == 0:
                continue
            avg_min = round(ps['total_min'] / gp, 1)
            players.append({
                'name': ps['name'],
                'gp': gp,
                'min': avg_min,
                'ppg': round(ps['total_pts'] / gp, 1),
                'rpg': round(ps['total_reb'] / gp, 1),
                'apg': round(ps['total_ast'] / gp, 1),
                'fg_pct': round(ps['total_fgm'] / ps['total_fga'], 3) if ps['total_fga'] > 0 else None,
                'fg3_pct': round(ps['total_fg3m'] / ps['total_fg3a'], 3) if ps['total_fg3a'] > 0 else None,
            })

        players.sort(key=lambda x: x['min'], reverse=True)
        return players[:8] if players else None

    def _derive_injuries(self, game_id: str, tricode: str) -> Optional[List[dict]]:
        """从最近 boxscore 提取伤病/缺阵球员"""
        tricode = tricode.upper()
        bs = self._fetch_boxscore(game_id)
        if not bs:
            return None

        game = bs.get('game', {})
        injuries = []
        for side in ('homeTeam', 'awayTeam'):
            team = game.get(side, {})
            if team.get('teamTricode') != tricode:
                continue
            for p in team.get('players', []):
                reason = p.get('notPlayingReason', '')
                if not reason:
                    continue
                name = p.get('name', '') or f"{p.get('firstName', '')} {p.get('familyName', '')}".strip()
                injuries.append({
                    'name': name,
                    'reason': reason,
                    'description': p.get('notPlayingDescription', '') or '',
                })
        return injuries if injuries else None

    def _derive_recent_games(self, team_games: List[dict], tricode: str,
                             last_n: int = 10) -> Optional[List[dict]]:
        """格式化近 N 场比赛结果"""
        tricode = tricode.upper()
        games = []
        for g in team_games[:last_n]:
            ht = g.get('homeTeam', {})
            at = g.get('awayTeam', {})
            is_home = ht.get('teamTricode') == tricode

            if is_home:
                pts = ht.get('score', 0) or 0
                opp_pts = at.get('score', 0) or 0
                opp_tc = at.get('teamTricode', '?')
                matchup = f"{tricode} vs. {opp_tc}"
            else:
                pts = at.get('score', 0) or 0
                opp_pts = ht.get('score', 0) or 0
                opp_tc = ht.get('teamTricode', '?')
                matchup = f"{tricode} @ {opp_tc}"

            won = pts > opp_pts
            plus_minus = pts - opp_pts

            # 解析日期
            date_str = g.get('gameDateEst', '') or g.get('gameDateTimeUTC', '')
            if date_str:
                try:
                    date_str = date_str[:10]
                except Exception:
                    pass

            games.append({
                'date': date_str,
                'matchup': matchup,
                'result': 'W' if won else 'L',
                'pts': pts,
                'opp_pts': opp_pts,
                'plus_minus': plus_minus,
            })
        return games if games else None

    # ------------------------------------------------------------------
    # 比赛结果查询
    # ------------------------------------------------------------------

    def fetch_game_result(self, home_abbr: str, away_abbr: str, game_date: str) -> Optional[dict]:
        """
        查询指定日期比赛的状态和比分。
        今日比赛用 todaysScoreboard，历史比赛用 schedule。
        """
        home_upper = home_abbr.upper()
        away_upper = away_abbr.upper()
        today = datetime.now().strftime('%Y-%m-%d')

        if game_date == today:
            return self._fetch_game_result_scoreboard(home_upper, away_upper)

        return self._fetch_game_result_schedule(home_upper, away_upper, game_date)

    def _fetch_game_result_scoreboard(self, home_abbr: str, away_abbr: str) -> Optional[dict]:
        """从今日 scoreboard 获取比赛结果"""
        data = _cdn_get(_CDN_SCOREBOARD_URL, timeout=self._timeout)
        if not data:
            return None

        games = data.get('scoreboard', {}).get('games', [])
        for g in games:
            ht = g.get('homeTeam', {})
            at = g.get('awayTeam', {})
            if ht.get('teamTricode') == home_abbr and at.get('teamTricode') == away_abbr:
                game_status_id = g.get('gameStatus')
                game_status_text = (g.get('gameStatusText') or '').strip()

                return {
                    'game_status_id': game_status_id,
                    'game_status_text': game_status_text or (
                        'Final' if game_status_id == 3
                        else 'In Progress' if game_status_id == 2
                        else 'Not Started'
                    ),
                    'home_score': ht.get('score'),
                    'away_score': at.get('score'),
                    'home_abbr': home_abbr,
                    'away_abbr': away_abbr,
                }

        logger.info(f"fetch_game_result: scoreboard 未找到 {away_abbr}@{home_abbr}")
        return None

    def _fetch_game_result_schedule(self, home_abbr: str, away_abbr: str,
                                    game_date: str) -> Optional[dict]:
        """从 schedule 获取历史比赛结果"""
        schedule = self._fetch_schedule()
        if not schedule:
            return None

        game_dates = schedule.get('leagueSchedule', {}).get('gameDates', [])
        for gd in game_dates:
            for g in gd.get('games', []):
                ht = g.get('homeTeam', {})
                at = g.get('awayTeam', {})
                if ht.get('teamTricode') != home_abbr or at.get('teamTricode') != away_abbr:
                    continue
                # 匹配日期
                g_date = (g.get('gameDateEst', '') or '')[:10]
                if g_date != game_date:
                    continue

                game_status = g.get('gameStatus')
                return {
                    'game_status_id': game_status,
                    'game_status_text': (
                        'Final' if game_status == 3
                        else 'In Progress' if game_status == 2
                        else 'Not Started'
                    ),
                    'home_score': ht.get('score'),
                    'away_score': at.get('score'),
                    'home_abbr': home_abbr,
                    'away_abbr': away_abbr,
                }

        logger.info(f"fetch_game_result: schedule 未找到 {away_abbr}@{home_abbr} on {game_date}")
        return None

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------

    def fetch_matchup_data(self, home_abbr: str, away_abbr: str, season: str = None) -> dict:
        """
        拉取双方数据，返回结构化字典。
        任何单个步骤失败不中断整体，对应字段返回 None。
        """
        season = season or Config.NBA_API_SEASON or _current_season()
        home_abbr = home_abbr.upper()
        away_abbr = away_abbr.upper()
        logger.info(f"开始拉取 NBA CDN 数据: {away_abbr} @ {home_abbr}, season={season}")

        # 验证球队缩写
        if home_abbr not in _TEAM_CONFERENCE or away_abbr not in _TEAM_CONFERENCE:
            unknown = home_abbr if home_abbr not in _TEAM_CONFERENCE else away_abbr
            logger.error(f"未知球队缩写: {unknown}")
            return {
                'home': None, 'away': None,
                'fetch_time': datetime.now().isoformat(), 'season': season,
                'error': f"Unknown team abbreviation: {unknown}",
            }

        # 1) 获取赛程
        schedule = self._fetch_schedule()
        if not schedule:
            logger.error("无法获取 NBA 赛程数据")
            return {
                'home': None, 'away': None,
                'fetch_time': datetime.now().isoformat(), 'season': season,
                'error': 'Failed to fetch NBA schedule from CDN',
            }

        # 2) 构建全队战绩
        all_records = self._build_all_team_records(schedule)

        def _fetch_team_data(abbr: str) -> dict:
            team_games = self._parse_team_games(schedule, abbr)
            standings = self._derive_standings(team_games, abbr, all_records)

            # 取最近 N 场的 gameId 用于 boxscore
            recent_game_ids = [g.get('gameId') for g in team_games[:self._boxscore_count]
                               if g.get('gameId')]

            players = self._derive_players_from_boxscores(recent_game_ids, abbr)

            # 伤病：从最近一场 boxscore 提取
            injuries = None
            if recent_game_ids:
                injuries = self._derive_injuries(recent_game_ids[0], abbr)

            recent_games = self._derive_recent_games(team_games, abbr, last_n=10)

            return {
                'standings': standings,
                'advanced': None,  # CDN 不提供高级统计
                'players': players,
                'recent_games': recent_games,
                'injuries': injuries,
            }

        # 主客队数据并行拉取
        with ThreadPoolExecutor(max_workers=2) as pool:
            home_future = pool.submit(_fetch_team_data, home_abbr)
            away_future = pool.submit(_fetch_team_data, away_abbr)
            home_data = home_future.result()
            away_data = away_future.result()

        result = {
            'home': home_data,
            'away': away_data,
            'fetch_time': datetime.now().isoformat(),
            'season': season,
        }
        logger.info(f"NBA CDN 数据拉取完成: {away_abbr} @ {home_abbr}")
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
            self._append_injuries_text(parts, team_data.get('injuries'), abbr)
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

    @staticmethod
    def _append_injuries_text(parts: list, injuries: Optional[List[dict]], abbr: str):
        if not injuries:
            return
        parts.append(f"{abbr} Injury Report:")
        for inj in injuries:
            name = inj.get('name', '?')
            reason = inj.get('reason', '?')
            desc = inj.get('description', '')
            line = f"  - {name}: {reason}"
            if desc:
                line += f" ({desc})"
            parts.append(line)
