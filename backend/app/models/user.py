"""
用户模型
"""

from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

from ..extensions import db


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=True)
    google_id = db.Column(db.String(255), unique=True, nullable=True, index=True)
    is_verified = db.Column(db.Boolean, default=True, nullable=False)
    token_balance = db.Column(db.Numeric(18, 6), default=0, nullable=False)  # legacy, kept for migration safety
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    subscription = db.relationship('Subscription', uselist=False, backref='user', lazy='joined')

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def get_active_subscription(self):
        """返回当前有效订阅，过期则标记为 expired 并返回 None"""
        sub = self.subscription
        if not sub:
            return None
        if sub.status == 'active' and sub.period_end > datetime.utcnow():
            return sub
        # 过期 → 标记
        if sub.status == 'active':
            sub.status = 'expired'
            db.session.commit()
        return None

    def get_remaining_quota(self) -> int:
        """返回当前剩余额度（订阅用户查 sub，免费用户查本月已用）"""
        sub = self.get_active_subscription()
        if sub:
            return max(0, sub.quota - sub.used)
        # 免费用户：查本月 free 已用次数
        from ..config import Config
        free_used = self._count_free_predictions_this_month()
        return max(0, Config.FREE_MONTHLY_QUOTA - free_used)

    def can_predict(self) -> bool:
        return self.get_remaining_quota() > 0

    def _count_free_predictions_this_month(self) -> int:
        """统计当前自然月内该用户的免费预测次数（排除旧 token 制度下的预测）"""
        from ..models.prediction_task import PredictionTask
        from ..config import Config
        now = datetime.utcnow()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        # 取订阅制上线时间和本月初的较大值，避免计入旧制度的预测
        cutoff = max(month_start, Config.SUBSCRIPTION_LAUNCH_DATE)
        return PredictionTask.query.filter(
            PredictionTask.user_id == self.id,
            PredictionTask.task_type == 'prediction',
            PredictionTask.status.in_(['completed', 'processing', 'pending']),
            PredictionTask.created_at >= cutoff,
        ).count()

    def to_dict(self) -> dict:
        from ..config import Config
        perms = []
        if not Config.TRACK_RECORD_WHITELIST or (self.email or '').lower() in Config.TRACK_RECORD_WHITELIST:
            perms.append('track_record')
        sub = self.get_active_subscription()
        sub_info = sub.to_dict() if sub else None
        return {
            "id": self.id,
            "email": self.email,
            "is_verified": self.is_verified,
            "token_balance": float(self.token_balance or 0),
            "subscription": sub_info,
            "remaining_quota": self.get_remaining_quota(),
            "created_at": self.created_at.isoformat(),
            "permissions": perms,
        }
