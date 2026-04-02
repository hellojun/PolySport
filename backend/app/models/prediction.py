"""
预测结果 PG 模型
持久化存储完整预测数据（L3 + graph_data + matchup_meta + game_result）
"""

from datetime import datetime

from ..extensions import db


class Prediction(db.Model):
    __tablename__ = 'predictions'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    matchup_id = db.Column(db.String(100), unique=True, nullable=False)   # 自然键
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    task_id = db.Column(db.String(36), db.ForeignKey('prediction_tasks.id'), nullable=True)
    data = db.Column(db.JSON, nullable=False)      # 完整 L3 预测 + graph_data + matchup_meta + game_result
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.Index('ix_predictions_user_id', 'user_id'),
        db.Index('ix_predictions_task_id', 'task_id'),
    )
