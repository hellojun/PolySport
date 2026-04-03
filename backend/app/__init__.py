"""
MiroFish Backend - Flask应用工厂
"""

import os
import warnings

warnings.filterwarnings("ignore", message=".*resource_tracker.*")

from flask import Flask, request
from flask_cors import CORS

from .config import Config
from .extensions import db, jwt
from .utils.logger import setup_logger, get_logger


def _cleanup_interrupted_tasks(app, logger):
    """启动时将被中断的 pending/processing 任务标记为 failed 并退还 token"""
    from datetime import datetime
    from decimal import Decimal
    try:
        with app.app_context():
            from .extensions import db
            from .models.prediction_task import PredictionTask
            from .models.user import User
            from .models.deposit import TokenTransaction

            interrupted = PredictionTask.query.filter(
                PredictionTask.status.in_(['pending', 'processing'])
            ).all()

            if not interrupted:
                return

            logger.info(f"发现 {len(interrupted)} 个被中断的预测任务，正在清理...")

            for task in interrupted:
                task.status = 'failed'
                task.error = '服务重启，任务被中断'
                task.updated_at = datetime.utcnow()

                # 退还 token
                user_id = task.user_id or (task.metadata_ or {}).get('user_id')
                if user_id:
                    pred_type = (task.metadata_ or {}).get('prediction_type', 'normal')
                    from .config import Config as C
                    cost = C.PREDICTION_COST_NORMAL if pred_type == 'normal' else C.PREDICTION_COST_PREMIUM
                    user = db.session.get(User, user_id)
                    if user:
                        user.token_balance += cost
                        tx = TokenTransaction(
                            user_id=user_id,
                            type='refund',
                            amount=Decimal(str(cost)),
                            balance=user.token_balance,
                            reference=task.id,
                        )
                        db.session.add(tx)
                        logger.info(f"  任务 {task.id[:8]}... 退还 {cost} token 给用户 {user_id}")

            db.session.commit()
            logger.info(f"清理完成，共处理 {len(interrupted)} 个任务")
    except Exception as e:
        logger.warning(f"清理中断任务失败: {e}")


def create_app(config_class=Config):
    """Flask应用工厂函数"""
    app = Flask(__name__)
    app.config.from_object(config_class)

    if hasattr(app, 'json') and hasattr(app.json, 'ensure_ascii'):
        app.json.ensure_ascii = False

    logger = setup_logger('mirofish')

    is_reloader_process = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
    debug_mode = app.config.get('DEBUG', False)
    should_log_startup = not debug_mode or is_reloader_process

    if should_log_startup:
        logger.info("=" * 50)
        logger.info("MiroFish Backend 启动中...")
        logger.info("=" * 50)

    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # 初始化 Flask 扩展
    db.init_app(app)
    jwt.init_app(app)

    # JWT 黑名单回调：检查 Redis 中的 jwt_blacklist:<jti>
    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(jwt_header, jwt_payload):
        from .utils.redis_client import get_redis
        jti = jwt_payload["jti"]
        r = get_redis()
        if r is None:
            return False
        return r.get(f"jwt_blacklist:{jti}") is not None

    @app.before_request
    def log_request():
        logger = get_logger('mirofish.request')
        logger.debug(f"请求: {request.method} {request.path}")
        if request.content_type and 'json' in request.content_type:
            logger.debug(f"请求体: {request.get_json(silent=True)}")

    @app.after_request
    def log_response(response):
        logger = get_logger('mirofish.request')
        logger.debug(f"响应: {response.status_code}")
        return response

    # 注册蓝图
    from .api import prediction_bp, auth_bp, deposit_bp, nft_bp
    app.register_blueprint(prediction_bp, url_prefix='/api/prediction')
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(deposit_bp, url_prefix='/api/deposit')
    app.register_blueprint(nft_bp, url_prefix='/api/nft')

    @app.route('/health')
    def health():
        return {'status': 'ok', 'service': 'MiroFish Backend'}

    # 创建数据库表
    with app.app_context():
        from .models.user import User  # noqa: F401
        from .models.deposit import DepositOrder, TokenTransaction  # noqa: F401
        from .models.prediction_task import PredictionTask  # noqa: F401
        from .models.prediction import Prediction  # noqa: F401
        db.create_all()

    # 启动时清理被中断的预测任务：标记 failed + 退还 token
    if should_log_startup:
        _cleanup_interrupted_tasks(app, logger)

    # 聪明钱排行榜：启动检查 + 月度定时任务
    if should_log_startup:
        from .services.data_fetcher.smart_money import (
            check_and_refresh_on_startup,
            start_monthly_scheduler,
        )
        check_and_refresh_on_startup()
        start_monthly_scheduler()

    if should_log_startup:
        logger.info("MiroFish Backend 启动完成")

    return app
