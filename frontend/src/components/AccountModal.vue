<template>
  <div v-if="accountModal.visible" class="account-overlay" @click.self="closeAccountModal">
    <div class="account-modal">
      <div class="account-header">
        <div class="account-tabs">
          <button
            class="tab-btn"
            :class="{ active: accountModal.tab === 'info' }"
            @click="accountModal.tab = 'info'"
          >{{ t('account.info_tab') }}</button>
          <button
            class="tab-btn"
            :class="{ active: accountModal.tab === 'settings' }"
            @click="accountModal.tab = 'settings'"
          >{{ t('account.settings_tab') }}</button>
        </div>
        <button class="account-close" @click="closeAccountModal">&times;</button>
      </div>

      <!-- 信息 Tab -->
      <div v-if="accountModal.tab === 'info'" class="account-body">
        <div class="info-row">
          <span class="info-label">{{ t('account.email_label') }}</span>
          <span class="info-value">{{ userEmail }}</span>
        </div>

        <div class="info-row balance-row">
          <span class="info-label">{{ t('account.balance_label') }}</span>
          <span class="info-value balance-value">{{ balance.toFixed(2) }} Token</span>
          <button class="deposit-toggle-btn" @click="showDeposit = !showDeposit">
            {{ showDeposit ? '▲' : t('account.deposit_btn') }}
          </button>
        </div>

        <!-- 充值区 -->
        <div v-if="showDeposit" class="deposit-section">
          <div class="deposit-address-area">
            <p class="deposit-hint">{{ t('account.deposit_hint') }}</p>
            <div class="address-box">
              <code class="address-text">{{ platformAddress }}</code>
              <button class="copy-btn" @click="copyAddress">
                {{ copied ? t('account.copied') : t('account.copy_address') }}
              </button>
            </div>
            <canvas ref="qrCanvas" class="qr-canvas"></canvas>
          </div>

          <div class="deposit-form">
            <p class="exchange-rate-hint">1 USDT = 1 Token</p>

            <input
              v-model="txHash"
              class="form-input tx-input"
              :placeholder="t('account.tx_hash_placeholder')"
            />

            <button
              class="submit-btn"
              :disabled="!txHash || submitting"
              @click="handleSubmitTx"
            >
              {{ submitting ? t('account.verifying') : t('account.submit_verify') }}
            </button>

            <p v-if="depositStatus === 'completed'" class="status-text success">{{ t('account.verify_success') }}</p>
            <p v-if="depositStatus === 'failed'" class="status-text error">{{ depositError || t('account.verify_failed') }}</p>
            <p v-if="depositStatus === 'confirming'" class="status-text warning">{{ depositError }}</p>
          </div>
        </div>

        <!-- 交易记录 -->
        <div class="history-section">
          <h4 class="section-title">{{ t('account.tx_history') }}</h4>
          <div v-if="transactions.length === 0" class="no-history">{{ t('account.no_history') }}</div>
          <div v-else class="tx-list">
            <div v-for="tx in transactions" :key="tx.id" class="tx-item">
              <div class="tx-info">
                <span class="tx-type" :class="tx.amount >= 0 ? 'credit' : 'debit'">
                  {{ txTypeLabel(tx.type) }}
                </span>
                <span class="tx-time">{{ formatTime(tx.created_at) }}</span>
              </div>
              <span class="tx-amount" :class="tx.amount >= 0 ? 'credit' : 'debit'">
                {{ tx.amount >= 0 ? '+' : '' }}{{ tx.amount.toFixed(2) }}
              </span>
            </div>
          </div>
        </div>

        <button class="logout-btn-full" @click="handleLogout">{{ t('account.logout') }}</button>
      </div>

      <!-- 设置 Tab -->
      <div v-if="accountModal.tab === 'settings'" class="account-body">
        <div class="setting-item">
          <div class="setting-info">
            <span class="setting-label">{{ t('settings.fast_mode') }}</span>
            <span class="setting-desc">{{ t('settings.fast_mode_desc') }}</span>
          </div>
          <label class="toggle-switch">
            <input type="checkbox" v-model="fastMode" @change="saveFastMode" />
            <span class="toggle-slider"></span>
          </label>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  authState, clearAuth, accountModal, closeAccountModal,
} from '../stores/auth'
import { logout as logoutApi } from '../api/auth'
import {
  getPlatformAddress, createDepositOrder, submitTxHash, getBalance, getTokenHistory,
} from '../api/deposit'
import QRCode from 'qrcode'

const { t } = useI18n()

// ---- Auth ----
const userEmail = ref(authState.user?.email || '')
watch(() => authState.user, (u) => { userEmail.value = u?.email || '' })

async function handleLogout() {
  try {
    if (authState.refreshToken) {
      await logoutApi(authState.refreshToken)
    }
  } catch {}
  clearAuth()
  closeAccountModal()
}

// ---- Balance ----
const balance = ref(0)

async function refreshBalance() {
  try {
    const res = await getBalance()
    balance.value = res.balance || 0
  } catch {}
}

// ---- Deposit ----
const showDeposit = ref(false)
const platformAddress = ref('')
const copied = ref(false)
const depositAmount = ref(10)
const txHash = ref('')
const submitting = ref(false)
const depositStatus = ref('')
const depositError = ref('')
const orderNo = ref('')
const qrCanvas = ref(null)

async function loadPlatformAddress() {
  try {
    const res = await getPlatformAddress()
    platformAddress.value = res.address || ''
  } catch {}
}

function copyAddress() {
  navigator.clipboard.writeText(platformAddress.value)
  copied.value = true
  setTimeout(() => { copied.value = false }, 2000)
}

function drawQR() {
  if (!qrCanvas.value || !platformAddress.value) return
  QRCode.toCanvas(qrCanvas.value, platformAddress.value, {
    width: 160,
    margin: 2,
    color: { dark: '#000000', light: '#ffffff' },
  })
}

watch(showDeposit, (val) => {
  if (val) {
    loadPlatformAddress()
    nextTick(() => { drawQR() })
  }
})

watch(platformAddress, () => {
  nextTick(() => { drawQR() })
})

async function handleSubmitTx() {
  if (!txHash.value) return
  submitting.value = true
  depositStatus.value = ''
  depositError.value = ''

  try {
    // 创建订单
    if (!orderNo.value) {
      const orderRes = await createDepositOrder(depositAmount.value)
      orderNo.value = orderRes.order_no
    }

    // 提交验证
    const res = await submitTxHash(orderNo.value, txHash.value.trim())
    if (res.success) {
      depositStatus.value = 'completed'
      balance.value = res.balance || balance.value
      txHash.value = ''
      orderNo.value = ''
      refreshHistory()
    } else {
      depositStatus.value = res.status || 'failed'
      depositError.value = res.error || ''
    }
  } catch (err) {
    depositStatus.value = 'failed'
    depositError.value = err?.response?.data?.error || err.message || ''
  } finally {
    submitting.value = false
  }
}

// ---- Transaction History ----
const transactions = ref([])

async function refreshHistory() {
  try {
    const res = await getTokenHistory()
    transactions.value = res.transactions || []
  } catch {}
}

function txTypeLabel(type) {
  const map = {
    deposit: t('account.deposit_btn'),
    predict_normal: t('predict_type.normal'),
    predict_premium: t('predict_type.premium'),
    refund: 'Refund',
  }
  return map[type] || type
}

function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours()}:${String(d.getMinutes()).padStart(2, '0')}`
}

// ---- Settings ----
const fastMode = ref(localStorage.getItem('fastMode') === 'true')
const debateRounds = ref(parseInt(localStorage.getItem('debateRounds') || '3', 10))

function saveFastMode() {
  localStorage.setItem('fastMode', String(fastMode.value))
}

function setDebateRounds(n) {
  debateRounds.value = n
  localStorage.setItem('debateRounds', String(n))
}

// ---- Init on visible ----
watch(() => accountModal.visible, (val) => {
  if (val) {
    refreshBalance()
    refreshHistory()
  }
})
</script>

<style scoped>
.account-overlay {
  position: fixed;
  top: 0; left: 0;
  width: 100%; height: 100%;
  background: rgba(0, 0, 0, 0.5);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.account-modal {
  background: var(--white);
  max-width: 480px;
  width: 90%;
  max-height: 85vh;
  overflow-y: auto;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
}

.account-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  border-bottom: 1px solid var(--border);
}

.account-tabs {
  display: flex;
  gap: 0;
}

.tab-btn {
  background: none;
  border: 1px solid var(--border);
  padding: 6px 20px;
  font-family: var(--font-mono);
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
  color: var(--gray-text);
  transition: all 0.2s;
}

.tab-btn:first-child { border-radius: 4px 0 0 4px; }
.tab-btn:last-child { border-radius: 0 4px 4px 0; border-left: none; }

.tab-btn.active {
  background: var(--black);
  border-color: var(--black);
  color: var(--white);
}

.account-close {
  background: none;
  border: none;
  font-size: 1.4rem;
  color: #999;
  cursor: pointer;
  line-height: 1;
  padding: 0;
}

.account-close:hover { color: var(--black); }

.account-body { padding: 24px; }

/* Info */
.info-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.info-label {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  color: var(--gray-text);
  min-width: 50px;
}

.info-value {
  font-family: var(--font-mono);
  font-size: 0.9rem;
  font-weight: 600;
}

.balance-row { margin-bottom: 20px; }

.balance-value {
  color: var(--orange);
  font-size: 1.1rem;
}

.deposit-toggle-btn {
  background: none;
  border: 1px solid var(--orange);
  color: var(--orange);
  font-family: var(--font-mono);
  font-size: 0.75rem;
  font-weight: 700;
  padding: 4px 12px;
  cursor: pointer;
  margin-left: auto;
  transition: all 0.2s;
}

.deposit-toggle-btn:hover {
  background: var(--orange);
  color: var(--white);
}

/* Deposit */
.deposit-section {
  background: #FAFAFA;
  border: 1px solid var(--border);
  padding: 16px;
  margin-bottom: 20px;
}

.deposit-hint {
  font-size: 0.8rem;
  color: var(--gray-text);
  margin: 0 0 12px 0;
  line-height: 1.4;
}

.address-box {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.address-text {
  font-size: 0.7rem;
  background: var(--white);
  padding: 8px;
  border: 1px solid var(--border);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  word-break: break-all;
}

.copy-btn {
  background: var(--black);
  color: var(--white);
  border: none;
  font-family: var(--font-mono);
  font-size: 0.7rem;
  padding: 8px 12px;
  cursor: pointer;
  white-space: nowrap;
}

.copy-btn:hover { background: var(--orange); }

.qr-canvas {
  display: block;
  margin: 0 auto 12px;
  border: 1px solid var(--border);
}

.deposit-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.exchange-rate-hint {
  font-family: var(--font-mono);
  font-size: 0.85rem;
  font-weight: 700;
  color: var(--orange);
  margin: 0;
  text-align: center;
}

.form-input {
  border: 1px solid var(--border);
  background: var(--white);
  padding: 10px 12px;
  font-family: var(--font-mono);
  font-size: 0.8rem;
  outline: none;
  transition: border-color 0.2s;
}

.form-input:focus { border-color: var(--black); }

.submit-btn {
  background: var(--black);
  color: var(--white);
  border: none;
  padding: 10px;
  font-family: var(--font-mono);
  font-weight: 700;
  font-size: 0.85rem;
  cursor: pointer;
  transition: background 0.3s;
}

.submit-btn:not(:disabled):hover { background: var(--orange); }
.submit-btn:disabled { background: #E5E5E5; color: #999; cursor: not-allowed; }

.status-text {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  margin: 0;
}

.status-text.success { color: #00AA00; }
.status-text.error { color: #CC0000; }
.status-text.warning { color: #CC6600; }

/* History */
.history-section {
  margin-top: 20px;
  border-top: 1px solid var(--border);
  padding-top: 16px;
}

.section-title {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 1px;
  margin: 0 0 12px 0;
  color: #333;
}

.no-history {
  font-size: 0.8rem;
  color: var(--gray-text);
}

.tx-list {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.tx-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid #F0F0F0;
}

.tx-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.tx-type {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  font-weight: 600;
}

.tx-type.credit { color: #00AA00; }
.tx-type.debit { color: #333; }

.tx-time {
  font-size: 0.65rem;
  color: #999;
}

.tx-amount {
  font-family: var(--font-mono);
  font-size: 0.85rem;
  font-weight: 700;
}

.tx-amount.credit { color: #00AA00; }
.tx-amount.debit { color: #CC0000; }

.logout-btn-full {
  width: 100%;
  margin-top: 20px;
  background: none;
  border: 1px solid #e53e3e;
  color: #e53e3e;
  font-family: var(--font-mono);
  font-size: 0.8rem;
  font-weight: 600;
  padding: 10px;
  cursor: pointer;
  transition: all 0.2s;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.logout-btn-full:hover {
  background: #e53e3e;
  color: var(--white);
}

/* Settings (reuse styles from App.vue) */
.setting-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.setting-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
}

.setting-label {
  font-family: var(--font-mono);
  font-size: 0.85rem;
  font-weight: 600;
}

.setting-desc {
  font-size: 0.75rem;
  color: var(--gray-text);
  line-height: 1.4;
}

.toggle-switch {
  position: relative;
  display: inline-block;
  width: 44px;
  height: 24px;
  flex-shrink: 0;
}

.toggle-switch input { opacity: 0; width: 0; height: 0; }

.toggle-slider {
  position: absolute;
  cursor: pointer;
  top: 0; left: 0; right: 0; bottom: 0;
  background: #DDD;
  transition: 0.3s;
  border-radius: 24px;
}

.toggle-slider::before {
  content: '';
  position: absolute;
  height: 18px; width: 18px;
  left: 3px; bottom: 3px;
  background: var(--white);
  transition: 0.3s;
  border-radius: 50%;
}

.toggle-switch input:checked + .toggle-slider { background: var(--orange); }
.toggle-switch input:checked + .toggle-slider::before { transform: translateX(20px); }

.rounds-btn-group {
  display: flex;
  gap: 0;
  flex-shrink: 0;
}

.rounds-btn {
  background: none;
  border: 1px solid var(--border);
  color: var(--gray-text);
  font-family: var(--font-mono);
  font-size: 0.85rem;
  font-weight: 700;
  width: 36px;
  height: 32px;
  cursor: pointer;
  transition: all 0.2s;
}

.rounds-btn:first-child { border-radius: 4px 0 0 4px; }
.rounds-btn:last-child { border-radius: 0 4px 4px 0; }
.rounds-btn:not(:first-child) { border-left: none; }

.rounds-btn.active {
  background: var(--orange);
  border-color: var(--orange);
  color: var(--white);
}

.rounds-btn:not(.active):hover {
  border-color: var(--black);
  color: var(--black);
}
</style>
