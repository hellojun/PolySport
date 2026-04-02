"""
Redis → PostgreSQL 数据迁移脚本

将 Redis 中的历史 task 和 prediction 数据迁移到 PG，
所有记录归属到唯一用户 hellojun0699@gmail.com。

运行方式:
    cd backend && .venv/bin/python -m scripts.migrate_redis_to_pg
"""

import json
import sys
import os

# 确保 backend 目录在 path 中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.prediction_task import PredictionTask
from app.models.prediction import Prediction
from app.utils.redis_client import get_redis

TARGET_EMAIL = "hellojun0699@gmail.com"
TASK_PREFIX = "task:"
PREDICTION_PREFIX = "prediction:"


def migrate():
    app = create_app()

    with app.app_context():
        # 1. 查找目标用户
        user = User.query.filter_by(email=TARGET_EMAIL).first()
        if not user:
            print(f"[ERROR] 用户 {TARGET_EMAIL} 不存在，请先注册。")
            sys.exit(1)

        user_id = user.id
        print(f"[INFO] 目标用户: {TARGET_EMAIL} (id={user_id})")

        r = get_redis()
        if r is None:
            print("[ERROR] Redis 连接失败")
            sys.exit(1)

        # 2. 迁移 task:* → prediction_tasks
        task_count = 0
        task_skip = 0
        cursor = 0
        task_matchup_map = {}  # task_id → matchup_id

        while True:
            cursor, keys = r.scan(cursor, match=f"{TASK_PREFIX}*", count=100)
            for key in keys:
                raw = r.get(key)
                if not raw:
                    continue
                try:
                    data = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    continue

                task_id = data.get("task_id")
                if not task_id:
                    continue

                # 记录 matchup_id 映射
                meta = data.get("metadata", {})
                matchup_id = meta.get("matchup_id")
                if matchup_id:
                    task_matchup_map[task_id] = matchup_id

                # 检查是否已存在
                existing = db.session.get(PredictionTask, task_id)
                if existing:
                    task_skip += 1
                    continue

                from datetime import datetime
                created_at = data.get("created_at")
                updated_at = data.get("updated_at")
                if isinstance(created_at, str):
                    try:
                        created_at = datetime.fromisoformat(created_at)
                    except ValueError:
                        created_at = datetime.utcnow()
                if isinstance(updated_at, str):
                    try:
                        updated_at = datetime.fromisoformat(updated_at)
                    except ValueError:
                        updated_at = datetime.utcnow()

                # 将 user_id 写入 metadata
                meta["user_id"] = user_id

                pt = PredictionTask(
                    id=task_id,
                    task_type=data.get("task_type", "prediction"),
                    user_id=user_id,
                    status=data.get("status", "completed"),
                    progress=data.get("progress", 0),
                    message=data.get("message", ""),
                    result=data.get("result"),
                    error=data.get("error"),
                    metadata_=meta,
                    progress_detail=data.get("progress_detail", {}),
                    created_at=created_at,
                    updated_at=updated_at,
                )
                db.session.add(pt)
                task_count += 1

            if cursor == 0:
                break

        if task_count > 0:
            db.session.commit()
        print(f"[INFO] Tasks 迁移: {task_count} 条新增, {task_skip} 条已存在跳过")

        # 3. 迁移 prediction:* → predictions
        pred_count = 0
        pred_skip = 0
        cursor = 0

        # 构建反向映射 matchup_id → task_id
        matchup_to_task = {v: k for k, v in task_matchup_map.items()}

        while True:
            cursor, keys = r.scan(cursor, match=f"{PREDICTION_PREFIX}*", count=100)
            for key in keys:
                raw = r.get(key)
                if not raw:
                    continue
                try:
                    data = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    continue

                # 从 key 提取 matchup_id
                matchup_id = key[len(PREDICTION_PREFIX):]
                if not matchup_id:
                    continue

                # 检查是否已存在
                existing = Prediction.query.filter_by(matchup_id=matchup_id).first()
                if existing:
                    pred_skip += 1
                    continue

                # 关联 task_id
                linked_task_id = matchup_to_task.get(matchup_id)

                pred = Prediction(
                    matchup_id=matchup_id,
                    user_id=user_id,
                    task_id=linked_task_id,
                    data=data,
                )
                db.session.add(pred)
                pred_count += 1

            if cursor == 0:
                break

        if pred_count > 0:
            db.session.commit()
        print(f"[INFO] Predictions 迁移: {pred_count} 条新增, {pred_skip} 条已存在跳过")

        print(f"\n[DONE] 迁移完成！")
        print(f"  prediction_tasks: {task_count} 新增")
        print(f"  predictions:      {pred_count} 新增")
        print(f"  目标用户:         {TARGET_EMAIL} (id={user_id})")


if __name__ == "__main__":
    migrate()
