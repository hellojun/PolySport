"""
Zep图谱记忆更新服务
将NBA数据更新动态写入Zep图谱
"""

import time
import threading
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime
from queue import Queue, Empty

from zep_cloud.client import Zep

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger('mirofish.zep_graph_memory_updater')


@dataclass
class NBADataUpdate:
    """NBA 数据更新记录"""
    data_type: str            # "standings" / "player_stats" / "game_result" / "matchup_analysis"
    team_abbreviation: str
    data: Dict[str, Any]
    timestamp: str
    season: Optional[str] = None

    def to_episode_text(self) -> str:
        """转为自然语言文本，供 Zep 图谱提取实体和关系"""
        handlers = {
            "standings": self._describe_standings,
            "player_stats": self._describe_player_stats,
            "game_result": self._describe_game_result,
            "matchup_analysis": self._describe_matchup_analysis,
        }
        handler = handlers.get(self.data_type, self._describe_generic)
        return handler()

    def _describe_standings(self) -> str:
        abbr = self.team_abbreviation
        d = self.data
        w = d.get('wins', '?')
        l = d.get('losses', '?')
        pct = d.get('win_pct', 0)
        conf = d.get('conference', '?')
        rank = d.get('conference_rank', '?')
        streak = d.get('streak', '')
        return (
            f"{abbr} current record is {w}-{l} ({pct:.3f} win rate), "
            f"ranked #{rank} in the {conf} Conference. "
            f"Current streak: {streak}."
        )

    def _describe_player_stats(self) -> str:
        abbr = self.team_abbreviation
        players = self.data.get('players', [])
        if not players:
            return f"{abbr}: No player stats available."
        lines = [f"{abbr} key player stats:"]
        for p in players:
            name = p.get('name', '?')
            ppg = p.get('ppg', 0)
            rpg = p.get('rpg', 0)
            apg = p.get('apg', 0)
            lines.append(f"  {name} averages {ppg} points, {rpg} rebounds, {apg} assists per game.")
        return "\n".join(lines)

    def _describe_game_result(self) -> str:
        abbr = self.team_abbreviation
        d = self.data
        date = d.get('date', '?')
        matchup = d.get('matchup', '?')
        result = d.get('result', '?')
        pts = d.get('pts', '?')
        pm = d.get('plus_minus', 0)
        outcome = 'won' if result == 'W' else 'lost'
        return (
            f"On {date}, {abbr} {outcome} the game ({matchup}) "
            f"scoring {pts} points (point differential: {pm:+d})."
        )

    def _describe_matchup_analysis(self) -> str:
        abbr = self.team_abbreviation
        analysis = self.data.get('analysis', '')
        if analysis:
            return f"{abbr} matchup analysis: {analysis}"
        return f"{abbr}: Matchup analysis data recorded."

    def _describe_generic(self) -> str:
        abbr = self.team_abbreviation
        return f"{abbr}: {self.data_type} data updated at {self.timestamp}."


class ZepGraphMemoryUpdater:
    """
    Zep图谱记忆更新器

    接收 NBADataUpdate 记录，按 data_type 分组批量发送到 Zep 图谱。
    """

    BATCH_SIZE = 5
    SEND_INTERVAL = 0.5
    MAX_RETRIES = 3
    RETRY_DELAY = 2

    def __init__(self, graph_id: str, api_key: Optional[str] = None):
        self.graph_id = graph_id
        self.api_key = api_key or Config.ZEP_API_KEY

        if not self.api_key:
            raise ValueError("ZEP_API_KEY未配置")

        self.client = Zep(api_key=self.api_key)

        self._update_queue: Queue = Queue()

        # 按 data_type 分组的缓冲区
        self._data_type_buffers: Dict[str, List[NBADataUpdate]] = {}
        self._buffer_lock = threading.Lock()

        self._running = False
        self._worker_thread: Optional[threading.Thread] = None

        # 统计
        self._total_updates = 0
        self._total_sent = 0
        self._total_items_sent = 0
        self._failed_count = 0

        logger.info(f"ZepGraphMemoryUpdater 初始化完成: graph_id={graph_id}, batch_size={self.BATCH_SIZE}")

    def start(self):
        """启动后台工作线程"""
        if self._running:
            return

        self._running = True
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name=f"ZepMemoryUpdater-{self.graph_id[:8]}"
        )
        self._worker_thread.start()
        logger.info(f"ZepGraphMemoryUpdater 已启动: graph_id={self.graph_id}")

    def stop(self):
        """停止后台工作线程"""
        self._running = False
        self._flush_remaining()

        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=10)

        logger.info(
            f"ZepGraphMemoryUpdater 已停止: graph_id={self.graph_id}, "
            f"total_updates={self._total_updates}, "
            f"batches_sent={self._total_sent}, "
            f"items_sent={self._total_items_sent}, "
            f"failed={self._failed_count}"
        )

    def add_update(self, update: NBADataUpdate):
        """添加一条 NBA 数据更新到队列"""
        self._update_queue.put(update)
        self._total_updates += 1
        logger.debug(f"添加更新到Zep队列: {update.team_abbreviation} - {update.data_type}")

    def _worker_loop(self):
        """后台工作循环 — 按 data_type 批量发送"""
        while self._running or not self._update_queue.empty():
            try:
                try:
                    update = self._update_queue.get(timeout=1)

                    dtype = update.data_type
                    with self._buffer_lock:
                        if dtype not in self._data_type_buffers:
                            self._data_type_buffers[dtype] = []
                        self._data_type_buffers[dtype].append(update)

                        if len(self._data_type_buffers[dtype]) >= self.BATCH_SIZE:
                            batch = self._data_type_buffers[dtype][:self.BATCH_SIZE]
                            self._data_type_buffers[dtype] = self._data_type_buffers[dtype][self.BATCH_SIZE:]
                            self._send_batch(batch, dtype)
                            time.sleep(self.SEND_INTERVAL)

                except Empty:
                    pass

            except Exception as e:
                logger.error(f"工作循环异常: {e}")
                time.sleep(1)

    def _send_batch(self, updates: List[NBADataUpdate], data_type: str):
        """批量发送更新到 Zep 图谱"""
        if not updates:
            return

        episode_texts = [u.to_episode_text() for u in updates]
        combined_text = "\n".join(episode_texts)

        for attempt in range(self.MAX_RETRIES):
            try:
                self.client.graph.add(
                    graph_id=self.graph_id,
                    type="text",
                    data=combined_text,
                )

                self._total_sent += 1
                self._total_items_sent += len(updates)
                logger.info(f"成功批量发送 {len(updates)} 条 {data_type} 更新到图谱 {self.graph_id}")
                return

            except Exception as e:
                if attempt < self.MAX_RETRIES - 1:
                    logger.warning(f"批量发送到Zep失败 (尝试 {attempt + 1}/{self.MAX_RETRIES}): {e}")
                    time.sleep(self.RETRY_DELAY * (attempt + 1))
                else:
                    logger.error(f"批量发送到Zep失败，已重试{self.MAX_RETRIES}次: {e}")
                    self._failed_count += 1

    def _flush_remaining(self):
        """发送队列和缓冲区中剩余的更新"""
        while not self._update_queue.empty():
            try:
                update = self._update_queue.get_nowait()
                dtype = update.data_type
                with self._buffer_lock:
                    if dtype not in self._data_type_buffers:
                        self._data_type_buffers[dtype] = []
                    self._data_type_buffers[dtype].append(update)
            except Empty:
                break

        with self._buffer_lock:
            for dtype, buffer in self._data_type_buffers.items():
                if buffer:
                    logger.info(f"发送剩余的 {len(buffer)} 条 {dtype} 更新")
                    self._send_batch(buffer, dtype)
            for dtype in self._data_type_buffers:
                self._data_type_buffers[dtype] = []

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._buffer_lock:
            buffer_sizes = {dt: len(b) for dt, b in self._data_type_buffers.items()}

        return {
            "graph_id": self.graph_id,
            "batch_size": self.BATCH_SIZE,
            "total_updates": self._total_updates,
            "batches_sent": self._total_sent,
            "items_sent": self._total_items_sent,
            "failed_count": self._failed_count,
            "queue_size": self._update_queue.qsize(),
            "buffer_sizes": buffer_sizes,
            "running": self._running,
        }


class ZepGraphMemoryManager:
    """
    管理多个预测任务的 Zep 图谱记忆更新器
    """

    _updaters: Dict[str, ZepGraphMemoryUpdater] = {}
    _lock = threading.Lock()

    @classmethod
    def create_updater(cls, prediction_id: str, graph_id: str) -> ZepGraphMemoryUpdater:
        """
        为预测任务创建图谱记忆更新器

        Args:
            prediction_id: 预测任务ID
            graph_id: Zep图谱ID

        Returns:
            ZepGraphMemoryUpdater实例
        """
        with cls._lock:
            if prediction_id in cls._updaters:
                cls._updaters[prediction_id].stop()

            updater = ZepGraphMemoryUpdater(graph_id)
            updater.start()
            cls._updaters[prediction_id] = updater

            logger.info(f"创建图谱记忆更新器: prediction_id={prediction_id}, graph_id={graph_id}")
            return updater

    @classmethod
    def get_updater(cls, prediction_id: str) -> Optional[ZepGraphMemoryUpdater]:
        """获取预测任务的更新器"""
        return cls._updaters.get(prediction_id)

    @classmethod
    def stop_updater(cls, prediction_id: str):
        """停止并移除预测任务的更新器"""
        with cls._lock:
            if prediction_id in cls._updaters:
                cls._updaters[prediction_id].stop()
                del cls._updaters[prediction_id]
                logger.info(f"已停止图谱记忆更新器: prediction_id={prediction_id}")

    _stop_all_done = False

    @classmethod
    def stop_all(cls):
        """停止所有更新器"""
        if cls._stop_all_done:
            return
        cls._stop_all_done = True

        with cls._lock:
            if cls._updaters:
                for pid, updater in list(cls._updaters.items()):
                    try:
                        updater.stop()
                    except Exception as e:
                        logger.error(f"停止更新器失败: prediction_id={pid}, error={e}")
                cls._updaters.clear()
            logger.info("已停止所有图谱记忆更新器")

    @classmethod
    def get_all_stats(cls) -> Dict[str, Dict[str, Any]]:
        """获取所有更新器的统计信息"""
        return {
            pid: updater.get_stats()
            for pid, updater in cls._updaters.items()
        }
