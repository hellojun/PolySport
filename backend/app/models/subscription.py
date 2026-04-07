"""
订阅模型
"""

from datetime import datetime

from ..extensions import db

PLAN_CONFIG = {
    'free':    {'price': 0,    'quota': 3,  'label': 'Free'},
    'basic':   {'price': 19.9, 'quota': 30, 'label': 'Basic'},
    'pro':     {'price': 29.9, 'quota': 50, 'label': 'Pro'},
    'premium': {'price': 39.9, 'quota': 70, 'label': 'Premium'},
}


class Subscription(db.Model):
    __tablename__ = 'subscriptions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False, index=True)
    plan = db.Column(db.String(20), nullable=False)  # basic/pro/premium
    status = db.Column(db.String(20), default='active', nullable=False)  # active/expired
    period_start = db.Column(db.DateTime, nullable=False)
    period_end = db.Column(db.DateTime, nullable=False)  # start + 30 days
    quota = db.Column(db.Integer, nullable=False)  # total quota for this period
    used = db.Column(db.Integer, default=0, nullable=False)  # used in this period
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    @property
    def remaining(self) -> int:
        return max(0, self.quota - self.used)

    @property
    def is_active(self) -> bool:
        return self.status == 'active' and self.period_end > datetime.utcnow()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "plan": self.plan,
            "plan_label": PLAN_CONFIG.get(self.plan, {}).get('label', self.plan),
            "status": self.status,
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "period_end": self.period_end.isoformat() if self.period_end else None,
            "quota": self.quota,
            "used": self.used,
            "remaining": self.remaining,
            "is_active": self.is_active,
        }
