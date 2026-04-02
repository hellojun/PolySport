"""
预测API路由
POST /api/prediction/create     - 提交对阵数据，创建异步预测任务
GET  /api/prediction/task/<id>  - 查询任务进度
GET  /api/prediction/result/<matchup_id> - 获取预测结果(分层)
GET  /api/prediction/history    - 获取预测历史列表
GET  /api/prediction/polymarket/events   - 获取 Polymarket NBA 盘口
"""

import json
import re
import time as _time
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Dict, Optional

from flask import request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from . import prediction_bp
from ..config import Config
from ..extensions import db
from ..models.task import TaskManager, TaskStatus
from ..models.matchup import MatchupInput
from ..models.user import User
from ..models.deposit import TokenTransaction
from ..services.graph_builder import GraphBuilderService
from ..services.zep_tools import ZepToolsService
from ..services.text_processor import TextProcessor
from ..services.nba_ontology import get_nba_ontology
from ..services.debate_engine import DebateEngine
from ..services.prediction_generator import PredictionGenerator, PredictionOutput
from ..utils.llm_client import LLMClient
from ..utils.redis_client import get_redis
from ..utils.logger import get_logger

logger = get_logger('mirofish.api.prediction')

REDIS_PREDICTION_PREFIX = "prediction:"

# 内存缓存
_prediction_store: Dict[str, dict] = {}
task_manager = TaskManager()


def _save_prediction(matchup_id: str, output: PredictionOutput, graph_data=None,
                     matchup_meta: Optional[dict] = None,
                     user_id=None, task_id: str = None):
    """保存预测结果到 PG + 内存 + Redis"""
    data = output.to_dict(level="L3")
    if graph_data:
        data["graph_data"] = graph_data
    if matchup_meta:
        data["matchup_meta"] = matchup_meta
    # 内存 + Redis
    _prediction_store[matchup_id] = data
    r = get_redis()
    key = f"{REDIS_PREDICTION_PREFIX}{matchup_id}"
    r.set(key, json.dumps(data, ensure_ascii=False), ex=Config.PREDICTION_TTL)
    # PG
    _save_prediction_to_pg(matchup_id, data, user_id=user_id, task_id=task_id)


def _load_prediction(matchup_id: str) -> Optional[dict]:
    """加载预测结果：内存 → Redis → PG（三级 fallback）"""
    data = _prediction_store.get(matchup_id)
    if data:
        return data
    r = get_redis()
    key = f"{REDIS_PREDICTION_PREFIX}{matchup_id}"
    raw = r.get(key)
    if raw:
        data = json.loads(raw)
        _prediction_store[matchup_id] = data
        return data
    # PG fallback
    data = _load_prediction_from_pg(matchup_id)
    if data:
        _prediction_store[matchup_id] = data
        r.set(key, json.dumps(data, ensure_ascii=False), ex=Config.PREDICTION_TTL)
    return data


def _save_prediction_data(matchup_id: str, data: dict):
    """保存修改后的预测数据到 PG + 内存 + Redis"""
    _prediction_store[matchup_id] = data
    r = get_redis()
    key = f"{REDIS_PREDICTION_PREFIX}{matchup_id}"
    r.set(key, json.dumps(data, ensure_ascii=False), ex=Config.PREDICTION_TTL)
    # 更新 PG
    _save_prediction_to_pg(matchup_id, data)


def _save_prediction_to_pg(matchup_id: str, data: dict, user_id=None, task_id: str = None):
    """写入/更新 PG predictions 表（需在 app context 内调用，或自动获取）"""
    try:
        # 检测是否已在 app context 中
        from flask import current_app
        in_context = True
        try:
            current_app._get_current_object()
        except RuntimeError:
            in_context = False

        if in_context:
            _do_save_prediction_pg(matchup_id, data, user_id, task_id)
        else:
            # 从 TaskManager 获取 app 引用
            app = task_manager._app
            if app:
                with app.app_context():
                    _do_save_prediction_pg(matchup_id, data, user_id, task_id)
    except Exception as e:
        logger.warning(f"PG prediction 写入失败 ({matchup_id}): {e}")


def _do_save_prediction_pg(matchup_id: str, data: dict, user_id=None, task_id: str = None):
    """实际执行 PG 写入（需在 app context 内）"""
    from ..models.prediction import Prediction
    existing = Prediction.query.filter_by(matchup_id=matchup_id).first()
    if existing:
        existing.data = data
        if user_id is not None:
            existing.user_id = user_id
        if task_id is not None:
            existing.task_id = task_id
    else:
        pred = Prediction(
            matchup_id=matchup_id,
            user_id=user_id,
            task_id=task_id,
            data=data,
        )
        db.session.add(pred)
    db.session.commit()


def _load_prediction_from_pg(matchup_id: str) -> Optional[dict]:
    """从 PG predictions 表加载（自动处理 app context）"""
    try:
        from flask import current_app
        in_context = True
        try:
            current_app._get_current_object()
        except RuntimeError:
            in_context = False

        if in_context:
            return _do_load_prediction_pg(matchup_id)
        else:
            app = task_manager._app
            if app:
                with app.app_context():
                    return _do_load_prediction_pg(matchup_id)
    except Exception as e:
        logger.warning(f"PG prediction 读取失败 ({matchup_id}): {e}")
    return None


def _do_load_prediction_pg(matchup_id: str) -> Optional[dict]:
    """实际执行 PG 读取（需在 app context 内）"""
    from ..models.prediction import Prediction
    pred = Prediction.query.filter_by(matchup_id=matchup_id).first()
    if pred:
        return pred.data
    return None


def _compute_hit_status(prediction: dict, game_result: dict) -> dict:
    """
    计算预测命中状态。
    prediction 的 betting_card 是主队视角:
      - moneyline: pick=主队缩写, model_probability=主队胜概率
      - spread: pick="主队 +/-线", opponent_pick="客队 +/-线"
      - total: pick="OVER 线", opponent_pick="UNDER 线"
    """
    betting_card = prediction.get('betting_card', [])
    home_score = game_result.get('home_score')
    away_score = game_result.get('away_score')
    home_abbr = game_result.get('home_abbr', '')
    away_abbr = game_result.get('away_abbr', '')

    if home_score is None or away_score is None:
        return {"moneyline_hit": None, "spread_hit": None, "total_hit": None,
                "hit_count": 0, "total_markets": 0}

    result = {"moneyline_hit": None, "spread_hit": None, "total_hit": None}
    hit_count = 0
    total_markets = 0

    for card in betting_card:
        market = card.get('market', '')
        pick = card.get('pick', '')
        model_prob = card.get('model_probability', 0.5)

        if market == 'moneyline':
            total_markets += 1
            # 模型选主队胜概率 > 0.5 → pick 主队, 否则 pick 客队
            model_picks_home = model_prob > 0.5
            home_won = home_score > away_score
            if home_score == away_score:
                result["moneyline_hit"] = None  # 平局(NBA极少)
            else:
                result["moneyline_hit"] = model_picks_home == home_won
                if result["moneyline_hit"]:
                    hit_count += 1

        elif market == 'spread':
            total_markets += 1
            # spread pick 格式: "ORL +3.5" 或 "ORL -3.5"
            # model_probability > 0.5 → 模型选主队 cover
            # 实际: home_score + spread_line > away_score → 主队 cover
            import re as _re
            m = _re.search(r'([+-]?\d+\.?\d*)', pick)
            if m:
                spread_line = float(m.group(1))
                home_margin = home_score - away_score
                # 主队让分后的 margin
                covered = (home_margin + spread_line) > 0
                model_picks_home_cover = model_prob > 0.5
                if (home_margin + spread_line) == 0:
                    result["spread_hit"] = None  # push
                else:
                    result["spread_hit"] = model_picks_home_cover == covered
                    if result["spread_hit"]:
                        hit_count += 1

        elif market == 'total':
            total_markets += 1
            # pick 格式: "OVER 220.5"
            import re as _re
            m = _re.search(r'(\d+\.?\d*)', pick)
            if m:
                total_line = float(m.group(1))
                actual_total = home_score + away_score
                is_over = actual_total > total_line
                model_picks_over = model_prob > 0.5
                if actual_total == total_line:
                    result["total_hit"] = None  # push
                else:
                    result["total_hit"] = model_picks_over == is_over
                    if result["total_hit"]:
                        hit_count += 1

    result["hit_count"] = hit_count
    result["total_markets"] = total_markets
    return result


@prediction_bp.route('/stats', methods=['GET'])
def get_public_stats():
    """公开端点：返回预测命中率统计"""
    from ..models.prediction import Prediction

    rows = Prediction.query.all()
    total_predictions = len(rows)
    ml_hits, ml_total = 0, 0
    sp_hits, sp_total = 0, 0
    tt_hits, tt_total = 0, 0

    for pred in rows:
        data = pred.data or {}
        gr = data.get('game_result')
        if not gr or gr.get('game_status_id') != 3:
            continue
        hs = gr.get('hit_status')
        if not hs:
            continue
        if hs.get('moneyline_hit') is not None:
            ml_total += 1
            if hs['moneyline_hit']:
                ml_hits += 1
        if hs.get('spread_hit') is not None:
            sp_total += 1
            if hs['spread_hit']:
                sp_hits += 1
        if hs.get('total_hit') is not None:
            tt_total += 1
            if hs['total_hit']:
                tt_hits += 1

    total_with_result = max(ml_total, sp_total, tt_total)
    insufficient = total_with_result < 10

    return jsonify({
        "success": True,
        "total_predictions": total_predictions,
        "total_with_result": total_with_result,
        "moneyline_hit_rate": round(ml_hits / ml_total, 3) if ml_total else 0,
        "spread_hit_rate": round(sp_hits / sp_total, 3) if sp_total else 0,
        "total_hit_rate": round(tt_hits / tt_total, 3) if tt_total else 0,
        "insufficient": insufficient,
    })


@prediction_bp.route('/game-result/<matchup_id>', methods=['POST'])
@jwt_required()
def fetch_game_result(matchup_id):
    """获取比赛实际结果并计算命中状态"""
    user_id = get_jwt_identity()
    prediction = _load_prediction(matchup_id)
    if not prediction:
        return jsonify({"success": False, "error": "预测结果不存在"}), 404

    # 如果已有 Final 的缓存结果，直接返回
    existing = prediction.get('game_result')
    if existing and existing.get('game_status_id') == 3:
        return jsonify({"success": True, "game_result": existing})

    # 从 prediction 数据或 task metadata 提取球队和日期
    home_abbr = None
    away_abbr = None
    game_date = None

    # 优先从 prediction 自身的 matchup_meta 读取
    mm = prediction.get("matchup_meta")
    if mm:
        home_abbr = mm.get("home")
        away_abbr = mm.get("away")
        game_date = mm.get("game_date")

    # Fallback: 从 task metadata 查找
    if not home_abbr or not away_abbr or not game_date:
        tasks = task_manager.list_tasks(task_type="prediction")
        for t in tasks:
            meta = t.get("metadata") or {}
            if meta.get("matchup_id") == matchup_id:
                home_abbr = home_abbr or meta.get("home")
                away_abbr = away_abbr or meta.get("away")
                game_date = game_date or meta.get("game_date")
                break

    # Fallback: 从请求体或 query 参数读取
    if not home_abbr or not away_abbr or not game_date:
        body = request.get_json(silent=True) or {}
        home_abbr = home_abbr or body.get("home") or request.args.get("home")
        away_abbr = away_abbr or body.get("away") or request.args.get("away")
        game_date = game_date or body.get("game_date") or request.args.get("game_date")

    if not home_abbr or not away_abbr or not game_date:
        return jsonify({"success": False, "error": "无法找到对应的比赛信息"}), 400

    try:
        from ..services.data_fetcher.nba_stats import NBAStatsService
        nba_service = NBAStatsService()
        result = nba_service.fetch_game_result(home_abbr, away_abbr, game_date)
    except Exception as e:
        logger.error(f"获取比赛结果失败: {e}")
        return jsonify({"success": False, "error": f"获取比赛结果失败: {e}"}), 500

    if not result:
        return jsonify({"success": False, "error": "未找到该场比赛数据"}), 404

    if result.get('game_status_id') != 3:
        return jsonify({
            "success": False,
            "error": "game_not_ended",
            "game_status_id": result.get('game_status_id'),
            "game_status_text": result.get('game_status_text'),
        }), 400

    # 计算命中状态
    hit_status = _compute_hit_status(prediction, result)
    result['hit_status'] = hit_status
    result['fetched_at'] = datetime.now().isoformat()

    # 存入 prediction
    prediction['game_result'] = result
    _save_prediction_data(matchup_id, prediction)

    return jsonify({"success": True, "game_result": result})


@prediction_bp.route('/history', methods=['GET'])
@jwt_required()
def get_prediction_history():
    """获取预测历史列表（仅 completed 和 failed），按 user_id 隔离，从 PG 联表查询"""
    user_id = get_jwt_identity()

    from ..models.prediction_task import PredictionTask
    from ..models.prediction import Prediction

    # PG 联表查询：prediction_tasks LEFT JOIN predictions
    rows = (
        db.session.query(PredictionTask, Prediction)
        .outerjoin(Prediction, PredictionTask.id == Prediction.task_id)
        .filter(PredictionTask.user_id == user_id)
        .filter(PredictionTask.task_type == "prediction")
        .filter(PredictionTask.status.in_(["completed", "failed"]))
        .order_by(PredictionTask.created_at.desc())
        .all()
    )

    predictions = []
    for pt, pred in rows:
        meta = pt.metadata_ or {}
        result = pt.result or {}
        item = {
            "task_id": pt.id,
            "matchup_id": meta.get("matchup_id", ""),
            "home": meta.get("home", ""),
            "away": meta.get("away", ""),
            "game_date": meta.get("game_date", ""),
            "game_time": meta.get("game_time", ""),
            "status": pt.status,
            "created_at": pt.created_at.isoformat() if pt.created_at else "",
            "duration_seconds": result.get("duration_seconds"),
            "total_llm_calls": result.get("total_llm_calls"),
            "step_timings": result.get("step_timings"),
            "error": pt.error,
        }
        # 附加比赛结果摘要
        if pred and pt.status == "completed" and pred.data:
            gr = pred.data.get("game_result")
            if gr:
                item["game_result"] = {
                    "home_score": gr.get("home_score"),
                    "away_score": gr.get("away_score"),
                    "game_status_id": gr.get("game_status_id"),
                    "hit_status": gr.get("hit_status"),
                }
        predictions.append(item)

    # 补充内存中仍在运行但也匹配条件的任务（理论上此处不会有，因为只查 completed/failed）
    return jsonify({"success": True, "predictions": predictions})


@prediction_bp.route('/delete/<task_id>', methods=['DELETE'])
@jwt_required()
def delete_prediction(task_id):
    """删除预测记录（任务 + 关联的预测结果），校验用户所有权"""
    user_id = get_jwt_identity()

    # 优先从 PG 校验所有权
    from ..models.prediction_task import PredictionTask
    from ..models.prediction import Prediction

    pt = db.session.get(PredictionTask, task_id)
    task = task_manager.get_task(task_id)

    if not pt and not task:
        return jsonify({"success": False, "error": "任务不存在"}), 404

    # 校验所有权（PG 优先）
    owner_id = None
    matchup_id = None
    if pt:
        owner_id = pt.user_id
        matchup_id = (pt.metadata_ or {}).get("matchup_id")
    elif task:
        meta = task.metadata or {}
        owner_id = meta.get("user_id")
        matchup_id = meta.get("matchup_id")

    if owner_id != int(user_id):
        return jsonify({"success": False, "error": "无权操作"}), 403

    # 清理关联的预测结果（PG + 内存 + Redis）
    if matchup_id:
        _prediction_store.pop(matchup_id, None)
        r = get_redis()
        r.delete(f"{REDIS_PREDICTION_PREFIX}{matchup_id}")
        # 删除 PG prediction
        Prediction.query.filter_by(matchup_id=matchup_id).delete()

    # 删除 PG task
    if pt:
        db.session.delete(pt)
    db.session.commit()

    # 删除内存 + Redis task
    task_manager.delete_task(task_id, user_id=user_id)
    return jsonify({"success": True})


def _seconds_until_et_midnight(date_str: str) -> int:
    """计算从现在到指定日期美东时间 23:59:59 的剩余秒数，最少 600 秒"""
    from zoneinfo import ZoneInfo
    et = ZoneInfo('America/New_York')
    target = datetime.strptime(date_str, '%Y-%m-%d').replace(
        hour=23, minute=59, second=59, tzinfo=et,
    )
    now_et = datetime.now(et)
    remaining = int((target - now_et).total_seconds())
    return max(remaining, 600)  # 至少缓存 10 分钟


@prediction_bp.route('/polymarket/events', methods=['GET'])
def get_polymarket_events():
    """获取指定日期的 Polymarket NBA 盘口（Redis 缓存至美东 23:59）"""
    date_str = request.args.get('date', '').strip()

    # 验证日期格式
    if not date_str or not re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        return jsonify({"success": False, "error": "请提供有效日期，格式: YYYY-MM-DD"}), 400

    # 尝试从 Redis 缓存读取
    r = get_redis()
    cache_key = f"polymarket_events:{date_str}"
    cached = r.get(cache_key)
    if cached:
        logger.info(f"Polymarket events cache hit: {date_str}")
        return jsonify(json.loads(cached))

    try:
        from ..services.data_fetcher.polymarket import PolymarketService
        service = PolymarketService()
        events = service.fetch_nba_events(date_str)
        result = {
            "success": True,
            "date": date_str,
            "events": events,
        }
        # 写入 Redis 缓存，有效期到该日期美东 23:59
        ttl = _seconds_until_et_midnight(date_str)
        r.set(cache_key, json.dumps(result, ensure_ascii=False), ex=ttl)
        return jsonify(result)
    except Exception as e:
        logger.error(f"获取 Polymarket 盘口失败: {e}")
        return jsonify({"success": False, "error": f"获取盘口数据失败: {e}"}), 500


@prediction_bp.route('/create', methods=['POST'])
@jwt_required()
def create_prediction():
    """创建预测任务"""
    from flask import current_app
    user_id = int(get_jwt_identity())
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "请求体为空"}), 400

    try:
        matchup = MatchupInput.from_request(data)
    except Exception as e:
        return jsonify({"success": False, "error": f"数据解析失败: {e}"}), 400

    if not matchup.home_team.abbreviation or not matchup.away_team.abbreviation:
        return jsonify({"success": False, "error": "主客队缩写不能为空"}), 400

    lang = data.get("lang", "en")
    if lang not in ("zh", "en"):
        lang = "en"

    # 预测类型 & 定价
    prediction_type = data.get("prediction_type", "premium")
    if prediction_type not in ("normal", "premium"):
        prediction_type = "premium"

    cost = Config.PREDICTION_COST_NORMAL if prediction_type == "normal" else Config.PREDICTION_COST_PREMIUM

    # 余额检查 & 扣费
    user = User.query.get(user_id)
    balance = float(user.token_balance or 0)
    if balance < cost:
        return jsonify({
            "success": False,
            "error": "余额不足",
            "required": cost,
            "balance": balance,
        }), 402

    from decimal import Decimal
    user.token_balance = (user.token_balance or Decimal(0)) - Decimal(str(cost))

    fast_mode = bool(data.get("fast_mode", False))
    debate_rounds = data.get("debate_rounds", Config.DEBATE_NUM_ROUNDS)
    if debate_rounds not in (1, 2, 3):
        debate_rounds = Config.DEBATE_NUM_ROUNDS

    # 根据 prediction_type 调整参数
    if prediction_type == "normal":
        debate_rounds = 1
        use_graph = False
        use_smart_money = False
    else:
        use_graph = True
        use_smart_money = True

    # 创建异步任务
    task_id = task_manager.create_task(
        task_type="prediction",
        metadata={
            "matchup_id": matchup.matchup_id,
            "home": matchup.home_team.abbreviation,
            "away": matchup.away_team.abbreviation,
            "game_date": matchup.game_date or "",
            "game_time": data.get("game_time") or "",
            "lang": lang,
            "prediction_type": prediction_type,
            "user_id": user_id,
        },
        user_id=user_id,
    )

    # 记录扣费流水
    tx_type = 'predict_normal' if prediction_type == 'normal' else 'predict_premium'
    tx_record = TokenTransaction(
        user_id=user_id,
        type=tx_type,
        amount=Decimal(str(-cost)),
        balance=user.token_balance,
        reference=task_id,
    )
    db.session.add(tx_record)
    db.session.commit()

    # 后台线程执行（需要传递 app context）
    app = current_app._get_current_object()
    thread = threading.Thread(
        target=_prediction_worker,
        args=(app, task_id, matchup, lang, fast_mode, debate_rounds, use_graph, use_smart_money, user_id, cost),
        daemon=True,
    )
    thread.start()

    return jsonify({
        "success": True,
        "task_id": task_id,
        "matchup_id": matchup.matchup_id,
        "cost": cost,
        "balance": float(user.token_balance),
    })


@prediction_bp.route('/task/<task_id>', methods=['GET'])
@jwt_required()
def get_prediction_task(task_id):
    """查询任务进度"""
    task = task_manager.get_task(task_id)
    if not task:
        return jsonify({"success": False, "error": "任务不存在"}), 404

    return jsonify({
        "success": True,
        "task": task.to_dict(),
    })


@prediction_bp.route('/result/<matchup_id>', methods=['GET'])
@jwt_required()
def get_prediction_result(matchup_id):
    """获取预测结果"""
    level = request.args.get("level", "L1").upper()
    if level not in ("L1", "L2", "L3"):
        level = "L1"

    data = _load_prediction(matchup_id)
    if not data:
        return jsonify({"success": False, "error": "预测结果不存在"}), 404

    # 按层级过滤返回
    prediction = dict(data)
    if level == "L1":
        prediction.pop("key_factors", None)
        prediction.pop("consensus", None)
        prediction.pop("debate_log", None)
    elif level == "L2":
        prediction.pop("debate_log", None)

    return jsonify({
        "success": True,
        "level": level,
        "prediction": prediction,
    })


def _prediction_worker(app, task_id: str, matchup: MatchupInput, lang: str = "en",
                       fast_mode: bool = False, debate_rounds: int = 3,
                       use_graph: bool = True, use_smart_money: bool = True,
                       user_id: int = None, cost: int = 0):
    """
    后台预测工作线程（带丰富进度详情）

    编排流程:
    01. 创建临时 Zep 图谱 + 注册 NBA 本体          (5%)
    02. 拉取 NBA 统计数据                          (7%)
    03. 拉取聪明钱链上数据                          (8-9%)
    04. 注入对阵文本 + 等待图谱处理                  (10-15%)
    05. 图谱构建完成 + 获取图谱数据                  (18%)
    06. 辩论分析 (3 rounds × 7 analysts)           (20-85%)
    07. 生成预测结果                                (90%)
    """
    # 确保 TaskManager 有 app 引用
    task_manager.set_app(app)

    graph_id = None
    steps = []  # 累积步骤数据
    graph_data_for_frontend = None  # 图谱可视化数据
    step_timings = {}  # step_num → duration_s
    _step_start = [None]  # mutable for closure

    def _start_timer(step_num):
        _step_start[0] = _time.time()

    def _stop_timer(step_num):
        if _step_start[0] is not None:
            elapsed = round(_time.time() - _step_start[0], 1)
            step_timings[step_num] = elapsed
            # 写入 step details
            for s in steps:
                if s.get("step") == step_num:
                    s.setdefault("details", {})["duration_s"] = elapsed
            _step_start[0] = None
            return elapsed
        return 0

    # 多语言进度消息模板
    from ..services.analyst_agents import get_analyst_roles as _get_roles
    _num_analysts = len(_get_roles())
    _total_llm = _num_analysts * 3

    _msg = {
        "zh": {
            "init": "初始化预测引擎...",
            "create_graph": "创建知识图谱...",
            "graph_done": "知识图谱创建完成",
            "fetch_nba": "拉取NBA统计数据...",
            "nba_ready": "NBA数据就绪",
            "smart_money": "拉取聪明钱链上数据...",
            "smart_money_done": "聪明钱数据就绪",
            "inject_graph": "注入对阵数据到图谱...",
            "wait_graph": "等待图谱处理...",
            "graph_process_done": "图谱处理完成",
            "fetch_graph_data": "获取图谱结构数据...",
            "graph_ready": "图谱就绪，准备辩论",
            "start_debate": "开始辩论分析...",
            "debate_done": "辩论分析完成",
            "gen_prediction": "生成预测结果...",
            "complete": "预测完成",
            "step1_title": "创建知识图谱",
            "step1_desc": "创建临时 Zep 图谱并注册 NBA 本体",
            "step2_title": "拉取 NBA 数据",
            "step2_desc": "从 NBA Stats API 拉取球队战绩、高级统计、球员数据",
            "step3_title": "拉取聪明钱数据",
            "step3_desc": "查询 Polymarket 链上聪明钱地址持仓",
            "step4_title": "注入图谱 & 处理",
            "step4_desc": "将对阵文本分块注入 Zep 图谱，等待实体/关系提取",
            "step5_title": "图谱构建完成",
            "step5_desc": "提取图谱节点与关系，生成可视化数据",
            "step6_title": "辩论分析",
            "step6_desc": f"{_num_analysts} 位分析师 × 3 轮辩论 = {_total_llm} 次 LLM 调用",
            "step7_title": "生成预测结果",
            "step7_desc": "综合辩论结果生成最终预测",
        },
        "en": {
            "init": "Initializing prediction engine...",
            "create_graph": "Creating knowledge graph...",
            "graph_done": "Knowledge graph created",
            "fetch_nba": "Fetching NBA stats...",
            "nba_ready": "NBA data ready",
            "smart_money": "Fetching smart money on-chain data...",
            "smart_money_done": "Smart money data ready",
            "inject_graph": "Injecting matchup data...",
            "wait_graph": "Waiting for graph processing...",
            "graph_process_done": "Graph processing complete",
            "fetch_graph_data": "Fetching graph structure...",
            "graph_ready": "Graph ready, preparing debate",
            "start_debate": "Starting debate analysis...",
            "debate_done": "Debate analysis complete",
            "gen_prediction": "Generating predictions...",
            "complete": "Prediction complete",
            "step1_title": "Create Knowledge Graph",
            "step1_desc": "Create temporary Zep graph and register NBA ontology",
            "step2_title": "Fetch NBA Data",
            "step2_desc": "Fetch team standings, advanced stats, player data from NBA Stats API",
            "step3_title": "Fetch Smart Money Data",
            "step3_desc": "Query on-chain smart money positions on Polymarket",
            "step4_title": "Inject Graph & Process",
            "step4_desc": "Split matchup text and inject into Zep graph for entity/relation extraction",
            "step5_title": "Graph Build Complete",
            "step5_desc": "Extract graph nodes and relations, generate visualization data",
            "step6_title": "Debate Analysis",
            "step6_desc": f"{_num_analysts} analysts × 3 rounds = {_total_llm} LLM calls",
            "step7_title": "Generate Predictions",
            "step7_desc": "Synthesize debate results into final prediction",
        },
    }
    msg = _msg.get(lang, _msg["en"])

    def _update(progress: int, message: str, new_step: dict = None):
        """统一更新进度，附带累积的 steps 和 graph_data"""
        if new_step:
            steps.append(new_step)
        detail = {"steps": steps}
        if graph_data_for_frontend:
            detail["graph_data"] = graph_data_for_frontend
        task_manager.update_task(
            task_id, progress=progress, message=message,
            progress_detail=detail,
        )

    try:
        task_manager.update_task(
            task_id, status=TaskStatus.PROCESSING, progress=2,
            message=msg["init"],
            progress_detail={"steps": [], "graph_data": None},
        )

        llm = LLMClient()

        graph_context = ""

        step_counter = 1  # 动态步骤编号（普通预测跳过图谱步骤时保持连续）

        if use_graph:
            graph_service = GraphBuilderService()
            zep_tools = ZepToolsService(llm_client=llm)

            # ── Step 01: 创建图谱 + 设置本体 ──
            _start_timer(1)
            _update(3, msg["create_graph"], {
                "step": step_counter, "title": msg["step1_title"], "status": "running",
                "desc": msg["step1_desc"],
            })
            graph_name = f"NBA_{matchup.home_team.abbreviation}_vs_{matchup.away_team.abbreviation}"
            graph_id = graph_service.create_graph(graph_name)
            ontology = get_nba_ontology()
            graph_service.set_ontology(graph_id, ontology)
            logger.info(f"图谱已创建: {graph_id}")

            entity_type_names = [e["name"] for e in ontology["entity_types"]]
            edge_type_names = [e["name"] for e in ontology["edge_types"]]
            steps[-1].update({
                "status": "completed",
                "details": {
                    "graph_id": graph_id,
                    "matchup_id": matchup.matchup_id,
                    "entity_types": entity_type_names,
                    "relation_types": edge_type_names,
                    "ontology_entities": len(entity_type_names),
                    "ontology_relations": len(edge_type_names),
                },
            })
            _stop_timer(1)
            step_counter += 1
            _update(5, msg["graph_done"])
        else:
            # 普通预测：跳过图谱，step_counter 仍为 1
            _update(5, msg["graph_done"])

        # ── 流水线：立即注入核心文本，Zep 处理与数据拉取并行 ──
        all_episode_uuids = []
        core_chunks = []
        if use_graph:
            core_text = matchup.to_graph_text()
            core_chunks = TextProcessor.split_text(
                core_text,
                chunk_size=Config.GRAPH_CHUNK_SIZE,
                overlap=Config.GRAPH_CHUNK_OVERLAP,
            )
            core_episode_uuids = graph_service.add_text_batches(graph_id, core_chunks, batch_size=3)
            all_episode_uuids = list(core_episode_uuids)
            logger.info(f"核心文本已注入图谱: {len(core_chunks)} chunks, Zep 开始后台处理")

        # ── 拉取 NBA 数据 + 聪明钱数据 ──
        # 普通预测用连续编号（从 step_counter 递增），premium 用固定编号
        _start_timer(step_counter)
        nba_step = {
            "step": step_counter, "title": msg["step2_title"], "status": "running",
            "desc": msg["step2_desc"],
        }
        smart_money_context = None
        sm_step = None
        if Config.SMART_MONEY_ENABLED and use_smart_money:
            sm_step = {
                "step": step_counter + 1, "title": msg["step3_title"], "status": "running",
                "desc": msg["step3_desc"],
            }
            _update(6, msg["fetch_nba"], nba_step)
            steps.append(sm_step)
            _update(6, msg["smart_money"])
        else:
            _update(6, msg["fetch_nba"], nba_step)

        def _fetch_nba():
            """并行子任务：拉取 NBA 数据"""
            if not Config.NBA_API_ENABLED:
                return None, {"info": "NBA API 已禁用"}
            from ..services.data_fetcher.nba_stats import NBAStatsService
            nba_service = NBAStatsService()
            stats_data = nba_service.fetch_matchup_data(
                home_abbr=matchup.home_team.abbreviation,
                away_abbr=matchup.away_team.abbreviation,
            )
            matchup.nba_stats = stats_data
            matchup.enriched_text = nba_service.to_enrichment_text(
                stats_data,
                matchup.home_team.abbreviation,
                matchup.away_team.abbreviation,
            )
            nba_details = {"season": stats_data.get("season", "N/A")}
            for side, abbr in [("home", matchup.home_team.abbreviation),
                               ("away", matchup.away_team.abbreviation)]:
                sd = stats_data.get(side)
                if sd and sd.get("standings"):
                    st = sd["standings"]
                    nba_details[f"{side}_record"] = f'{st.get("wins",0)}-{st.get("losses",0)}'
                    nba_details[f"{side}_win_pct"] = st.get("win_pct", 0)
                    nba_details[f"{side}_conf_rank"] = st.get("conference_rank", "?")
                if sd and sd.get("advanced"):
                    adv = sd["advanced"]
                    nba_details[f"{side}_off_rtg"] = adv.get("off_rating")
                    nba_details[f"{side}_def_rtg"] = adv.get("def_rating")
                    nba_details[f"{side}_net_rtg"] = adv.get("net_rating")
                if sd and sd.get("players"):
                    top3 = sd["players"][:3]
                    nba_details[f"{side}_top_players"] = [
                        {"name": p["name"], "ppg": p["ppg"], "rpg": p["rpg"], "apg": p["apg"]}
                        for p in top3
                    ]
            return stats_data, nba_details

        def _fetch_smart_money():
            """并行子任务：拉取聪明钱数据"""
            from ..services.data_fetcher.smart_money import SmartMoneyService
            sm_service = SmartMoneyService()
            condition_id = matchup.condition_id or ""
            token_ids = matchup.token_ids or []
            sm_data = sm_service.fetch_positions(condition_id, token_ids)
            matchup.smart_money_data = sm_data
            ctx = sm_service.to_context_text(
                sm_data,
                home_abbr=matchup.home_team.abbreviation,
                away_abbr=matchup.away_team.abbreviation,
            )
            matchup.smart_money_context = ctx
            sm_details = {
                "tracked_wallets": sm_data.get("tracked_wallets", 0),
                "wallets_with_position": sm_data.get("wallets_with_position", 0),
                "majority_direction": sm_data.get("majority_direction", ""),
                "status": sm_data.get("status", ""),
            }
            return ctx, sm_details

        # 并行执行
        with ThreadPoolExecutor(max_workers=2) as pool:
            nba_future = pool.submit(_fetch_nba)
            sm_future = pool.submit(_fetch_smart_money) if (Config.SMART_MONEY_ENABLED and use_smart_money) else None

            # 处理 NBA 结果
            try:
                nba_result, nba_details = nba_future.result()
                nba_step.update({"status": "completed", "details": nba_details})
                logger.info("NBA数据拉取完成")
            except Exception as e:
                logger.warning(f"NBA数据拉取失败: {e}")
                nba_step.update({"status": "completed", "details": {"warning": f"拉取失败: {e}"}})

            # 处理聪明钱结果
            if sm_future is not None:
                try:
                    smart_money_context, sm_details = sm_future.result()
                    sm_step.update({"status": "completed", "details": sm_details})
                    logger.info(f"聪明钱数据拉取完成: {sm_details.get('wallets_with_position', 0)} 个地址有持仓")
                except Exception as e:
                    logger.warning(f"聪明钱数据拉取失败: {e}")
                    smart_money_context = "On-chain smart money data is currently unavailable."
                    sm_step.update({"status": "completed", "details": {"warning": f"拉取失败: {e}"}})

        _stop_timer(step_counter)  # NBA + 聪明钱总计时
        if use_smart_money and Config.SMART_MONEY_ENABLED:
            step_counter += 2  # NBA + 聪明钱各占一步
        else:
            step_counter += 1  # 仅 NBA
        _update(9, msg["nba_ready"])

        if use_graph:
            # ── 注入 NBA 富化数据 + 等待全部 Zep 处理 ──
            _start_timer(step_counter)
            _update(9, msg["inject_graph"], {
                "step": step_counter, "title": msg["step4_title"], "status": "running",
                "desc": msg["step4_desc"],
            })

            enriched_chunks_count = 0

            # 追加注入 NBA 富化数据（如有）
            if matchup.enriched_text:
                enriched_chunks = TextProcessor.split_text(
                    matchup.enriched_text,
                    chunk_size=Config.GRAPH_CHUNK_SIZE,
                    overlap=Config.GRAPH_CHUNK_OVERLAP,
                )
                enriched_uuids = graph_service.add_text_batches(graph_id, enriched_chunks, batch_size=3)
                all_episode_uuids.extend(enriched_uuids)
                enriched_chunks_count = len(enriched_chunks)
                logger.info(f"NBA富化文本已追加注入: {enriched_chunks_count} chunks")

            _update(12, msg["wait_graph"])
            graph_service._wait_for_episodes(all_episode_uuids, timeout=120)

            steps[-1].update({
                "status": "completed",
                "details": {
                    "core_chunks": len(core_chunks),
                    "enriched_chunks": enriched_chunks_count,
                    "total_episodes": len(all_episode_uuids),
                },
            })
            _stop_timer(step_counter)
            step_counter += 1
            _update(15, msg["graph_process_done"])

            # ── 图谱构建完成 + 获取可视化数据 ──
            _start_timer(step_counter)
            _update(16, msg["fetch_graph_data"], {
                "step": step_counter, "title": msg["step5_title"], "status": "running",
                "desc": msg["step5_desc"],
            })
            try:
                raw_graph = graph_service.get_graph_data(graph_id)
                graph_data_for_frontend = {
                    "nodes": raw_graph.get("nodes", []),
                    "edges": raw_graph.get("edges", []),
                    "node_count": raw_graph.get("node_count", 0),
                    "edge_count": raw_graph.get("edge_count", 0),
                }
                # 统计 entity_types 分布
                type_counts = {}
                for n in raw_graph.get("nodes", []):
                    for label in (n.get("labels") or []):
                        if label not in ("Entity", "Node"):
                            type_counts[label] = type_counts.get(label, 0) + 1
                steps[-1].update({
                    "status": "completed",
                    "details": {
                        "node_count": raw_graph.get("node_count", 0),
                        "edge_count": raw_graph.get("edge_count", 0),
                        "entity_type_distribution": type_counts,
                    },
                })
            except Exception as e:
                logger.warning(f"获取图谱数据失败: {e}")
                steps[-1].update({"status": "completed", "details": {"warning": str(e)}})

            # 检索上下文
            query = (
                f"{matchup.away_team.abbreviation} vs {matchup.home_team.abbreviation} "
                f"NBA game prediction matchup analysis"
            )
            search_result = zep_tools.quick_search(graph_id, query, limit=15)
            graph_context = search_result.to_text()

            _stop_timer(step_counter)
            step_counter += 1
            _update(20, msg["graph_ready"])
        else:
            # 普通预测：跳过图谱步骤
            _update(20, msg["graph_ready"])

        # ── 辩论分析 ──
        debate_step_num = step_counter
        _start_timer(debate_step_num)
        debate_step = {
            "step": debate_step_num, "title": msg["step6_title"], "status": "running",
            "desc": msg["step6_desc"],
            "details": {"rounds": [], "current_round": 0, "current_analyst": ""},
        }
        _update(20, msg["start_debate"], debate_step)

        if fast_mode and Config.has_boost_llm():
            debate_llm = LLMClient(
                api_key=Config.LLM_BOOST_API_KEY,
                base_url=Config.LLM_BOOST_BASE_URL,
                model=Config.LLM_BOOST_MODEL_NAME,
            )
            logger.info(f"辩论使用快速模型: {Config.LLM_BOOST_MODEL_NAME}")
        else:
            debate_llm = llm

        engine = DebateEngine(llm_client=debate_llm)
        engine.num_rounds = debate_rounds
        total_calls = engine.num_rounds * len(engine.roles)
        completed_calls = [0]  # mutable for closure

        def debate_progress(message: str, percent: float):
            mapped = 20 + int(percent * 65)
            # 解析当前 round/analyst
            debate_step["details"]["current_round"] = message
            _update(mapped, message)

        debate_result = engine.run_debate(
            matchup_text=matchup.to_full_text(),
            matchup_id=matchup.matchup_id,
            graph_context=graph_context,
            progress_callback=debate_progress,
            lang=lang,
            smart_money_context=smart_money_context,
        )

        # 辩论完成后，将每轮结果摘要放入 step details
        round_summaries = []
        for rd in debate_result.rounds:
            preds = []
            for p in rd.predictions:
                preds.append({
                    "analyst": p.analyst_id,
                    "ml_pick": p.moneyline_pick,
                    "ml_conf": round(p.moneyline_confidence, 2),
                    "spread_pick": p.spread_pick,
                    "total_pick": p.total_pick,
                    "changed": p.changed_from_previous,
                })
            round_summaries.append({
                "round": rd.round_num,
                "predictions": preds,
            })

        debate_step.update({
            "status": "completed",
            "details": {
                "total_llm_calls": debate_result.total_llm_calls,
                "duration_seconds": round(debate_result.total_duration_seconds, 1),
                "rounds": round_summaries,
            },
        })
        _stop_timer(debate_step_num)
        step_counter += 1
        _update(88, msg["debate_done"])

        # ── 生成预测 ──
        gen_step_num = step_counter
        _start_timer(gen_step_num)
        _update(90, msg["gen_prediction"], {
            "step": gen_step_num, "title": msg["step7_title"], "status": "running",
            "desc": msg["step7_desc"],
        })
        generator = PredictionGenerator(llm_client=llm)
        market_odds_dict = matchup.market_odds.to_dict() if matchup.market_odds else None
        prediction_output = generator.generate(
            debate_result,
            market_odds=market_odds_dict,
            home_abbr=matchup.home_team.abbreviation,
            away_abbr=matchup.away_team.abbreviation,
            lang=lang,
        )

        _stop_timer(gen_step_num)
        steps[-1].update({"status": "completed"})

        # ── 清理图谱 ──
        if use_graph and graph_id:
            try:
                graph_service.delete_graph(graph_id)
            except Exception as e:
                logger.warning(f"删除临时图谱失败: {e}")

        # ── 存储结果 ──
        with app.app_context():
            _save_prediction(matchup.matchup_id, prediction_output,
                             graph_data=graph_data_for_frontend,
                             matchup_meta={
                                 "home": matchup.home_team.abbreviation,
                                 "away": matchup.away_team.abbreviation,
                                 "game_date": matchup.game_date or "",
                             },
                             user_id=user_id,
                             task_id=task_id)

        _update(100, msg["complete"])
        total_duration = sum(step_timings.values())
        task_manager.complete_task(task_id, {
            "matchup_id": matchup.matchup_id,
            "total_llm_calls": debate_result.total_llm_calls,
            "duration_seconds": total_duration,
            "step_timings": step_timings,
        })
        logger.info(f"预测完成: matchup={matchup.matchup_id}")

    except Exception as e:
        error_msg = f"{str(e)}\n{traceback.format_exc()}"
        logger.error(f"预测失败: {error_msg}")
        task_manager.fail_task(task_id, str(e))

        # 退还 Token
        if user_id and cost > 0:
            try:
                with app.app_context():
                    from decimal import Decimal as Dec
                    refund_user = User.query.get(user_id)
                    if refund_user:
                        refund_user.token_balance = (refund_user.token_balance or Dec(0)) + Dec(str(cost))
                        refund_tx = TokenTransaction(
                            user_id=user_id,
                            type='refund',
                            amount=Dec(str(cost)),
                            balance=refund_user.token_balance,
                            reference=task_id,
                        )
                        db.session.add(refund_tx)
                        db.session.commit()
                        logger.info(f"预测失败，已退还 {cost} Token 给用户 {user_id}")
            except Exception as refund_err:
                logger.error(f"退款失败: {refund_err}")

        # 尝试清理图谱
        if graph_id:
            try:
                GraphBuilderService().delete_graph(graph_id)
            except Exception:
                pass
