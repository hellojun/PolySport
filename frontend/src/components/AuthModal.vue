<template>
  <div v-if="authModal.visible" class="auth-overlay" @click.self="closeAuthModal">
    <div class="auth-modal">
      <button class="auth-close" @click="closeAuthModal">&times;</button>

      <!-- Tab 切换 -->
      <div class="auth-tabs">
        <button
          class="auth-tab"
          :class="{ active: authModal.tab === 'login' }"
          @click="switchTab('login')"
        >{{ t('auth.login_title') }}</button>
        <button
          class="auth-tab"
          :class="{ active: authModal.tab === 'register' }"
          @click="switchTab('register')"
        >{{ t('auth.register_title') }}</button>
        <button
          class="auth-tab"
          :class="{ active: authModal.tab === 'forgot' }"
          @click="switchTab('forgot')"
        >{{ t('auth.forgot_title') }}</button>
      </div>

      <!-- ===== 登录表单 ===== -->
      <form v-if="authModal.tab === 'login'" @submit.prevent="handleLogin" class="auth-form">
        <div class="form-group">
          <label>{{ t('auth.email') }}</label>
          <input
            type="email"
            v-model="loginEmail"
            :placeholder="t('auth.email_placeholder')"
            required
            autocomplete="email"
          />
        </div>
        <div class="form-group">
          <label>{{ t('auth.password') }}</label>
          <input
            type="password"
            v-model="loginPassword"
            :placeholder="t('auth.password_placeholder')"
            required
            autocomplete="current-password"
          />
        </div>
        <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>
        <button type="submit" class="auth-btn" :disabled="loading">
          {{ loading ? t('auth.logging_in') : t('auth.login') }}
        </button>
        <p class="auth-link-row">
          <a href="#" @click.prevent="switchTab('forgot')">{{ t('auth.forgot_password') }}</a>
        </p>
      </form>

      <!-- ===== 注册表单 ===== -->
      <div v-if="authModal.tab === 'register'" class="auth-form">
        <template v-if="regStep === 1">
          <div class="form-group">
            <label>{{ t('auth.email') }}</label>
            <input type="email" v-model="regEmail" :placeholder="t('auth.email_placeholder')" autocomplete="email" />
          </div>
          <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>
          <button class="auth-btn" :disabled="loading" @click="handleRegSendCode">
            {{ loading ? t('auth.sending') : t('auth.send_code') }}
          </button>
        </template>

        <template v-if="regStep === 2">
          <p class="step-hint">{{ t('auth.code_sent_to', { email: regEmail }) }}</p>
          <div class="form-group">
            <label>{{ t('auth.verification_code') }}</label>
            <input type="text" v-model="regCode" maxlength="6" :placeholder="t('auth.code_placeholder')" autocomplete="one-time-code" />
          </div>
          <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>
          <button class="auth-btn" :disabled="loading" @click="handleRegVerifyCode">
            {{ loading ? t('auth.verifying') : t('auth.verify') }}
          </button>
          <button class="resend-btn" :disabled="countdown > 0 || loading" @click="handleRegSendCode">
            {{ countdown > 0 ? t('auth.resend_in', { seconds: countdown }) : t('auth.resend_code') }}
          </button>
        </template>

        <template v-if="regStep === 3">
          <div class="form-group">
            <label>{{ t('auth.password') }}</label>
            <input type="password" v-model="regPassword" :placeholder="t('auth.password_set_placeholder')" autocomplete="new-password" />
          </div>
          <div class="form-group">
            <label>{{ t('auth.confirm_password') }}</label>
            <input type="password" v-model="regConfirmPassword" :placeholder="t('auth.confirm_password_placeholder')" autocomplete="new-password" />
          </div>
          <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>
          <button class="auth-btn" :disabled="loading" @click="handleRegister">
            {{ loading ? t('auth.registering') : t('auth.register') }}
          </button>
        </template>
      </div>

      <!-- ===== 找回密码表单 ===== -->
      <div v-if="authModal.tab === 'forgot'" class="auth-form">
        <template v-if="forgotStep === 1">
          <div class="form-group">
            <label>{{ t('auth.email') }}</label>
            <input type="email" v-model="forgotEmail" :placeholder="t('auth.email_placeholder')" autocomplete="email" />
          </div>
          <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>
          <button class="auth-btn" :disabled="loading" @click="handleForgotSendCode">
            {{ loading ? t('auth.sending') : t('auth.send_code') }}
          </button>
        </template>

        <template v-if="forgotStep === 2">
          <p class="step-hint">{{ t('auth.code_sent_to', { email: forgotEmail }) }}</p>
          <div class="form-group">
            <label>{{ t('auth.verification_code') }}</label>
            <input type="text" v-model="forgotCode" maxlength="6" :placeholder="t('auth.code_placeholder')" autocomplete="one-time-code" />
          </div>
          <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>
          <button class="auth-btn" :disabled="loading" @click="handleForgotVerifyCode">
            {{ loading ? t('auth.verifying') : t('auth.verify') }}
          </button>
          <button class="resend-btn" :disabled="forgotCountdown > 0 || loading" @click="handleForgotSendCode">
            {{ forgotCountdown > 0 ? t('auth.resend_in', { seconds: forgotCountdown }) : t('auth.resend_code') }}
          </button>
        </template>

        <template v-if="forgotStep === 3">
          <div class="form-group">
            <label>{{ t('auth.new_password') }}</label>
            <input type="password" v-model="forgotPassword" :placeholder="t('auth.password_set_placeholder')" autocomplete="new-password" />
          </div>
          <div class="form-group">
            <label>{{ t('auth.confirm_password') }}</label>
            <input type="password" v-model="forgotConfirmPassword" :placeholder="t('auth.confirm_password_placeholder')" autocomplete="new-password" />
          </div>
          <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>
          <button class="auth-btn" :disabled="loading" @click="handleResetPassword">
            {{ loading ? t('auth.resetting') : t('auth.reset_password') }}
          </button>
        </template>

        <template v-if="forgotStep === 4">
          <p class="success-msg">{{ t('auth.reset_success') }}</p>
          <button class="auth-btn" @click="switchTab('login')">{{ t('auth.go_login') }}</button>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import { login, sendVerificationCode, verifyCode, register, resetPassword } from '../api/auth'
import { setAuth, authModal, closeAuthModal } from '../stores/auth'

const { t } = useI18n()

// ---- Shared ----
const errorMsg = ref('')
const loading = ref(false)

// ---- Login ----
const loginEmail = ref('')
const loginPassword = ref('')

async function handleLogin() {
  errorMsg.value = ''
  loading.value = true
  try {
    const res = await login(loginEmail.value, loginPassword.value)
    setAuth(res)
    closeAuthModal()
  } catch (e) {
    errorMsg.value = e.message || t('auth.login_failed')
  } finally {
    loading.value = false
  }
}

// ---- Register ----
const regStep = ref(1)
const regEmail = ref('')
const regCode = ref('')
const regPassword = ref('')
const regConfirmPassword = ref('')
const countdown = ref(0)
let regTimer = null

function startRegCountdown() {
  countdown.value = 60
  if (regTimer) clearInterval(regTimer)
  regTimer = setInterval(() => {
    countdown.value--
    if (countdown.value <= 0) { clearInterval(regTimer); regTimer = null }
  }, 1000)
}

async function handleRegSendCode() {
  errorMsg.value = ''
  if (!regEmail.value || !regEmail.value.includes('@')) {
    errorMsg.value = t('auth.invalid_email'); return
  }
  loading.value = true
  try {
    await sendVerificationCode(regEmail.value, 'register')
    regStep.value = 2
    startRegCountdown()
  } catch (e) {
    errorMsg.value = e.message || t('auth.send_code_failed')
  } finally {
    loading.value = false
  }
}

async function handleRegVerifyCode() {
  errorMsg.value = ''
  if (!regCode.value || regCode.value.length !== 6) {
    errorMsg.value = t('auth.invalid_code'); return
  }
  loading.value = true
  try {
    await verifyCode(regEmail.value, regCode.value)
    regStep.value = 3
  } catch (e) {
    errorMsg.value = e.message || t('auth.verify_failed')
  } finally {
    loading.value = false
  }
}

async function handleRegister() {
  errorMsg.value = ''
  if (regPassword.value.length < 6) { errorMsg.value = t('auth.password_too_short'); return }
  if (regPassword.value !== regConfirmPassword.value) { errorMsg.value = t('auth.password_mismatch'); return }
  loading.value = true
  try {
    const res = await register(regEmail.value, regPassword.value)
    setAuth(res)
    closeAuthModal()
  } catch (e) {
    errorMsg.value = e.message || t('auth.register_failed')
  } finally {
    loading.value = false
  }
}

// ---- Forgot Password ----
const forgotStep = ref(1)
const forgotEmail = ref('')
const forgotCode = ref('')
const forgotPassword = ref('')
const forgotConfirmPassword = ref('')
const forgotCountdown = ref(0)
let forgotTimer = null

function startForgotCountdown() {
  forgotCountdown.value = 60
  if (forgotTimer) clearInterval(forgotTimer)
  forgotTimer = setInterval(() => {
    forgotCountdown.value--
    if (forgotCountdown.value <= 0) { clearInterval(forgotTimer); forgotTimer = null }
  }, 1000)
}

async function handleForgotSendCode() {
  errorMsg.value = ''
  if (!forgotEmail.value || !forgotEmail.value.includes('@')) {
    errorMsg.value = t('auth.invalid_email'); return
  }
  loading.value = true
  try {
    await sendVerificationCode(forgotEmail.value, 'reset')
    forgotStep.value = 2
    startForgotCountdown()
  } catch (e) {
    errorMsg.value = e.message || t('auth.send_code_failed')
  } finally {
    loading.value = false
  }
}

async function handleForgotVerifyCode() {
  errorMsg.value = ''
  if (!forgotCode.value || forgotCode.value.length !== 6) {
    errorMsg.value = t('auth.invalid_code'); return
  }
  loading.value = true
  try {
    await verifyCode(forgotEmail.value, forgotCode.value)
    forgotStep.value = 3
  } catch (e) {
    errorMsg.value = e.message || t('auth.verify_failed')
  } finally {
    loading.value = false
  }
}

async function handleResetPassword() {
  errorMsg.value = ''
  if (forgotPassword.value.length < 6) { errorMsg.value = t('auth.password_too_short'); return }
  if (forgotPassword.value !== forgotConfirmPassword.value) { errorMsg.value = t('auth.password_mismatch'); return }
  loading.value = true
  try {
    await resetPassword(forgotEmail.value, forgotPassword.value)
    forgotStep.value = 4
  } catch (e) {
    errorMsg.value = e.message || t('auth.reset_failed')
  } finally {
    loading.value = false
  }
}

// ---- Tab 切换时重置 ----
function switchTab(tab) {
  authModal.tab = tab
  errorMsg.value = ''
  regStep.value = 1
  forgotStep.value = 1
}

// 弹窗关闭时重置所有状态
watch(() => authModal.visible, (v) => {
  if (!v) {
    regStep.value = 1
    forgotStep.value = 1
    errorMsg.value = ''
    loginEmail.value = ''
    loginPassword.value = ''
    regEmail.value = ''
    regCode.value = ''
    regPassword.value = ''
    regConfirmPassword.value = ''
    forgotEmail.value = ''
    forgotCode.value = ''
    forgotPassword.value = ''
    forgotConfirmPassword.value = ''
  }
})

onBeforeUnmount(() => {
  if (regTimer) clearInterval(regTimer)
  if (forgotTimer) clearInterval(forgotTimer)
})
</script>

<style scoped>
.auth-overlay {
  position: fixed;
  top: 0; left: 0; width: 100%; height: 100%;
  background: rgba(0, 0, 0, 0.5);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.auth-modal {
  background: var(--white);
  width: 90%; max-width: 400px;
  padding: 32px;
  position: relative;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
}

.auth-close {
  position: absolute; top: 12px; right: 16px;
  background: none; border: none;
  font-size: 1.4rem; color: #999; cursor: pointer; line-height: 1; padding: 0;
}
.auth-close:hover { color: var(--black); }

.auth-tabs {
  display: flex; gap: 0;
  margin-bottom: 28px;
  border-bottom: 1px solid var(--border);
}

.auth-tab {
  flex: 1;
  background: none; border: none;
  border-bottom: 2px solid transparent;
  font-family: var(--font-mono); font-size: 0.8rem; font-weight: 700;
  text-transform: uppercase; letter-spacing: 0.5px;
  padding: 10px 0; color: var(--gray-text); cursor: pointer; transition: all 0.2s;
}
.auth-tab.active { color: var(--black); border-bottom-color: var(--orange); }
.auth-tab:hover:not(.active) { color: var(--black); }

.auth-form { display: flex; flex-direction: column; gap: 20px; }

.step-hint { font-size: 0.8rem; color: var(--gray-text); margin: 0; }

.form-group { display: flex; flex-direction: column; gap: 6px; }
.form-group label {
  font-family: var(--font-mono); font-size: 0.75rem; font-weight: 600;
  text-transform: uppercase; letter-spacing: 1px; color: var(--gray-text);
}
.form-group input {
  font-family: var(--font-mono); font-size: 0.9rem; padding: 10px 12px;
  border: 1px solid var(--border); background: var(--white); color: var(--black);
  outline: none; transition: border-color 0.2s;
}
.form-group input:focus { border-color: var(--black); }

.error-msg { color: #e53e3e; font-size: 0.8rem; margin: 0; }
.success-msg { color: #38a169; font-size: 0.85rem; margin: 0; text-align: center; }

.auth-btn {
  font-family: var(--font-mono); font-size: 0.85rem; font-weight: 700;
  text-transform: uppercase; letter-spacing: 1px; padding: 12px;
  background: var(--black); color: var(--white); border: none; cursor: pointer; transition: background 0.2s;
}
.auth-btn:hover:not(:disabled) { background: var(--orange); }
.auth-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.resend-btn {
  font-family: var(--font-mono); font-size: 0.8rem;
  background: none; border: 1px solid var(--border); color: var(--gray-text);
  padding: 8px; cursor: pointer; transition: all 0.2s;
}
.resend-btn:hover:not(:disabled) { border-color: var(--black); color: var(--black); }
.resend-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.auth-link-row {
  text-align: center; margin: 0; font-size: 0.8rem;
}
.auth-link-row a {
  color: var(--gray-text); text-decoration: none; transition: color 0.2s;
}
.auth-link-row a:hover { color: var(--orange); }
</style>
