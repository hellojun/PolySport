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
    token_balance = db.Column(db.Numeric(18, 6), default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def to_dict(self) -> dict:
        from ..config import Config
        perms = []
        if not Config.TRACK_RECORD_WHITELIST or (self.email or '').lower() in Config.TRACK_RECORD_WHITELIST:
            perms.append('track_record')
        return {
            "id": self.id,
            "email": self.email,
            "is_verified": self.is_verified,
            "token_balance": float(self.token_balance or 0),
            "created_at": self.created_at.isoformat(),
            "permissions": perms,
        }
