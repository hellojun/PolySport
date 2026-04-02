"""
Redis 客户端单例
连接失败时打印详细信息后退出进程
"""

import sys
import redis
from ..config import Config
from .logger import get_logger

logger = get_logger('mirofish.redis')

_redis_client = None
_initialized = False


def get_redis() -> redis.Redis:
    """
    获取 Redis 客户端单例。
    首次调用时建立连接，连接失败直接退出进程。
    """
    global _redis_client, _initialized

    if _initialized:
        return _redis_client

    _initialized = True
    url = Config.REDIS_URL
    try:
        client = redis.Redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=3,
        )
        client.ping()
        _redis_client = client
        logger.info(f"Redis 连接成功: {url}")
    except Exception as e:
        logger.error(f"Redis 连接失败，进程退出。URL={url}  错误: {e}")
        print(f"\n[FATAL] Redis 连接失败，无法启动。", file=sys.stderr)
        print(f"  URL:   {url}", file=sys.stderr)
        print(f"  错误:  {e}", file=sys.stderr)
        print(f"  请确认 Redis 已启动且 REDIS_URL 配置正确。\n", file=sys.stderr)
        sys.exit(1)

    return _redis_client
