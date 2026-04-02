import axios from 'axios'
import { authState, updateAccessToken, clearAuth, openAuthModal } from '../stores/auth'

// 创建axios实例
const service = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:5001',
  timeout: 300000, // 5分钟超时（本体生成可能需要较长时间）
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器：注入 Authorization header
service.interceptors.request.use(
  config => {
    if (authState.token && !config._skipAuthInterceptor) {
      config.headers.Authorization = `Bearer ${authState.token}`
    }
    return config
  },
  error => {
    console.error('Request error:', error)
    return Promise.reject(error)
  }
)

// 是否正在刷新 token
let isRefreshing = false
let refreshSubscribers = []

function onRefreshed(newToken) {
  refreshSubscribers.forEach(cb => cb(newToken))
  refreshSubscribers = []
}

function addRefreshSubscriber(cb) {
  refreshSubscribers.push(cb)
}

// 响应拦截器
service.interceptors.response.use(
  response => {
    const res = response.data

    // 如果返回的状态码不是success，则抛出错误
    if (!res.success && res.success !== undefined) {
      console.error('API Error:', res.error || res.message || 'Unknown error')
      return Promise.reject(new Error(res.error || res.message || 'Error'))
    }

    return res
  },
  async error => {
    const originalRequest = error.config

    // 401: auth 接口（登录/注册等）直接返回错误，不触发 token 刷新
    const isAuthApi = originalRequest.url?.includes('/api/auth/')
    if (error.response?.status === 401 && !isAuthApi && !originalRequest._skipAuthInterceptor && !originalRequest._isRetry) {
      if (!authState.refreshToken) {
        clearAuth()
        openAuthModal('login')
        return Promise.reject(error)
      }

      if (isRefreshing) {
        // 排队等待 refresh 完成
        return new Promise(resolve => {
          addRefreshSubscriber(newToken => {
            originalRequest.headers.Authorization = `Bearer ${newToken}`
            originalRequest._isRetry = true
            resolve(service(originalRequest))
          })
        })
      }

      isRefreshing = true
      try {
        const res = await axios.post(
          (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:5001') + '/api/auth/refresh',
          {},
          { headers: { Authorization: `Bearer ${authState.refreshToken}` } }
        )
        const newToken = res.data.access_token
        updateAccessToken(newToken)
        isRefreshing = false
        onRefreshed(newToken)

        originalRequest.headers.Authorization = `Bearer ${newToken}`
        originalRequest._isRetry = true
        return service(originalRequest)
      } catch (refreshError) {
        isRefreshing = false
        refreshSubscribers = []
        clearAuth()
        openAuthModal('login')
        return Promise.reject(refreshError)
      }
    }

    console.error('Response error:', error)

    // 从后端响应体提取业务错误信息
    const serverMsg = error.response?.data?.error || error.response?.data?.message
    if (serverMsg) {
      return Promise.reject(new Error(serverMsg))
    }

    // 处理超时
    if (error.code === 'ECONNABORTED' && error.message.includes('timeout')) {
      return Promise.reject(new Error('Request timeout'))
    }

    // 处理网络错误
    if (error.message === 'Network Error') {
      return Promise.reject(new Error('Network error'))
    }

    return Promise.reject(error)
  }
)

// 带重试的请求函数
export const requestWithRetry = async (requestFn, maxRetries = 3, delay = 1000) => {
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await requestFn()
    } catch (error) {
      if (i === maxRetries - 1) throw error

      console.warn(`Request failed, retrying (${i + 1}/${maxRetries})...`)
      await new Promise(resolve => setTimeout(resolve, delay * Math.pow(2, i)))
    }
  }
}

export default service
