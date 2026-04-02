import service from './index'

/** 获取平台收款地址 */
export const getPlatformAddress = () => {
  return service.get('/api/deposit/platform-address')
}

/** 创建充值订单 */
export const createDepositOrder = (amountUsdt) => {
  return service.post('/api/deposit/create-order', { amount_usdt: amountUsdt })
}

/** 提交 tx hash 验证 */
export const submitTxHash = (orderNo, txHash) => {
  return service.post('/api/deposit/submit-tx', { order_no: orderNo, tx_hash: txHash })
}

/** 查询订单状态 */
export const getOrderStatus = (orderNo) => {
  return service.get(`/api/deposit/order/${orderNo}`)
}

/** 查询 Token 余额 */
export const getBalance = () => {
  return service.get('/api/deposit/balance')
}

/** Token 流水列表 */
export const getTokenHistory = (page = 1) => {
  return service.get('/api/deposit/history', { params: { page } })
}
