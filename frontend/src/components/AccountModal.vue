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
            :class="{ active: accountModal.tab === 'history' }"
            @click="accountModal.tab = 'history'"
          >{{ t('account.history_tab') }}</button>
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

        <!-- 订阅状态 -->
        <div class="subscription-status">
          <div class="sub-plan-row">
            <span class="sub-plan-label">{{ t('subscription.current_plan') }}</span>
            <span class="sub-plan-name">{{ currentPlanLabel }}</span>
          </div>
          <div class="sub-quota-row">
            <span class="sub-quota-label">{{ t('subscription.remaining') }}</span>
            <span class="sub-quota-value">{{ remainingQuota }} / {{ totalQuota }}</span>
          </div>
          <div v-if="subscriptionData && subscriptionData.period_end" class="sub-expire-row">
            <span class="sub-expire-label">{{ t('subscription.expires') }}</span>
            <span class="sub-expire-value">{{ formatDate(subscriptionData.period_end) }}</span>
          </div>
        </div>

        <!-- 升级/订阅区 -->
        <div class="plans-section">
          <button class="upgrade-toggle-btn" @click="showPlans = !showPlans">
            {{ showPlans ? '▲' : t('subscription.upgrade_btn') }}
          </button>

          <div v-if="showPlans" class="plans-grid">
            <div
              v-for="plan in plans.filter(p => p.plan !== 'free')"
              :key="plan.plan"
              class="plan-card"
              :class="{ active: currentPlan === plan.plan }"
              @click="selectPlan(plan)"
            >
              <div class="plan-name">{{ plan.label }}</div>
              <div class="plan-price">${{ plan.price }} <span class="plan-period">/ {{ t('subscription.month') }}</span></div>
              <div class="plan-quota">{{ plan.quota }} {{ t('subscription.predictions') }}</div>
            </div>
          </div>

          <!-- 付款流程 -->
          <div v-if="selectedPlan" class="payment-section">
            <div class="payment-info">
              <p class="payment-plan">{{ t('subscription.subscribing_to') }}: <strong>{{ selectedPlan.label }}</strong></p>
              <p class="payment-amount">{{ t('subscription.amount') }}: <strong>${{ selectedPlan.price }} USDT</strong></p>
            </div>

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
              <input
                v-model="txHash"
                class="form-input tx-input"
                :placeholder="t('account.tx_hash_placeholder')"
              />

              <button
                class="submit-btn"
                :disabled="!txHash || submitting"
                @click="handleSubmitPayment"
              >
                {{ submitting ? t('account.verifying') : t('account.submit_verify') }}
              </button>

              <p v-if="paymentStatus === 'completed'" class="status-text success">{{ t('subscription.subscribe_success') }}</p>
              <p v-if="paymentStatus === 'failed'" class="status-text error">{{ paymentError || t('account.verify_failed') }}</p>
              <p v-if="paymentStatus === 'confirming'" class="status-text warning">{{ paymentError }}</p>
            </div>
          </div>
        </div>

        <button class="logout-btn-full" @click="handleLogout">{{ t('account.logout') }}</button>
      </div>

      <!-- 交易记录 Tab -->
      <div v-if="accountModal.tab === 'history'" class="account-body">
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
import { ref, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  authState, clearAuth, accountModal, closeAccountModal,
} from '../stores/auth'
import { logout as logoutApi } from '../api/auth'
import {
  getPlatformAddress, getTokenHistory,
  getPlans, getCurrentSubscription,
  createSubscriptionOrder, verifySubscriptionPayment,
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

// ---- Subscription ----
const currentPlan = ref('free')
const currentPlanLabel = ref('Free')
const remainingQuota = ref(0)
const totalQuota = ref(3)
const subscriptionData = ref(null)
const plans = ref([])
const showPlans = ref(false)
const selectedPlan = ref(null)
const orderNo = ref('')

async function refreshSubscription() {
  try {
    const res = await getCurrentSubscription()
    currentPlan.value = res.plan || 'free'
    currentPlanLabel.value = res.plan_label || 'Free'
    remainingQuota.value = res.remaining_quota || 0
    totalQuota.value = res.total_quota || 3
    subscriptionData.value = res.subscription
  } catch {}
}

async function loadPlans() {
  try {
    const res = await getPlans()
    plans.value = res.plans || []
  } catch {}
}

async function selectPlan(plan) {
  selectedPlan.value = plan
  paymentStatus.value = ''
  paymentError.value = ''
  orderNo.value = ''
  txHash.value = ''

  await loadPlatformAddress()
  nextTick(() => { drawQR() })
}

// ---- Payment ----
const platformAddress = ref('')
const copied = ref(false)
const txHash = ref('')
const submitting = ref(false)
const paymentStatus = ref('')
const paymentError = ref('')
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

watch(platformAddress, () => {
  nextTick(() => { drawQR() })
})

async function handleSubmitPayment() {
  if (!txHash.value || !selectedPlan.value) return
  submitting.value = true
  paymentStatus.value = ''
  paymentError.value = ''

  try {
    // 创建订单
    if (!orderNo.value) {
      const orderRes = await createSubscriptionOrder(selectedPlan.value.plan)
      orderNo.value = orderRes.order_no
    }

    // 提交验证
    const res = await verifySubscriptionPayment(orderNo.value, txHash.value.trim())
    if (res.success) {
      paymentStatus.value = 'completed'
      selectedPlan.value = null
      orderNo.value = ''
      txHash.value = ''
      showPlans.value = false
      refreshSubscription()
      refreshHistory()
    } else {
      paymentStatus.value = res.status || 'failed'
      paymentError.value = res.error || ''
    }
  } catch (err) {
    paymentStatus.value = 'failed'
    paymentError.value = err?.response?.data?.error || err.message || ''
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
    subscribe: t('subscription.subscribe'),
    predict_premium: t('subscription.prediction'),
    predict_normal: t('subscription.prediction'),
    refund: 'Refund',
  }
  return map[type] || type
}

function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours()}:${String(d.getMinutes()).padStart(2, '0')}`
}

function formatDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

// ---- Settings ----
const fastMode = ref(localStorage.getItem('fastMode') === 'true')

function saveFastMode() {
  localStorage.setItem('fastMode', String(fastMode.value))
}

// ---- Init on visible ----
watch(() => accountModal.visible, (val) => {
  if (val) {
    refreshSubscription()
    loadPlans()
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
  max-width: 520px;
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
.tab-btn:last-child { border-radius: 0 4px 4px 0; }
.tab-btn + .tab-btn { border-left: none; }

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

/* Subscription Status */
.subscription-status {
  background: #FAFAFA;
  border: 1px solid var(--border);
  padding: 16px;
  margin-bottom: 20px;
}

.sub-plan-row, .sub-quota-row, .sub-expire-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.sub-plan-row:last-child, .sub-quota-row:last-child, .sub-expire-row:last-child {
  margin-bottom: 0;
}

.sub-plan-label, .sub-quota-label, .sub-expire-label {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  color: var(--gray-text);
}

.sub-plan-name {
  font-family: var(--font-mono);
  font-size: 1rem;
  font-weight: 700;
  color: var(--orange);
}

.sub-quota-value {
  font-family: var(--font-mono);
  font-size: 0.9rem;
  font-weight: 700;
}

.sub-expire-value {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  color: #666;
}

/* Plans */
.plans-section {
  margin-bottom: 20px;
}

.upgrade-toggle-btn {
  background: none;
  border: 1px solid var(--orange);
  color: var(--orange);
  font-family: var(--font-mono);
  font-size: 0.75rem;
  font-weight: 700;
  padding: 6px 16px;
  cursor: pointer;
  transition: all 0.2s;
  margin-bottom: 12px;
}

.upgrade-toggle-btn:hover {
  background: var(--orange);
  color: var(--white);
}

.plans-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}

.plan-card {
  border: 2px solid var(--border);
  padding: 16px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
}

.plan-card:hover {
  border-color: var(--orange);
  box-shadow: 0 2px 8px rgba(255, 69, 0, 0.1);
}

.plan-card.active {
  border-color: var(--orange);
  background: #FFF5F0;
}

.plan-name {
  font-family: var(--font-mono);
  font-size: 0.85rem;
  font-weight: 700;
  margin-bottom: 6px;
}

.plan-price {
  font-family: var(--font-mono);
  font-size: 1.1rem;
  font-weight: 800;
  color: var(--orange);
  margin-bottom: 4px;
}

.plan-period {
  font-size: 0.7rem;
  font-weight: 400;
  color: #999;
}

.plan-quota {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--gray-text);
}

/* Payment */
.payment-section {
  background: #FAFAFA;
  border: 1px solid var(--border);
  padding: 16px;
}

.payment-info {
  margin-bottom: 12px;
}

.payment-info p {
  font-family: var(--font-mono);
  font-size: 0.85rem;
  margin: 0 0 4px 0;
  color: #666;
}

.payment-info strong {
  color: var(--black);
}

.deposit-address-area { margin-bottom: 12px; }

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

/* Settings */
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

/* Responsive */
@media (max-width: 480px) {
  .plans-grid { grid-template-columns: 1fr; }
}
</style>
