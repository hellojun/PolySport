"""
充值订单 & Token 流水模型
"""

import uuid
from datetime import datetime
from decimal import Decimal

from ..extensions import db


class DepositOrder(db.Model):
    __tablename__ = 'deposit_orders'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    order_no = db.Column(db.String(64), unique=True, nullable=False, index=True)
    amount_usdt = db.Column(db.Numeric(18, 6), nullable=False)
    tokens_credit = db.Column(db.Numeric(18, 6), nullable=False)
    tx_hash = db.Column(db.String(128), unique=True, nullable=True)
    from_address = db.Column(db.String(64), nullable=True)
    status = db.Column(db.String(20), default='pending', nullable=False)  # pending/confirming/completed/failed
    confirmations = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    confirmed_at = db.Column(db.DateTime, nullable=True)

    @staticmethod
    def generate_order_no() -> str:
        return f"DEP-{uuid.uuid4().hex[:16].upper()}"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "order_no": self.order_no,
            "amount_usdt": float(self.amount_usdt),
            "tokens_credit": float(self.tokens_credit),
            "tx_hash": self.tx_hash,
            "from_address": self.from_address,
            "status": self.status,
            "confirmations": self.confirmations,
            "created_at": self.created_at.isoformat(),
            "confirmed_at": self.confirmed_at.isoformat() if self.confirmed_at else None,
        }


class TokenTransaction(db.Model):
    __tablename__ = 'token_transactions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    type = db.Column(db.String(30), nullable=False)  # deposit/predict_normal/predict_premium/refund
    amount = db.Column(db.Numeric(18, 6), nullable=False)  # 正=充值, 负=消费
    balance = db.Column(db.Numeric(18, 6), nullable=False)  # 交易后余额
    reference = db.Column(db.String(128), nullable=True)  # order_no 或 task_id
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "amount": float(self.amount),
            "balance": float(self.balance),
            "reference": self.reference,
            "created_at": self.created_at.isoformat(),
        }
