/**
 * 认证状态管理
 * reactive state + localStorage 持久化
 */
import { reactive } from 'vue'

const AUTH_KEY = 'mirofish_auth'

function loadFromStorage() {
  try {
    const raw = localStorage.getItem(AUTH_KEY)
    if (raw) return JSON.parse(raw)
  } catch {}
  return { token: '', refreshToken: '', user: null }
}

const saved = loadFromStorage()

const state = reactive({
  token: saved.token || '',
  refreshToken: saved.refreshToken || '',
  user: saved.user || null,
})

function persist() {
  localStorage.setItem(AUTH_KEY, JSON.stringify({
    token: state.token,
    refreshToken: state.refreshToken,
    user: state.user,
  }))
}

export function setAuth({ access_token, refresh_token, user }) {
  state.token = access_token || ''
  state.refreshToken = refresh_token || ''
  state.user = user || null
  persist()
}

export function updateAccessToken(access_token) {
  state.token = access_token || ''
  persist()
}

export function clearAuth() {
  state.token = ''
  state.refreshToken = ''
  state.user = null
  localStorage.removeItem(AUTH_KEY)
}

export function isLoggedIn() {
  return !!state.token
}

export const authState = state

// ---- 全局弹窗控制 ----
export const authModal = reactive({
  visible: false,
  tab: 'login', // 'login' | 'register'
})

export function openAuthModal(tab = 'login') {
  authModal.tab = tab
  authModal.visible = true
}

export function closeAuthModal() {
  authModal.visible = false
}

// ---- 账号弹窗控制 ----
export const accountModal = reactive({
  visible: false,
  tab: 'info', // 'info' | 'settings'
})

export function openAccountModal(tab = 'info') {
  accountModal.tab = tab
  accountModal.visible = true
}

export function closeAccountModal() {
  accountModal.visible = false
}
