/**
 * 认证 API
 */
import service from './index'

export const sendVerificationCode = (email, purpose = '') => {
  return service.post('/api/auth/send-code', { email, purpose })
}

export const verifyCode = (email, code) => {
  return service.post('/api/auth/verify-code', { email, code })
}

export const register = (email, password) => {
  return service.post('/api/auth/register', { email, password })
}

export const login = (email, password) => {
  return service.post('/api/auth/login', { email, password })
}

export const refreshToken = (refreshToken) => {
  return service.post('/api/auth/refresh', {}, {
    headers: { Authorization: `Bearer ${refreshToken}` },
    _skipAuthInterceptor: true,
  })
}

export const logout = (refreshToken) => {
  return service.post('/api/auth/logout', {}, {
    headers: { Authorization: `Bearer ${refreshToken}` },
  })
}

export const getMe = () => {
  return service.get('/api/auth/me')
}

export const resetPassword = (email, password) => {
  return service.post('/api/auth/reset-password', { email, password })
}
