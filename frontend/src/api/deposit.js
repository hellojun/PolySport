import service from './index'

/** 获取平台收款地址 */
export const getPlatformAddress = () => {
  return service.get('/api/deposit/platform-address')
}

/** 查询余额 & 订阅状态 */
export const getBalance = () => {
  return service.get('/api/deposit/balance')
}

/** Token 流水列表 */
export const getTokenHistory = (page = 1) => {
  return service.get('/api/deposit/history', { params: { page } })
}

/** 获取订阅计划列表 */
export const getPlans = () => {
  return service.get('/api/subscription/plans')
}

/** 获取当前订阅状态 */
export const getCurrentSubscription = () => {
  return service.get('/api/subscription/current')
}

/** 创建订阅订单 */
export const createSubscriptionOrder = (plan) => {
  return service.post('/api/subscription/create-order', { plan })
}

/** 验证订阅付款 */
export const verifySubscriptionPayment = (orderNo, txHash) => {
  return service.post('/api/subscription/verify-payment', { order_no: orderNo, tx_hash: txHash })
}
