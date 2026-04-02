"""
Flask 扩展实例
在应用工厂中通过 init_app() 初始化
"""

from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager

db = SQLAlchemy()
jwt = JWTManager()
