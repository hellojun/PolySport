import service from './index'

/**
 * 获取指定日期的 Polymarket NBA 盘口
 * @param {string} date - YYYY-MM-DD
 */
export const getPolymarketEvents = (date) => {
  return service.get('/api/prediction/polymarket/events', {
    params: { date }
  })
}

/**
 * 创建预测任务
 * @param {Object} data - 对阵数据
 * @param {string} predictionType - 'normal' | 'premium'
 */
export const createPrediction = (data, predictionType = 'premium') => {
  return service.post('/api/prediction/create', { ...data, prediction_type: predictionType })
}

/**
 * 查询预测任务进度
 * @param {string} taskId - 任务ID
 */
export const getPredictionTask = (taskId) => {
  return service.get(`/api/prediction/task/${taskId}`)
}

/**
 * 获取预测结果
 * @param {string} matchupId - 对阵ID
 * @param {string} level - 输出层级 L1/L2/L3
 */
export const getPredictionResult = (matchupId, level = 'L1') => {
  return service.get(`/api/prediction/result/${matchupId}`, {
    params: { level }
  })
}

/**
 * 获取预测历史列表
 */
export const getPredictionHistory = () => {
  return service.get('/api/prediction/history')
}

/**
 * 获取比赛实际结果
 * @param {string} matchupId - 对阵ID
 * @param {Object} meta - 可选的 {home, away, game_date} 兜底参数
 */
export const fetchGameResult = (matchupId, meta = {}) => {
  return service.post(`/api/prediction/game-result/${matchupId}`, meta)
}

/**
 * 删除预测记录
 * @param {string} taskId - 任务ID
 */
export const deletePrediction = (taskId) => {
  return service.delete(`/api/prediction/delete/${taskId}`)
}

/**
 * 获取公开预测统计数据（无需登录）
 */
export const getPublicStats = () => {
  return service.get('/api/prediction/stats')
}

/**
 * 获取完整战绩数据（无需登录）
 */
export const getTrackRecord = (params = {}) => {
  return service.get('/api/prediction/track-record', { params })
}
