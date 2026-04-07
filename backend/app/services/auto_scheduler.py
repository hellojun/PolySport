"""
自动预测调度器
- 每天美东 08:00 拉取当日赛程，为每场比赛在开赛前 N 分钟注册一次性预测任务
- 每天美东 14:00 自动回填昨日比赛结果
"""

import threading
import time as _time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger('mirofish.auto_scheduler')

ET = ZoneInfo('America/New_York')


class AutoPredictionScheduler:
    """每日自动预测 + 结果回填调度器"""

    def __init__(self, app):
        self.app = app
        self._scheduler = BackgroundScheduler(daemon=True)
        self._scheduled_games: set = set()  # 防重复调度
        self._semaphore = threading.Semaphore(Config.AUTO_PREDICT_MAX_CONCURRENT)

    def start(self):
        """启动调度器，注册 cron 任务并立即执行一次赛程拉取"""
        schedule_hour = Config.AUTO_PREDICT_SCHEDULE_HOUR
        backfill_hour = Config.AUTO_BACKFILL_HOUR

        # 每天美东 schedule_hour:00 拉取当日赛程
        self._scheduler.add_job(
            self._daily_schedule_fetch,
            CronTrigger(hour=schedule_hour, minute=0, timezone=ET),
            id='daily_schedule_fetch',
            replace_existing=True,
        )

        # 每天美东 backfill_hour:00 回填昨日结果
        if Config.AUTO_BACKFILL_ENABLED:
            self._scheduler.add_job(
                self._daily_backfill,
                CronTrigger(hour=backfill_hour, minute=0, timezone=ET),
                id='daily_backfill',
                replace_existing=True,
            )

        self._scheduler.start()
        logger.info(f"AutoPredictionScheduler 启动: 赛程@{schedule_hour}:00ET, 回填@{backfill_hour}:00ET")

        # 启动时立即执行一次（处理今天剩余比赛）
        threading.Thread(target=self._daily_schedule_fetch, daemon=True).start()

    # ------------------------------------------------------------------
    # 赛程拉取 & 调度预测
    # ------------------------------------------------------------------

    def _daily_schedule_fetch(self):
        """拉取今日赛程，为每场比赛注册预测任务"""
        try:
            with self.app.app_context():
                games = self._get_today_games()
                if not games:
                    logger.info("今日无 NBA 比赛")
                    return
                logger.info(f"今日 {len(games)} 场 NBA 比赛")
                for game in games:
                    self._schedule_game_prediction(game)
        except Exception as e:
            logger.error(f"每日赛程拉取失败: {e}", exc_info=True)

    def _get_today_games(self) -> list:
        """从 CDN schedule 获取今日比赛列表"""
        from .data_fetcher.nba_stats import NBAStatsService

        today_et = datetime.now(ET).strftime('%Y-%m-%d')
        nba = NBAStatsService()
        schedule = nba._fetch_schedule()
        if not schedule:
            logger.warning("无法获取 NBA 赛程数据")
            return []

        games = []
        game_dates = schedule.get('leagueSchedule', {}).get('gameDates', [])
        for gd in game_dates:
            for g in gd.get('games', []):
                g_date = (g.get('gameDateEst', '') or '')[:10]
                if g_date != today_et:
                    continue
                # 跳过季前赛/全明星
                if g.get('gameSubtype'):
                    continue
                ht = g.get('homeTeam', {})
                at = g.get('awayTeam', {})
                home_abbr = ht.get('teamTricode', '')
                away_abbr = at.get('teamTricode', '')
                game_time_utc = g.get('gameDateTimeUTC', '')
                game_id = g.get('gameId', '')

                if home_abbr and away_abbr and game_time_utc:
                    games.append({
                        'home_abbr': home_abbr,
                        'away_abbr': away_abbr,
                        'game_date': g_date,
                        'game_time_utc': game_time_utc,
                        'game_id': game_id,
                        'game_status': g.get('gameStatus', 1),
                    })
        return games

    def _schedule_game_prediction(self, game: dict):
        """为单场比赛注册一次性预测任务"""
        game_key = f"{game['away_abbr']}@{game['home_abbr']}_{game['game_date']}"
        if game_key in self._scheduled_games:
            return

        # 已开始的比赛跳过
        if game.get('game_status', 1) >= 2:
            logger.info(f"跳过已开始的比赛: {game_key}")
            return

        # 计算触发时间 = 开赛 - N 分钟
        try:
            game_time = datetime.fromisoformat(game['game_time_utc'].replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            logger.warning(f"无法解析比赛时间: {game['game_time_utc']}, 跳过 {game_key}")
            return

        trigger_time = game_time - timedelta(minutes=Config.AUTO_PREDICT_MINUTES_BEFORE)
        now_utc = datetime.now(game_time.tzinfo or ZoneInfo('UTC'))

        if trigger_time <= now_utc:
            # 触发时间已过但比赛未开始 → 立即执行
            if game_time > now_utc:
                logger.info(f"触发时间已过但比赛未开始，立即执行: {game_key}")
                self._scheduled_games.add(game_key)
                threading.Thread(
                    target=self._run_auto_prediction,
                    args=(game,),
                    daemon=True,
                ).start()
            else:
                logger.info(f"比赛时间已过，跳过: {game_key}")
            return

        # 注册 DateTrigger 一次性任务
        self._scheduled_games.add(game_key)
        self._scheduler.add_job(
            self._run_auto_prediction,
            DateTrigger(run_date=trigger_time),
            args=[game],
            id=f'auto_pred_{game_key}',
            replace_existing=True,
        )
        trigger_et = trigger_time.astimezone(ET).strftime('%H:%M ET')
        logger.info(f"已调度: {game_key} → {trigger_et}")

    # ------------------------------------------------------------------
    # 执行预测
    # ------------------------------------------------------------------

    def _run_auto_prediction(self, game: dict, retry: int = 0):
        """通过信号量控制并发执行预测，失败重试"""
        self._semaphore.acquire()
        try:
            with self.app.app_context():
                self._execute_prediction(game)
        except Exception as e:
            game_key = f"{game['away_abbr']}@{game['home_abbr']}_{game['game_date']}"
            logger.error(f"自动预测失败 ({game_key}): {e}", exc_info=True)
            if retry < 2:
                logger.info(f"2 分钟后重试 ({retry + 1}/2): {game_key}")
                self._scheduler.add_job(
                    self._run_auto_prediction,
                    DateTrigger(run_date=datetime.now(ZoneInfo('UTC')) + timedelta(minutes=2)),
                    args=[game, retry + 1],
                    id=f'auto_retry_{game_key}_{retry + 1}',
                    replace_existing=True,
                )
        finally:
            self._semaphore.release()

    def _execute_prediction(self, game: dict):
        """核心执行流程：拉盘口 → 构建输入 → 调用 worker"""
        from ..models.prediction import Prediction
        from ..models.user import User
        from ..models.matchup import MatchupInput, TeamInfo, MarketOdds
        from ..models.task import TaskManager
        from ..api.prediction import _prediction_worker

        home_abbr = game['home_abbr']
        away_abbr = game['away_abbr']
        game_date = game['game_date']
        matchup_id = f"auto_{away_abbr}_{home_abbr}_{game_date}"

        # 防重复
        existing = Prediction.query.filter_by(matchup_id=matchup_id).first()
        if existing:
            logger.info(f"已存在预测 {matchup_id}，跳过")
            return

        # 获取系统用户
        system_user = User.query.filter_by(email=Config.SYSTEM_USER_EMAIL).first()
        if not system_user:
            logger.error(f"系统用户 {Config.SYSTEM_USER_EMAIL} 不存在")
            return

        # 拉取盘口
        market_odds = None
        condition_id = None
        token_ids = None
        try:
            from .data_fetcher.polymarket import PolymarketService
            events = PolymarketService().fetch_nba_events(game_date)
            for ev in events:
                if (ev.get('home_team', {}).get('abbreviation') == home_abbr
                        and ev.get('away_team', {}).get('abbreviation') == away_abbr):
                    odds = ev.get('market_odds', {})
                    market_odds = MarketOdds(
                        moneyline_home=odds.get('moneyline_home'),
                        moneyline_away=odds.get('moneyline_away'),
                        spread_line=odds.get('spread_line'),
                        spread_home=odds.get('spread_home'),
                        spread_away=odds.get('spread_away'),
                        total_line=odds.get('total_line'),
                        total_over=odds.get('total_over'),
                        total_under=odds.get('total_under'),
                        volume=odds.get('volume'),
                    )
                    condition_id = ev.get('condition_id')
                    token_ids = ev.get('token_ids')
                    break
        except Exception as e:
            logger.warning(f"拉取盘口失败 ({matchup_id}): {e}")

        # 构建 MatchupInput
        matchup = MatchupInput(
            matchup_id=matchup_id,
            home_team=TeamInfo(name=home_abbr, abbreviation=home_abbr),
            away_team=TeamInfo(name=away_abbr, abbreviation=away_abbr),
            market_odds=market_odds,
            game_date=game_date,
            source='auto',
            condition_id=condition_id,
            token_ids=token_ids,
        )

        # 创建任务
        task_manager = TaskManager()
        task_manager.set_app(self.app)
        task_id = task_manager.create_task(
            task_type="prediction",
            metadata={
                "matchup_id": matchup_id,
                "home": home_abbr,
                "away": away_abbr,
                "game_date": game_date,
                "game_time": game.get('game_time_utc', ''),
                "lang": Config.AUTO_PREDICT_LANG,
                "user_id": system_user.id,
                "source": "auto",
            },
            user_id=system_user.id,
        )

        logger.info(f"开始自动预测: {matchup_id}, task={task_id}")

        # 直接调用 worker（当前已在线程中，cost=0 不扣费）
        _prediction_worker(
            self.app, task_id, matchup,
            lang=Config.AUTO_PREDICT_LANG,
            fast_mode=False,
            debate_rounds=Config.DEBATE_NUM_ROUNDS,
            use_graph=True,
            use_smart_money=True,
            user_id=system_user.id,
            cost=0,
        )
        logger.info(f"自动预测完成: {matchup_id}")

    # ------------------------------------------------------------------
    # 自动回填
    # ------------------------------------------------------------------

    def _daily_backfill(self):
        """回填昨日及更早的自动预测结果"""
        try:
            with self.app.app_context():
                self._do_backfill()
        except Exception as e:
            logger.error(f"自动回填失败: {e}", exc_info=True)

    def _do_backfill(self):
        """扫描缺 game_result 的自动预测，拉取比分并计算命中"""
        import json
        from sqlalchemy.orm.attributes import flag_modified
        from ..extensions import db
        from ..models.prediction import Prediction
        from ..utils.hit_calculator import compute_hit_status
        from ..utils.redis_client import get_redis

        now = datetime.utcnow()
        cutoff = now - timedelta(hours=24)

        rows = Prediction.query.filter(
            Prediction.matchup_id.startswith('auto_')
        ).all()

        candidates = []
        for pred in rows:
            data = pred.data or {}
            mm = data.get('matchup_meta')
            if not mm:
                continue
            game_date = mm.get('game_date')
            if not game_date:
                continue
            try:
                gd = datetime.strptime(game_date, '%Y-%m-%d')
            except ValueError:
                continue
            if gd > cutoff:
                continue
            gr = data.get('game_result')
            if gr and gr.get('game_status_id') == 3 and gr.get('hit_status'):
                continue
            candidates.append((pred, mm, data))

        if not candidates:
            logger.info("自动回填: 无需处理")
            return

        logger.info(f"自动回填: {len(candidates)} 条待处理")

        from .data_fetcher.nba_stats import NBAStatsService
        nba_service = NBAStatsService()
        updated = 0

        for pred, mm, data in candidates:
            home_abbr = mm.get('home')
            away_abbr = mm.get('away')
            game_date = mm.get('game_date')
            if not home_abbr or not away_abbr:
                continue

            try:
                result = nba_service.fetch_game_result(home_abbr, away_abbr, game_date)
            except Exception as e:
                logger.warning(f"回填 API 错误 ({pred.matchup_id}): {e}")
                _time.sleep(Config.NBA_API_DELAY)
                continue

            if not result or result.get('game_status_id') != 3:
                _time.sleep(Config.NBA_API_DELAY)
                continue

            hit_status = compute_hit_status(data, result)
            result['hit_status'] = hit_status
            result['fetched_at'] = datetime.now().isoformat()

            data['game_result'] = result
            pred.data = data
            flag_modified(pred, 'data')
            db.session.add(pred)

            # 更新 Redis
            try:
                r = get_redis()
                key = f"prediction:{pred.matchup_id}"
                r.set(key, json.dumps(data, ensure_ascii=False), ex=Config.PREDICTION_TTL)
            except Exception:
                pass

            updated += 1
            hit_str = f"{hit_status['hit_count']}/{hit_status['total_markets']}"
            logger.info(f"回填: {pred.matchup_id} → {result.get('away_score')}-{result.get('home_score')} 命中 {hit_str}")
            _time.sleep(Config.NBA_API_DELAY)

        db.session.commit()
        logger.info(f"自动回填完成: 更新 {updated} 条")

    # ------------------------------------------------------------------
    # 状态查询
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        """返回调度器状态"""
        jobs = self._scheduler.get_jobs()
        pending = [
            {
                'id': j.id,
                'next_run': j.next_run_time.isoformat() if j.next_run_time else None,
            }
            for j in jobs
        ]
        return {
            'running': self._scheduler.running,
            'scheduled_games': len(self._scheduled_games),
            'pending_jobs': pending,
        }
