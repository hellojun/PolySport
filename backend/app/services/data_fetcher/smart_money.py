"""
聪明钱链上数据服务

1. 排行榜拉取：每月 1 号自动从 Polymarket 体育赛道排行榜拉取 top 50 盈利地址（API 上限）
2. 持仓查询：查询这些地址在指定 NBA 市场的持仓
3. 缓存：排行榜数据缓存为本地 JSON 文件，避免重复拉取
"""

import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

import requests

from ...config import Config
from ...utils.logger import get_logger

logger = get_logger('mirofish.data_fetcher.smart_money')

# ── 排行榜缓存路径 ──
_CACHE_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data')
_CACHE_FILE = os.path.join(_CACHE_DIR, 'smart_money_leaderboard.json')

# ── Polymarket 排行榜 API ──
_LB_API_URL = "https://lb-api.polymarket.com/profit"
_LB_PARAMS = {"window": "30d", "limit": 50, "offset": 0, "tag": "sports"}


# ────────────────────────────────────────
#  排行榜拉取与缓存
# ────────────────────────────────────────

def _fetch_leaderboard() -> List[Dict[str, Any]]:
    """
    从 Polymarket 体育赛道排行榜 API 拉取 top 50（API 上限）。
    返回 [{"address": ..., "alias": ..., "profit_usd": ...}, ...]
    """
    resp = requests.get(
        _LB_API_URL,
        params=_LB_PARAMS,
        timeout=Config.SMART_MONEY_TIMEOUT,
    )
    resp.raise_for_status()
    raw = resp.json()

    entries = []
    for i, item in enumerate(raw):
        address = item.get("proxyWallet", "")
        alias = item.get("name") or item.get("pseudonym") or f"Wallet #{i+1}"
        profit = item.get("amount", 0)
        entries.append({
            "address": address.lower(),
            "alias": alias,
            "profit_usd": round(profit, 2),
            "rank": i + 1,
        })

    return entries


def _save_cache(entries: List[Dict[str, Any]]):
    """将排行榜数据写入缓存文件"""
    os.makedirs(_CACHE_DIR, exist_ok=True)
    data = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": _LB_API_URL,
        "count": len(entries),
        "entries": entries,
    }
    with open(_CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"排行榜缓存已保存: {len(entries)} 条, {_CACHE_FILE}")


def _load_cache() -> Optional[Dict[str, Any]]:
    """读取缓存文件，返回 None 如果文件不存在"""
    if not os.path.exists(_CACHE_FILE):
        return None
    try:
        with open(_CACHE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"缓存文件读取失败: {e}")
        return None


def _cache_needs_refresh() -> bool:
    """
    判断缓存是否需要刷新：
    - 缓存不存在 → 需要
    - 缓存是上个月（或更早）的数据 → 需要
    """
    cache = _load_cache()
    if not cache:
        return True

    fetched_at = cache.get("fetched_at", "")
    if not fetched_at:
        return True

    try:
        fetched_dt = datetime.fromisoformat(fetched_at)
        now = datetime.now(timezone.utc)
        # 如果拉取时间和当前不在同一个月 → 需要刷新
        if fetched_dt.year != now.year or fetched_dt.month != now.month:
            return True
    except (ValueError, TypeError):
        return True

    return False


def refresh_leaderboard():
    """拉取排行榜并更新缓存。供启动检查和定时任务调用。"""
    try:
        logger.info("开始拉取 Polymarket 体育赛道排行榜 (top 50)...")
        entries = _fetch_leaderboard()
        if entries:
            _save_cache(entries)
            logger.info(f"排行榜刷新完成: {len(entries)} 个地址, "
                        f"Top1: {entries[0]['alias']} (${entries[0]['profit_usd']:,.0f})")
        else:
            logger.warning("排行榜返回为空，保留旧缓存")
    except Exception as e:
        logger.warning(f"排行榜拉取失败: {e}，保留旧缓存")


def check_and_refresh_on_startup():
    """
    启动时检查：如果缓存不存在或属于上个月的数据，后台线程刷新。
    不阻塞 Flask 启动。
    """
    if not Config.SMART_MONEY_ENABLED:
        return

    if _cache_needs_refresh():
        logger.info("聪明钱排行榜缓存需要刷新，启动后台拉取...")
        t = threading.Thread(target=refresh_leaderboard, daemon=True)
        t.start()
    else:
        cache = _load_cache()
        count = cache.get("count", 0) if cache else 0
        fetched_at = cache.get("fetched_at", "?") if cache else "?"
        logger.info(f"聪明钱排行榜缓存有效: {count} 条, 拉取时间 {fetched_at}")


def get_smart_money_addresses() -> List[Dict[str, str]]:
    """
    返回聪明钱地址列表（从缓存读取）。
    如果缓存不存在返回空列表。
    """
    cache = _load_cache()
    if not cache:
        return []
    return cache.get("entries", [])


# ────────────────────────────────────────
#  定时任务（每月 1 号刷新）
# ────────────────────────────────────────

_scheduler_started = False


def start_monthly_scheduler():
    """
    启动后台线程，每天检查一次，如果是当月 1 号且缓存不是本月的就刷新。
    轻量实现，无需额外依赖。
    """
    global _scheduler_started
    if _scheduler_started:
        return
    _scheduler_started = True

    def _scheduler_loop():
        while True:
            # 每 12 小时检查一次
            time.sleep(12 * 3600)
            try:
                now = datetime.now(timezone.utc)
                if now.day == 1 and _cache_needs_refresh():
                    logger.info("月度定时任务触发：刷新聪明钱排行榜")
                    refresh_leaderboard()
            except Exception as e:
                logger.warning(f"定时任务异常: {e}")

    t = threading.Thread(target=_scheduler_loop, daemon=True, name="smart_money_scheduler")
    t.start()
    logger.info("聪明钱排行榜月度定时任务已启动")


# ────────────────────────────────────────
#  SmartMoneyService
# ────────────────────────────────────────

class SmartMoneyService:
    """查询聪明钱地址在 Polymarket 指定市场的持仓"""

    CLOB_BASE_URL = "https://clob.polymarket.com"

    def __init__(self):
        self.timeout = Config.SMART_MONEY_TIMEOUT
        self.addresses = get_smart_money_addresses()

    def fetch_positions(self, condition_id: str, token_ids: List[str]) -> Dict[str, Any]:
        """
        查询聪明钱地址在指定市场的持仓。

        Args:
            condition_id: Polymarket 市场的 conditionId
            token_ids: 市场的 outcome token IDs [token_0, token_1]

        Returns:
            聪明钱持仓数据字典
        """
        if not self.addresses:
            return {
                "status": "unavailable",
                "reason": "No smart money addresses loaded (leaderboard not yet fetched)",
                "tracked_wallets": 0,
                "wallets_with_position": 0,
                "positions": [],
                "summary": {},
            }

        if not condition_id or not token_ids:
            return {
                "status": "unavailable",
                "reason": "Missing condition_id or token_ids",
                "tracked_wallets": len(self.addresses),
                "wallets_with_position": 0,
                "positions": [],
                "summary": {},
            }

        positions = []
        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = {
                pool.submit(
                    self._query_wallet_position,
                    wallet["address"], wallet.get("alias", ""), token_ids,
                ): wallet
                for wallet in self.addresses
            }
            for future in as_completed(futures):
                wallet = futures[future]
                try:
                    pos = future.result()
                    if pos:
                        positions.append(pos)
                except Exception as e:
                    logger.debug(f"查询钱包 {wallet.get('alias', '')} 失败: {e}")
                    continue

        # 计算 summary
        summary = self._build_summary(positions)

        # 多数方向
        direction_split = summary.get("direction_split", {})
        majority_direction = ""
        if direction_split:
            majority_direction = max(direction_split, key=direction_split.get)

        return {
            "status": "ok",
            "tracked_wallets": len(self.addresses),
            "wallets_with_position": len(positions),
            "majority_direction": majority_direction,
            "positions": positions,
            "summary": summary,
        }

    def _query_wallet_position(
        self, address: str, alias: str, token_ids: List[str]
    ) -> Optional[Dict[str, Any]]:
        """
        通过 Polymarket CLOB API 查询单个地址的持仓。
        GET /data/position?user=<address>&token=<token_id>
        """
        best_position = None
        best_size = 0.0

        for i, token_id in enumerate(token_ids):
            try:
                resp = requests.get(
                    f"{self.CLOB_BASE_URL}/data/position",
                    params={"user": address, "token": token_id},
                    timeout=self.timeout,
                )
                if resp.status_code != 200:
                    continue

                data = resp.json()
                size = float(data.get("size", 0))
                if size <= 0:
                    continue

                avg_price = float(data.get("avgPrice", 0))
                current_price = float(data.get("currentPrice", 0))

                if size > best_size:
                    best_size = size
                    best_position = {
                        "address": address,
                        "alias": alias,
                        "token_index": i,
                        "size_usd": round(size * avg_price, 2) if avg_price else round(size, 2),
                        "size_shares": round(size, 2),
                        "avg_entry_price": round(avg_price, 4),
                        "current_price": round(current_price, 4),
                    }
            except Exception as e:
                logger.debug(f"CLOB position query failed for {alias}: {e}")
                continue

        return best_position

    def _build_summary(self, positions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """从持仓列表构建统计摘要"""
        if not positions:
            return {}

        total_usd = sum(p.get("size_usd", 0) for p in positions)
        direction_split: Dict[str, int] = {}
        for p in positions:
            idx = p.get("token_index", 0)
            direction = f"outcome_{idx}"
            direction_split[direction] = direction_split.get(direction, 0) + 1

        return {
            "total_smart_money_usd": round(total_usd, 2),
            "direction_split": direction_split,
            "num_positions": len(positions),
        }

    def to_context_text(
        self,
        data: Dict[str, Any],
        home_abbr: str = "",
        away_abbr: str = "",
    ) -> str:
        """
        将持仓数据转为自然语言文本，注入到聪明钱分析师 prompt。

        Args:
            data: fetch_positions 的返回值
            home_abbr: 主队缩写（用于将 token_index 映射为球队）
            away_abbr: 客队缩写
        """
        status = data.get("status", "unavailable")
        if status != "ok":
            reason = data.get("reason", "Unknown error")
            return (
                f"[Smart Money Data - UNAVAILABLE]\n"
                f"On-chain smart money data is currently unavailable. Reason: {reason}\n"
                f"Please base your analysis on market odds and trading volume instead."
            )

        positions = data.get("positions", [])
        tracked = data.get("tracked_wallets", 0)
        with_pos = data.get("wallets_with_position", 0)

        if not positions:
            return (
                f"[Smart Money Data]\n"
                f"Tracked {tracked} sport-focused smart money wallets on Polymarket.\n"
                f"None of the tracked wallets hold positions in this market.\n"
                f"This may indicate smart money sees no clear edge in this game."
            )

        # 将 token_index 映射为球队（Polymarket 惯例：index 0 = away, index 1 = home）
        team_map = {0: away_abbr or "Outcome_0", 1: home_abbr or "Outcome_1"}

        lines = [
            f"[Smart Money Data]",
            f"Tracked {tracked} sport-focused smart money wallets (Polymarket top 100 monthly profit). "
            f"{with_pos} wallet(s) hold positions in this market.",
            "",
        ]

        # 方向统计
        summary = data.get("summary", {})
        direction_split = summary.get("direction_split", {})
        if direction_split:
            split_parts = []
            for key, count in direction_split.items():
                idx = int(key.split("_")[-1]) if "_" in key else 0
                team = team_map.get(idx, key)
                split_parts.append(f"{team}: {count}")
            lines.append(f"Direction split: {', '.join(split_parts)}")

        total_usd = summary.get("total_smart_money_usd", 0)
        if total_usd:
            lines.append(f"Total smart money exposure: ${total_usd:,.0f}")

        lines.append("")
        lines.append("Individual positions:")

        for p in positions:
            idx = p.get("token_index", 0)
            team = team_map.get(idx, f"Outcome_{idx}")
            alias = p.get("alias", p.get("address", "")[:10])
            size_usd = p.get("size_usd", 0)
            avg_price = p.get("avg_entry_price", 0)
            current = p.get("current_price", 0)

            line = (
                f"- {alias}: {team}, "
                f"${size_usd:,.0f} position, "
                f"entry price {avg_price:.2f}, "
                f"current price {current:.2f}"
            )
            lines.append(line)

        # 多数方向
        majority = data.get("majority_direction", "")
        if majority:
            if "_" in majority:
                idx = int(majority.split("_")[-1])
                majority_team = team_map.get(idx, majority)
            else:
                majority_team = majority
            lines.append(f"\nMajority direction: {majority_team}")

        return "\n".join(lines)
