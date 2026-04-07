"""
Flask CLI 命令
"""

import time as _time
from datetime import datetime, timedelta

import click
from flask import current_app

from .config import Config
from .extensions import db
from .utils.hit_calculator import compute_hit_status, normalize_hit_status
from .utils.logger import get_logger
from .utils.redis_client import get_redis

logger = get_logger('mirofish.cli')

REDIS_PREDICTION_PREFIX = "prediction:"


def register_cli(app):
    """注册所有 CLI 命令"""

    @app.cli.command('backfill-results')
    @click.option('--dry-run', is_flag=True, help='只扫描不写入')
    @click.option('--limit', default=50, help='每次最多处理数')
    def backfill_results(dry_run, limit):
        """回填已结束比赛的实际结果和命中状态"""
        from .models.prediction import Prediction

        now = datetime.utcnow()
        cutoff = now - timedelta(hours=24)

        rows = Prediction.query.all()
        candidates = []

        for pred in rows:
            data = pred.data or {}
            mm = data.get('matchup_meta')
            if not mm:
                continue
            game_date = mm.get('game_date')
            if not game_date:
                continue

            # 仅处理 game_date 已过 24 小时的
            try:
                gd = datetime.strptime(game_date, '%Y-%m-%d')
            except ValueError:
                continue
            if gd > cutoff:
                continue

            # 跳过已有 Final 结果的
            gr = data.get('game_result')
            if gr and gr.get('game_status_id') == 3:
                # 但检查是否缺少 hit_status
                if gr.get('hit_status'):
                    continue

            candidates.append((pred, mm, data))

        click.echo(f"共 {len(rows)} 条预测，{len(candidates)} 条需要回填")

        if not candidates:
            click.echo("无需回填")
            return

        from .services.data_fetcher.nba_stats import NBAStatsService
        nba_service = NBAStatsService()

        processed = 0
        updated = 0
        errors = 0

        for pred, mm, data in candidates[:limit]:
            home_abbr = mm.get('home')
            away_abbr = mm.get('away')
            game_date = mm.get('game_date')

            if not home_abbr or not away_abbr:
                continue

            processed += 1
            click.echo(f"  [{processed}/{min(len(candidates), limit)}] "
                       f"{away_abbr} @ {home_abbr} ({game_date}) ... ", nl=False)

            try:
                result = nba_service.fetch_game_result(home_abbr, away_abbr, game_date)
            except Exception as e:
                click.echo(f"API 错误: {e}")
                errors += 1
                _time.sleep(Config.NBA_API_DELAY)
                continue

            if not result:
                click.echo("未找到比赛数据")
                _time.sleep(Config.NBA_API_DELAY)
                continue

            if result.get('game_status_id') != 3:
                status_text = result.get('game_status_text', '未知')
                click.echo(f"比赛未结束 ({status_text})")
                _time.sleep(Config.NBA_API_DELAY)
                continue

            # 计算命中状态
            hit_status = compute_hit_status(data, result)
            result['hit_status'] = hit_status
            result['fetched_at'] = datetime.now().isoformat()

            score_str = f"{result.get('away_score', '?')}-{result.get('home_score', '?')}"
            hit_str = f"{hit_status['hit_count']}/{hit_status['total_markets']}"
            click.echo(f"Final {score_str}, 命中 {hit_str}")

            if not dry_run:
                data['game_result'] = result
                pred.data = data
                # 标记 JSON 列已修改（SQLAlchemy 需要）
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(pred, 'data')
                db.session.add(pred)

                # 更新 Redis
                try:
                    import json
                    r = get_redis()
                    key = f"{REDIS_PREDICTION_PREFIX}{pred.matchup_id}"
                    r.set(key, json.dumps(data, ensure_ascii=False),
                          ex=Config.PREDICTION_TTL)
                except Exception:
                    pass

                updated += 1

            _time.sleep(Config.NBA_API_DELAY)

        if not dry_run:
            db.session.commit()

        click.echo(f"\n完成: 处理 {processed}, 更新 {updated}, 错误 {errors}")
        if dry_run:
            click.echo("(dry-run 模式，未实际写入)")

    @app.cli.command('auto-predict-status')
    def auto_predict_status():
        """显示自动预测调度器状态"""
        scheduler = getattr(current_app, 'auto_scheduler', None)
        if not scheduler:
            click.echo("自动预测调度器未启动（AUTO_PREDICT_ENABLED=false 或未初始化）")
            return

        status = scheduler.get_status()
        click.echo(f"调度器运行中: {status['running']}")
        click.echo(f"已调度比赛数: {status['scheduled_games']}")
        click.echo(f"待执行任务数: {len(status['pending_jobs'])}")
        for job in status['pending_jobs']:
            click.echo(f"  - {job['id']}  → {job['next_run']}")

    @app.cli.command('auto-predict-today')
    @click.option('--dry-run', is_flag=True, help='只展示赛程不执行')
    def auto_predict_today(dry_run):
        """手动触发今日所有比赛的自动预测"""
        from .services.auto_scheduler import AutoPredictionScheduler

        scheduler = AutoPredictionScheduler(current_app._get_current_object())
        games = scheduler._get_today_games()

        if not games:
            click.echo("今日无 NBA 比赛")
            return

        click.echo(f"今日 {len(games)} 场比赛:")
        for g in games:
            status_map = {1: '未开始', 2: '进行中', 3: '已结束'}
            status_text = status_map.get(g.get('game_status', 1), '未知')
            click.echo(f"  {g['away_abbr']} @ {g['home_abbr']}  "
                       f"{g['game_time_utc']}  [{status_text}]")

        if dry_run:
            click.echo("\n(dry-run 模式，未执行预测)")
            return

        click.echo("\n开始执行自动预测...")
        for g in games:
            if g.get('game_status', 1) >= 2:
                click.echo(f"  跳过已开始: {g['away_abbr']}@{g['home_abbr']}")
                continue
            try:
                scheduler._execute_prediction(g)
                click.echo(f"  完成: {g['away_abbr']}@{g['home_abbr']}")
            except Exception as e:
                click.echo(f"  失败: {g['away_abbr']}@{g['home_abbr']} — {e}")

    @app.cli.command('auto-predict-game')
    @click.argument('away')
    @click.argument('home')
    @click.option('--date', default=None, help='比赛日期 YYYY-MM-DD（默认今天 ET）')
    def auto_predict_game(away, home, date):
        """手动触发指定比赛的自动预测"""
        from zoneinfo import ZoneInfo
        from .services.auto_scheduler import AutoPredictionScheduler

        if not date:
            date = datetime.now(ZoneInfo('America/New_York')).strftime('%Y-%m-%d')

        away = away.upper()
        home = home.upper()

        click.echo(f"执行自动预测: {away} @ {home} ({date})")

        game = {
            'home_abbr': home,
            'away_abbr': away,
            'game_date': date,
            'game_time_utc': '',
            'game_id': '',
            'game_status': 1,
        }

        scheduler = AutoPredictionScheduler(current_app._get_current_object())
        try:
            scheduler._execute_prediction(game)
            click.echo("预测完成")
        except Exception as e:
            click.echo(f"预测失败: {e}")
