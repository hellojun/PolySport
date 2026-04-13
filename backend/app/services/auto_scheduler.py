"""
自动预测调度器
- 每天北京时间 22:00 拉取当日赛程，并行预测所有比赛（最多 5 并发）
- 每天美东 14:00 自动回填昨日比赛结果
- 每 10 分钟检查当日是否有已结束但未回填的比赛，及时更新战绩
"""

import threading
import time as _time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger('mirofish.auto_scheduler')

ET = ZoneInfo('America/New_York')
BJT = ZoneInfo('Asia/Shanghai')


class AutoPredictionScheduler:
    """每日自动预测 + 结果回填调度器"""

    def __init__(self, app):
        self.app = app
        self._scheduler = BackgroundScheduler(daemon=True)
        self._predicted_games: set = set()  # 防重复预测
        self._semaphore = threading.Semaphore(Config.AUTO_PREDICT_MAX_CONCURRENT)

    def start(self):
        """启动调度器，注册 cron 任务"""
        trigger_hour = Config.AUTO_PREDICT_TRIGGER_HOUR_BJT
        backfill_hour = Config.AUTO_BACKFILL_HOUR

        # 每天北京时间 trigger_hour:00 批量预测当日所有比赛
        self._scheduler.add_job(
            self._daily_batch_predict,
            CronTrigger(hour=trigger_hour, minute=0, timezone=BJT),
            id='daily_batch_predict',
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

            # 每 10 分钟检查当日未回填的比赛结果
            self._scheduler.add_job(
                self._today_backfill_check,
                IntervalTrigger(minutes=10),
                id='today_backfill_check',
                replace_existing=True,
            )

        self._scheduler.start()
        logger.info(f"AutoPredictionScheduler 启动: 预测@{trigger_hour}:00BJT, 回填@{backfill_hour}:00ET, 并发={Config.AUTO_PREDICT_MAX_CONCURRENT}")

        # 启动时立即执行一次（补漏 + 回填）
        def _startup_tasks():
            self._daily_batch_predict()
            if Config.AUTO_BACKFILL_ENABLED:
                self._today_backfill_check()

        threading.Thread(target=_startup_tasks, daemon=True).start()

    # ------------------------------------------------------------------
    # 批量预测
    # ------------------------------------------------------------------

    def _daily_batch_predict(self):
        """拉取今日赛程，并行预测所有尚未预测的比赛"""
        try:
            with self.app.app_context():
                games = self._get_today_games()
                if not games:
                    logger.info("今日无 NBA 比赛")
                    return

                # 过滤已预测的
                pending = []
                for game in games:
                    game_key = f"{game['away_abbr']}@{game['home_abbr']}_{game['game_date']}"
                    if game_key not in self._predicted_games:
                        pending.append((game, game_key))

                if not pending:
                    logger.info(f"今日 {len(games)} 场比赛均已预测")
                    return

                logger.info(f"今日 {len(games)} 场比赛，待预测 {len(pending)} 场，并发={Config.AUTO_PREDICT_MAX_CONCURRENT}")

                # 并行启动所有预测线程，由信号量控制并发
                threads = []
                for game, game_key in pending:
                    self._predicted_games.add(game_key)
                    t = threading.Thread(
                        target=self._run_auto_prediction,
                        args=(game,),
                        daemon=True,
                    )
                    threads.append(t)
                    t.start()

                # 等待所有线程完成
                for t in threads:
                    t.join()

                logger.info(f"今日批量预测完成: {len(pending)} 场")
        except Exception as e:
            logger.error(f"批量预测失败: {e}", exc_info=True)

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
                raw_date = (g.get('gameDateEst', '') or '').strip()
                if '/' in raw_date:
                    try:
                        g_date = datetime.strptime(raw_date[:10], '%m/%d/%Y').strftime('%Y-%m-%d')
                    except ValueError:
                        g_date = raw_date[:10]
                else:
                    g_date = raw_date[:10]
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
        from ..extensions import db

        home_abbr = game['home_abbr']
        away_abbr = game['away_abbr']
        game_date = game['game_date']
        matchup_id = f"auto_{away_abbr}_{home_abbr}_{game_date}"

        # 防重复：尝试插入占位记录，利用 DB 唯一约束防竞态
        existing = Prediction.query.filter_by(matchup_id=matchup_id).first()
        if existing:
            logger.info(f"已存在预测 {matchup_id}，跳过")
            return
        try:
            placeholder = Prediction(
                matchup_id=matchup_id,
                data={"_placeholder": True},
            )
            db.session.add(placeholder)
            db.session.commit()
        except Exception:
            db.session.rollback()
            logger.info(f"占位写入冲突 {matchup_id}，跳过")
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

    def _today_backfill_check(self):
        """每 10 分钟检查当日是否有已结束但未回填的比赛"""
        logger.info("当日回填检查: 开始")
        try:
            with self.app.app_context():
                self._do_today_backfill()
        except Exception as e:
            logger.error(f"当日回填检查失败: {e}", exc_info=True)

    def _do_today_backfill(self):
        """扫描当日（ET）缺 game_result 的自动预测，尝试回填"""
        import json
        from sqlalchemy.orm.attributes import flag_modified
        from ..extensions import db
        from ..models.prediction import Prediction
        from ..utils.hit_calculator import compute_hit_status
        from ..utils.redis_client import get_redis

        now_et = datetime.now(ET)
        today_et = now_et.strftime('%Y-%m-%d')
        yesterday_et = (now_et - timedelta(days=1)).strftime('%Y-%m-%d')
        check_dates = {today_et, yesterday_et}

        rows = Prediction.query.filter(
            Prediction.matchup_id.startswith('auto_')
        ).all()

        candidates = []
        for pred in rows:
            data = pred.data or {}
            mm = data.get('matchup_meta')
            if not mm or mm.get('game_date') not in check_dates:
                continue
            gr = data.get('game_result')
            if gr and gr.get('game_status_id') == 3 and gr.get('hit_status'):
                continue
            candidates.append((pred, mm, data))

        if not candidates:
            logger.info(f"当日回填: 无待处理 ({yesterday_et}~{today_et}, 共 {len(rows)} 条auto记录)")
            return

        logger.info(f"当日回填: {len(candidates)} 条待检查 ({yesterday_et}~{today_et})")

        from .data_fetcher.nba_stats import NBAStatsService
        nba_service = NBAStatsService()
        updated = 0

        for pred, mm, data in candidates:
            home_abbr = mm.get('home')
            away_abbr = mm.get('away')
            if not home_abbr or not away_abbr:
                continue

            game_date = mm.get('game_date')
            try:
                result = nba_service.fetch_game_result(home_abbr, away_abbr, game_date)
            except Exception as e:
                logger.warning(f"当日回填 API 错误 ({pred.matchup_id}): {e}")
                continue

            if not result or result.get('game_status_id') != 3:
                continue

            hit_status = compute_hit_status(data, result)
            result['hit_status'] = hit_status
            result['fetched_at'] = datetime.now().isoformat()

            data['game_result'] = result
            pred.data = data
            flag_modified(pred, 'data')
            db.session.add(pred)

            try:
                r = get_redis()
                key = f"prediction:{pred.matchup_id}"
                r.set(key, json.dumps(data, ensure_ascii=False), ex=Config.PREDICTION_TTL)
            except Exception:
                pass

            updated += 1
            hit_str = f"{hit_status['hit_count']}/{hit_status['total_markets']}"
            logger.info(f"当日回填: {pred.matchup_id} → "
                        f"{result.get('away_score')}-{result.get('home_score')} 命中 {hit_str}")

        if updated:
            db.session.commit()
            logger.info(f"当日回填完成: 更新 {updated} 条")

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
            'predicted_games': len(self._predicted_games),
            'pending_jobs': pending,
        }
