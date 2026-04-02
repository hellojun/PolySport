"""
预测任务 PG 模型
持久化存储任务状态，替代纯 Redis 方案
"""

from datetime import datetime

from ..extensions import db


class PredictionTask(db.Model):
    __tablename__ = 'prediction_tasks'

    id = db.Column(db.String(36), primary_key=True)                   # UUID task_id
    task_type = db.Column(db.String(50), nullable=False)               # "prediction"
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    status = db.Column(db.String(20), nullable=False, default='pending')
    progress = db.Column(db.Integer, default=0)
    message = db.Column(db.Text, default='')
    result = db.Column(db.JSON, nullable=True)                         # 任务完成后的摘要
    error = db.Column(db.Text, nullable=True)
    metadata_ = db.Column('metadata', db.JSON, default=dict)           # matchup_id, home, away 等
    progress_detail = db.Column(db.JSON, default=dict)                 # steps 详细进度
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.Index('ix_prediction_tasks_user_id', 'user_id'),
        db.Index('ix_prediction_tasks_status', 'status'),
        db.Index('ix_prediction_tasks_created_at', created_at.desc()),
    )

    def to_task_dict(self) -> dict:
        """转换为与 Task dataclass 兼容的字典格式"""
        return {
            "task_id": self.id,
            "task_type": self.task_type,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else "",
            "updated_at": self.updated_at.isoformat() if self.updated_at else "",
            "progress": self.progress or 0,
            "message": self.message or "",
            "progress_detail": self.progress_detail or {},
            "result": self.result,
            "error": self.error,
            "metadata": self.metadata_ or {},
        }
