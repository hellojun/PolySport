"""
任务状态管理
三层存储：内存（活跃任务快速读写）+ Redis（缓存层）+ PostgreSQL（持久化层）
活跃任务（pending/processing）使用内存+Redis；终态任务写入PG后从内存移除。
"""

import json
import uuid
import threading
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass, field


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"          # 等待中
    PROCESSING = "processing"    # 处理中
    COMPLETED = "completed"      # 已完成
    FAILED = "failed"            # 失败


@dataclass
class Task:
    """任务数据类"""
    task_id: str
    task_type: str
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    progress: int = 0              # 总进度百分比 0-100
    message: str = ""              # 状态消息
    result: Optional[Dict] = None  # 任务结果
    error: Optional[str] = None    # 错误信息
    metadata: Dict = field(default_factory=dict)  # 额外元数据
    progress_detail: Dict = field(default_factory=dict)  # 详细进度信息

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "progress": self.progress,
            "message": self.message,
            "progress_detail": self.progress_detail,
            "result": self.result,
            "error": self.error,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        """从字典反序列化"""
        return cls(
            task_id=data["task_id"],
            task_type=data["task_type"],
            status=TaskStatus(data["status"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            progress=data.get("progress", 0),
            message=data.get("message", ""),
            result=data.get("result"),
            error=data.get("error"),
            metadata=data.get("metadata", {}),
            progress_detail=data.get("progress_detail", {}),
        )


class TaskManager:
    """
    任务管理器
    线程安全的任务状态管理，三层存储：内存 + Redis + PostgreSQL
    """

    _instance = None
    _lock = threading.Lock()

    REDIS_PREFIX = "task:"

    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._tasks: Dict[str, Task] = {}
                    cls._instance._task_lock = threading.Lock()
                    cls._instance._app = None
        return cls._instance

    def set_app(self, app):
        """设置 Flask app 引用，供 worker 线程使用 app context"""
        self._app = app

    def _get_app_context(self):
        """获取 app context（优先 current_app，fallback 到缓存的 _app）"""
        try:
            from flask import current_app
            current_app._get_current_object()
            return current_app.app_context()
        except RuntimeError:
            if self._app:
                return self._app.app_context()
        return None

    def _get_redis(self):
        from ..utils.redis_client import get_redis
        return get_redis()

    def _save_to_redis(self, task: Task):
        """保存任务到 Redis"""
        r = self._get_redis()
        from ..config import Config
        key = f"{self.REDIS_PREFIX}{task.task_id}"
        r.set(key, json.dumps(task.to_dict(), ensure_ascii=False), ex=Config.PREDICTION_TTL)

    def _load_from_redis(self, task_id: str) -> Optional[Task]:
        """从 Redis 加载任务"""
        r = self._get_redis()
        key = f"{self.REDIS_PREFIX}{task_id}"
        data = r.get(key)
        if data:
            return Task.from_dict(json.loads(data))
        return None

    # ── PostgreSQL 操作 ──

    def _save_to_pg(self, task: Task, is_create: bool = False):
        """保存任务到 PostgreSQL"""
        ctx = self._get_app_context()
        if ctx is None:
            return
        try:
            with ctx:
                from ..extensions import db
                from .prediction_task import PredictionTask
                if is_create:
                    pg_task = PredictionTask(
                        id=task.task_id,
                        task_type=task.task_type,
                        user_id=task.metadata.get("user_id"),
                        status=task.status.value,
                        progress=task.progress,
                        message=task.message,
                        result=task.result,
                        error=task.error,
                        metadata_=task.metadata,
                        progress_detail=task.progress_detail,
                        created_at=task.created_at,
                        updated_at=task.updated_at,
                    )
                    db.session.add(pg_task)
                else:
                    pg_task = db.session.get(PredictionTask, task.task_id)
                    if pg_task:
                        pg_task.status = task.status.value
                        pg_task.progress = task.progress
                        pg_task.message = task.message
                        pg_task.result = task.result
                        pg_task.error = task.error
                        pg_task.metadata_ = task.metadata
                        pg_task.progress_detail = task.progress_detail
                        pg_task.updated_at = task.updated_at
                db.session.commit()
        except Exception as e:
            from ..utils.logger import get_logger
            get_logger('mirofish.task').warning(f"PG 写入失败 (task={task.task_id}): {e}")

    def _load_from_pg(self, task_id: str) -> Optional[Task]:
        """从 PostgreSQL 加载任务"""
        ctx = self._get_app_context()
        if ctx is None:
            return None
        try:
            with ctx:
                from .prediction_task import PredictionTask
                from ..extensions import db
                pg_task = db.session.get(PredictionTask, task_id)
                if pg_task:
                    return Task(
                        task_id=pg_task.id,
                        task_type=pg_task.task_type,
                        status=TaskStatus(pg_task.status),
                        created_at=pg_task.created_at,
                        updated_at=pg_task.updated_at,
                        progress=pg_task.progress or 0,
                        message=pg_task.message or "",
                        result=pg_task.result,
                        error=pg_task.error,
                        metadata=pg_task.metadata_ or {},
                        progress_detail=pg_task.progress_detail or {},
                    )
        except Exception as e:
            from ..utils.logger import get_logger
            get_logger('mirofish.task').warning(f"PG 读取失败 (task={task_id}): {e}")
        return None

    def _delete_from_pg(self, task_id: str):
        """从 PostgreSQL 删除任务及关联预测"""
        ctx = self._get_app_context()
        if ctx is None:
            return
        try:
            with ctx:
                from ..extensions import db
                from .prediction_task import PredictionTask
                from .prediction import Prediction
                # 删除关联的 prediction 记录
                Prediction.query.filter_by(task_id=task_id).delete()
                # 删除 task 记录
                pg_task = db.session.get(PredictionTask, task_id)
                if pg_task:
                    db.session.delete(pg_task)
                db.session.commit()
        except Exception as e:
            from ..utils.logger import get_logger
            get_logger('mirofish.task').warning(f"PG 删除失败 (task={task_id}): {e}")

    # ── 公共接口 ──

    def create_task(self, task_type: str, metadata: Optional[Dict] = None, user_id=None) -> str:
        """
        创建新任务：写内存 + Redis + PG

        Args:
            task_type: 任务类型
            metadata: 额外元数据
            user_id: 关联的用户ID

        Returns:
            任务ID
        """
        task_id = str(uuid.uuid4())
        now = datetime.now()

        meta = metadata or {}
        if user_id is not None:
            meta["user_id"] = user_id

        task = Task(
            task_id=task_id,
            task_type=task_type,
            status=TaskStatus.PENDING,
            created_at=now,
            updated_at=now,
            metadata=meta
        )

        with self._task_lock:
            self._tasks[task_id] = task

        self._save_to_redis(task)
        self._save_to_pg(task, is_create=True)

        # 维护 user_tasks:<user_id> Set（兼容旧逻辑）
        if user_id is not None:
            r = self._get_redis()
            r.sadd(f"user_tasks:{user_id}", task_id)

        return task_id

    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务：内存 → Redis → PG（三级 fallback）"""
        with self._task_lock:
            task = self._tasks.get(task_id)
            if task:
                return task

        # 内存中没有，从 Redis 加载
        task = self._load_from_redis(task_id)
        if task:
            with self._task_lock:
                self._tasks[task_id] = task
            return task

        # Redis 中也没有，从 PG 加载
        task = self._load_from_pg(task_id)
        if task:
            # 活跃任务回填内存；终态任务不回填（避免内存膨胀）
            if task.status in (TaskStatus.PENDING, TaskStatus.PROCESSING):
                with self._task_lock:
                    self._tasks[task_id] = task
        return task

    def update_task(
        self,
        task_id: str,
        status: Optional[TaskStatus] = None,
        progress: Optional[int] = None,
        message: Optional[str] = None,
        result: Optional[Dict] = None,
        error: Optional[str] = None,
        progress_detail: Optional[Dict] = None
    ):
        """
        更新任务状态：写内存 + Redis（高频更新不走PG）
        """
        with self._task_lock:
            task = self._tasks.get(task_id)
            if task:
                task.updated_at = datetime.now()
                if status is not None:
                    task.status = status
                if progress is not None:
                    task.progress = progress
                if message is not None:
                    task.message = message
                if result is not None:
                    task.result = result
                if error is not None:
                    task.error = error
                if progress_detail is not None:
                    task.progress_detail = progress_detail

        if task:
            self._save_to_redis(task)

    def complete_task(self, task_id: str, result: Dict):
        """标记任务完成：写内存 + Redis + PG，然后从内存移除"""
        self.update_task(
            task_id,
            status=TaskStatus.COMPLETED,
            progress=100,
            message="任务完成",
            result=result
        )
        # 终态写入 PG
        with self._task_lock:
            task = self._tasks.get(task_id)
        if task:
            self._save_to_pg(task)
            # 从内存移除，减少内存占用
            with self._task_lock:
                self._tasks.pop(task_id, None)

    def fail_task(self, task_id: str, error: str):
        """标记任务失败：写内存 + Redis + PG，然后从内存移除"""
        self.update_task(
            task_id,
            status=TaskStatus.FAILED,
            message="任务失败",
            error=error
        )
        # 终态写入 PG
        with self._task_lock:
            task = self._tasks.get(task_id)
        if task:
            self._save_to_pg(task)
            with self._task_lock:
                self._tasks.pop(task_id, None)

    def list_tasks(self, task_type: Optional[str] = None, user_id=None) -> list:
        """
        列出任务：PG + Redis + 内存三层合并。
        PG 为持久化权威来源，Redis 兼容尚未迁移的旧数据，内存覆盖活跃任务。
        如果提供 user_id 则只返回该用户的任务。
        """
        merged: Dict[str, dict] = {}

        # 1. 从 Redis 扫描（兼容未迁移的旧数据）
        r = self._get_redis()
        if user_id is not None:
            task_ids = r.smembers(f"user_tasks:{user_id}")
            for tid in task_ids:
                data = r.get(f"{self.REDIS_PREFIX}{tid}")
                if data:
                    try:
                        t = json.loads(data)
                        merged[t["task_id"]] = t
                    except (json.JSONDecodeError, KeyError):
                        pass
        else:
            cursor = 0
            while True:
                cursor, keys = r.scan(cursor, match=f"{self.REDIS_PREFIX}*", count=100)
                for key in keys:
                    data = r.get(key)
                    if data:
                        try:
                            t = json.loads(data)
                            merged[t["task_id"]] = t
                        except (json.JSONDecodeError, KeyError):
                            pass
                if cursor == 0:
                    break

        # 2. PG 覆盖（持久化权威来源，优先级高于 Redis）
        ctx = self._get_app_context()
        if ctx:
            try:
                with ctx:
                    from .prediction_task import PredictionTask
                    query = PredictionTask.query
                    if user_id is not None:
                        query = query.filter_by(user_id=user_id)
                    if task_type:
                        query = query.filter_by(task_type=task_type)
                    query = query.order_by(PredictionTask.created_at.desc())
                    for pt in query.all():
                        merged[pt.id] = pt.to_task_dict()
            except Exception as e:
                from ..utils.logger import get_logger
                get_logger('mirofish.task').warning(f"PG list_tasks 查询失败: {e}")

        # 3. 内存中的活跃任务覆盖（最高优先级，最实时）
        with self._task_lock:
            for tid, task in self._tasks.items():
                task_dict = task.to_dict()
                meta = task.metadata or {}
                if user_id is not None and meta.get("user_id") != user_id:
                    continue
                if task_type and task.task_type != task_type:
                    continue
                merged[tid] = task_dict

        tasks = list(merged.values())
        if task_type:
            tasks = [t for t in tasks if t.get("task_type") == task_type]
        return sorted(tasks, key=lambda x: x.get("created_at", ""), reverse=True)

    def delete_task(self, task_id: str, user_id=None) -> bool:
        """删除任务：内存 + Redis + PG + 关联 predictions"""
        with self._task_lock:
            self._tasks.pop(task_id, None)
        r = self._get_redis()
        key = f"{self.REDIS_PREFIX}{task_id}"
        deleted = bool(r.delete(key))
        if user_id is not None:
            r.srem(f"user_tasks:{user_id}", task_id)
        # 删除 PG 记录
        self._delete_from_pg(task_id)
        return deleted

    def cleanup_old_tasks(self, max_age_hours: int = 24):
        """清理内存中的旧任务（PG 中保留，不受影响）"""
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(hours=max_age_hours)

        with self._task_lock:
            old_ids = [
                tid for tid, task in self._tasks.items()
                if task.created_at < cutoff and task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]
            ]
            for tid in old_ids:
                del self._tasks[tid]
