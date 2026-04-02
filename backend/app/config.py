"""
配置管理
统一从项目根目录的 .env 文件加载配置
"""

import os
from datetime import timedelta
from dotenv import load_dotenv

project_root_env = os.path.join(os.path.dirname(__file__), '../../.env')

if os.path.exists(project_root_env):
    load_dotenv(project_root_env, override=True)
else:
    load_dotenv(override=True)


class Config:
    """Flask配置类"""

    # Flask配置
    SECRET_KEY = os.environ.get('SECRET_KEY', 'mirofish-secret-key')
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'

    JSON_AS_ASCII = False

    # PostgreSQL
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL', 'postgresql://mirofish:mirofish@localhost:5432/mirofish')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'dev-secret-change-me')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=15)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)

    # SMTP
    SMTP_HOST = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
    SMTP_PORT = int(os.environ.get('SMTP_PORT', '587'))
    SMTP_USE_TLS = os.environ.get('SMTP_USE_TLS', 'true').lower() == 'true'
    SMTP_USERNAME = os.environ.get('SMTP_USERNAME', '')
    SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '')
    SMTP_SENDER = os.environ.get('SMTP_SENDER', '')

    # LLM配置
    LLM_API_KEY = os.environ.get('LLM_API_KEY')
    LLM_BASE_URL = os.environ.get('LLM_BASE_URL', 'https://api.openai.com/v1')
    LLM_MODEL_NAME = os.environ.get('LLM_MODEL_NAME', 'gpt-4o-mini')

    # 加速 LLM 配置（用于辩论加速，可选）
    LLM_BOOST_API_KEY = os.environ.get('LLM_BOOST_API_KEY') or None
    LLM_BOOST_BASE_URL = os.environ.get('LLM_BOOST_BASE_URL') or None
    LLM_BOOST_MODEL_NAME = os.environ.get('LLM_BOOST_MODEL_NAME') or None

    @classmethod
    def has_boost_llm(cls) -> bool:
        return bool(cls.LLM_BOOST_API_KEY and cls.LLM_BOOST_MODEL_NAME)

    # Zep配置
    ZEP_API_KEY = os.environ.get('ZEP_API_KEY')

    # 文本处理配置
    DEFAULT_CHUNK_SIZE = 500
    DEFAULT_CHUNK_OVERLAP = 50

    # 辩论引擎配置
    DEBATE_NUM_ROUNDS = 3
    DEBATE_LLM_TEMPERATURE = 0.7
    DEBATE_LLM_MAX_TOKENS = 2048
    GRAPH_CHUNK_SIZE = 500
    GRAPH_CHUNK_OVERLAP = 50

    # NBA API 配置
    NBA_API_ENABLED = os.environ.get('NBA_API_ENABLED', 'true').lower() == 'true'
    NBA_API_TIMEOUT = int(os.environ.get('NBA_API_TIMEOUT', '30'))
    NBA_API_DELAY = float(os.environ.get('NBA_API_DELAY', '0.6'))
    NBA_API_SEASON = os.environ.get('NBA_API_SEASON', '')  # 空=自动推断当前赛季
    NBA_API_PROXY = os.environ.get('NBA_API_PROXY', '')  # e.g. http://user:pass@us-proxy:port

    # NBA CDN 配置 (cdn.nba.com — 替代 stats.nba.com)
    NBA_CDN_SCHEDULE_TTL = int(os.environ.get('NBA_CDN_SCHEDULE_TTL', '3600'))    # 赛程 Redis 缓存 1h
    NBA_CDN_BOXSCORE_TTL = int(os.environ.get('NBA_CDN_BOXSCORE_TTL', '1800'))   # boxscore 缓存 30min
    NBA_CDN_BOXSCORE_COUNT = int(os.environ.get('NBA_CDN_BOXSCORE_COUNT', '7'))  # 每队取最近 N 场
    NBA_CDN_REQUEST_TIMEOUT = int(os.environ.get('NBA_CDN_REQUEST_TIMEOUT', '15'))

    # 聪明钱配置
    SMART_MONEY_ENABLED = os.environ.get('SMART_MONEY_ENABLED', 'true').lower() == 'true'
    SMART_MONEY_TIMEOUT = int(os.environ.get('SMART_MONEY_TIMEOUT', '15'))
    SMART_MONEY_RPC_URL = os.environ.get('SMART_MONEY_RPC_URL', '')

    # Redis 配置
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    PREDICTION_TTL = int(os.environ.get('PREDICTION_TTL', str(7 * 24 * 3600)))  # 默认7天

    # 预测结果存储
    PREDICTION_RESULTS_DIR = os.path.join(os.path.dirname(__file__), '../uploads/predictions')

    # Polygon 链上验证
    POLYGON_RPC_URL = os.environ.get('POLYGON_RPC_URL', 'https://polygon-bor-rpc.publicnode.com')
    POLYGON_USDT_CONTRACT = os.environ.get('POLYGON_USDT_CONTRACT', '0xc2132D05D31c914a87C6611C10748AEb04B58e8F')
    PLATFORM_WALLET_ADDRESS = os.environ.get('PLATFORM_WALLET_ADDRESS', '')
    DEPOSIT_MIN_CONFIRMATIONS = int(os.environ.get('DEPOSIT_MIN_CONFIRMATIONS', '5'))

    # 预测定价 (Token)
    PREDICTION_COST_NORMAL = 2
    PREDICTION_COST_PREMIUM = 4

    @classmethod
    def validate(cls):
        """验证必要配置"""
        errors = []
        if not cls.LLM_API_KEY:
            errors.append("LLM_API_KEY 未配置")
        if not cls.ZEP_API_KEY:
            errors.append("ZEP_API_KEY 未配置")
        return errors
