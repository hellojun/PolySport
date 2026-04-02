"""
Polygon 链上 USDT 转账验证服务
"""

from decimal import Decimal

from web3 import Web3

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger('mirofish.polygon')

# ERC20 Transfer event signature: Transfer(address,address,uint256)
TRANSFER_TOPIC = Web3.keccak(text="Transfer(address,address,uint256)").hex()

# USDT on Polygon has 6 decimals
USDT_DECIMALS = 6


class PolygonService:
    """通过 Polygon RPC 验证 USDT 链上转账"""

    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider(Config.POLYGON_RPC_URL))
        self.usdt_contract = Config.POLYGON_USDT_CONTRACT.lower()
        self.platform_address = Config.PLATFORM_WALLET_ADDRESS.lower()
        self.min_confirmations = Config.DEPOSIT_MIN_CONFIRMATIONS

    def verify_usdt_transfer(self, tx_hash: str) -> dict:
        """
        验证链上 USDT 转账交易。
        返回: { success, from_address, amount, confirmations, error }
        """
        try:
            receipt = self.w3.eth.get_transaction_receipt(tx_hash)
        except Exception as e:
            logger.error(f"获取交易收据失败: {e}")
            return {"success": False, "error": f"无法获取交易收据: {e}"}

        if receipt is None:
            return {"success": False, "error": "交易不存在或尚未被打包"}

        if receipt.status != 1:
            return {"success": False, "error": "交易执行失败 (reverted)"}

        # 解析 Transfer event logs
        # 不检查 receipt.to，因为交易所提币时 to 是批量转账合约而非 USDT 合约
        # 只要 logs 中有 USDT 合约发出的 Transfer 事件且收款地址是平台地址即可
        from_address = None
        amount = Decimal(0)

        for log in receipt.logs:
            if log.address.lower() != self.usdt_contract:
                continue
            if len(log.topics) < 3:
                continue
            if log.topics[0].hex() != TRANSFER_TOPIC:
                continue

            # topics[1] = from, topics[2] = to (左侧补零的 32 字节地址)
            to_addr = "0x" + log.topics[2].hex()[-40:]
            if to_addr.lower() != self.platform_address:
                continue

            # 记录第一个 from 地址，累加金额（一笔交易可能有多条 Transfer）
            if from_address is None:
                from_address = "0x" + log.topics[1].hex()[-40:]
            raw_amount = int(log.data.hex(), 16)
            amount += Decimal(raw_amount) / Decimal(10 ** USDT_DECIMALS)

        if from_address is None:
            return {"success": False, "error": "未找到转入平台地址的 USDT Transfer 事件"}

        if amount <= 0:
            return {"success": False, "error": "转账金额为 0"}

        # 检查确认数
        try:
            current_block = self.w3.eth.block_number
        except Exception as e:
            return {"success": False, "error": f"无法获取当前块高: {e}"}

        confirmations = current_block - receipt.blockNumber
        if confirmations < self.min_confirmations:
            return {
                "success": False,
                "confirming": True,
                "from_address": from_address,
                "amount": float(amount),
                "confirmations": confirmations,
                "required": self.min_confirmations,
                "error": f"确认数不足: {confirmations}/{self.min_confirmations}",
            }

        return {
            "success": True,
            "from_address": from_address,
            "amount": float(amount),
            "confirmations": confirmations,
        }
