<template>
  <div class="prediction-container">
    <div class="main-content">
      <!-- ===== SELECT 状态（日期 + 比赛列表合并） ===== -->
      <section v-if="viewState === 'select'" class="input-section">
        <div class="section-header">
          <h1 class="page-title">{{ t('date_select.title') }}</h1>
          <p class="page-desc">{{ t('date_select.desc') }}</p>
        </div>

        <div class="date-picker-row">
          <span class="timezone-hint">{{ t('date_select.timezone') }}</span>
          <input v-model="selectedDate" class="form-input date-input" type="date" />
          <button class="fetch-btn" :disabled="!selectedDate || fetchingEvents" @click="fetchEvents">
            <span v-if="fetchingEvents">{{ t('date_select.fetching') }}</span>
            <span v-else>{{ t('date_select.fetch_btn') }}</span>
          </button>
        </div>

        <p v-if="fetchError" class="error-text">{{ fetchError }}</p>

        <!-- 比赛列表 -->
        <div v-if="eventsFetched" class="games-area">
          <div class="games-header">
            <h2 class="games-title">{{ t('game_select.games_title', { date: selectedDate }) }}</h2>
            <p class="games-count">{{ t('game_select.games_count', { count: events.length }) }}</p>
          </div>

          <div v-if="events.length === 0" class="empty-state">
            <p>{{ t('game_select.no_games') }}</p>
          </div>

          <div v-else class="game-grid">
            <div
              v-for="event in events"
              :key="event.event_id"
              class="game-card"
              @click="selectGame(event)"
            >
              <div class="game-teams">
                <div class="team away-team">
                  <span class="team-abbr">{{ event.away_team.abbreviation }}</span>
                  <span class="team-name">{{ event.away_team.name }}</span>
                </div>
                <span class="at-symbol">@</span>
                <div class="team home-team">
                  <span class="team-abbr">{{ event.home_team.abbreviation }}</span>
                  <span class="team-name">{{ event.home_team.name }}</span>
                </div>
              </div>

              <div class="game-odds">
                <div v-if="event.market_odds.moneyline_home != null" class="odds-row">
                  <span class="odds-label">{{ t('odds.moneyline') }}</span>
                  <span class="odds-values">
                    {{ event.away_team.abbreviation }}
                    <strong>{{ (event.market_odds.moneyline_away * 100).toFixed(1) }}%</strong>
                    &mdash;
                    {{ event.home_team.abbreviation }}
                    <strong>{{ (event.market_odds.moneyline_home * 100).toFixed(1) }}%</strong>
                  </span>
                </div>
                <div v-if="event.market_odds.spread_line != null" class="odds-row">
                  <span class="odds-label">{{ t('odds.spread') }}</span>
                  <span class="odds-values">
                    {{ event.home_team.abbreviation }}
                    <strong>{{ event.market_odds.spread_line > 0 ? '+' : '' }}{{ event.market_odds.spread_line }}</strong>
                  </span>
                </div>
                <div v-if="event.market_odds.total_line != null" class="odds-row">
                  <span class="odds-label">{{ t('odds.total') }}</span>
                  <span class="odds-values">O/U <strong>{{ event.market_odds.total_line }}</strong></span>
                </div>
                <div v-if="event.market_odds.volume" class="odds-row volume-row">
                  <span class="odds-label">{{ t('odds.volume') }}</span>
                  <span class="odds-values">${{ formatVolume(event.market_odds.volume) }}</span>
                </div>
              </div>

              <div class="card-action">{{ t('game_select.click_predict') }} &rarr;</div>
            </div>
          </div>

          <p v-if="submitError" class="error-text">{{ submitError }}</p>
        </div>

        <!-- 预测类型选择面板 -->
        <div v-if="showTypePanel" class="type-panel-overlay" @click.self="showTypePanel = false">
          <div class="type-panel">
            <h3 class="type-panel-title">{{ t('predict_type.choose_title') }}</h3>
            <p class="type-panel-balance">
              {{ t('predict_type.current_balance') }}: <strong>{{ userBalance.toFixed(2) }} Token</strong>
            </p>

            <div class="type-options">
              <div
                class="type-card"
                :class="{ disabled: userBalance < 2 }"
                @click="userBalance >= 2 && confirmPredict('normal')"
              >
                <div class="type-name">{{ t('predict_type.normal') }}</div>
                <div class="type-desc">{{ t('predict_type.normal_desc') }}</div>
                <div class="type-cost">{{ t('predict_type.normal_cost') }}</div>
                <div class="type-eta">{{ t('predict_type.normal_eta') }}</div>
              </div>

              <div
                class="type-card premium"
                :class="{ disabled: userBalance < 4 }"
                @click="userBalance >= 4 && confirmPredict('premium')"
              >
                <div class="type-name">{{ t('predict_type.premium') }}</div>
                <div class="type-desc">{{ t('predict_type.premium_desc') }}</div>
                <div class="type-cost">{{ t('predict_type.premium_cost') }}</div>
                <div class="type-eta">{{ t('predict_type.premium_eta') }}</div>
              </div>
            </div>

            <p v-if="userBalance < 2" class="insufficient-text">{{ t('predict_type.insufficient') }}</p>
          </div>
        </div>
      </section>

      <!-- ===== PROGRESS 状态 (双栏布局) ===== -->
      <section v-if="viewState === 'progress'" class="progress-section">
        <!-- 顶部进度条 -->
        <div class="progress-top-bar">
          <div class="progress-matchup">{{ activeAway }} {{ t(`team.${activeAway}`, '') }} @ {{ activeHome }} {{ t(`team.${activeHome}`, '') }}</div>
          <div class="progress-status-text">{{ taskMessage }}</div>
          <div class="progress-bar-container">
            <div class="progress-bar" :style="{ width: taskProgress + '%' }"></div>
          </div>
          <div class="progress-info">
            <span class="progress-percent">{{ taskProgress }}%</span>
            <span v-if="etaText" class="progress-eta">{{ etaText }}</span>
          </div>
        </div>

        <!-- 双栏：图谱 + 步骤卡片 -->
        <div :class="['dual-panel', { 'no-graph': !graphData }]">
          <div v-if="graphData" class="panel-left">
            <GraphPanel :graphData="graphData" />
          </div>
          <div class="panel-right">
            <StepCard
              v-for="s in detailSteps"
              :key="s.step"
              :step="s"
              :homeAbbr="activeHome"
              :awayAbbr="activeAway"
            />
            <!-- 底部日志栏 -->
            <div class="system-dashboard">
              <div class="dashboard-label">{{ t('progress.system_dashboard') }}</div>
              <div class="dashboard-log">{{ taskMessage }}</div>
            </div>
          </div>
        </div>
      </section>

      <!-- ===== RESULT 状态 ===== -->
      <section v-if="viewState === 'result'" class="result-section">
        <div class="result-header">
          <h2>{{ activeAway }} {{ t(`team.${activeAway}`, '') }} @ {{ activeHome }} {{ t(`team.${activeHome}`, '') }}</h2>
          <span v-if="formattedGameTime" class="result-game-time">{{ formattedGameTime }}</span>
          <button class="new-btn" @click="resetToDateSelect">{{ t('result.new_prediction') }}</button>
        </div>

        <!-- Graph Panel (if available) -->
        <div v-if="graphData" class="result-card graph-result-card">
          <div class="graph-result-container">
            <GraphPanel :graphData="graphData" />
          </div>
        </div>

        <!-- Game Result Card -->
        <div v-if="gameResult" class="result-card game-result-card">
          <h3 class="card-title">{{ t('result.game_result_title') }}</h3>
          <div class="game-result-content">
            <div class="game-score-display">
              <div class="score-team">
                <span class="score-abbr">{{ gameResult.away_abbr }}</span>
                <span class="score-number">{{ gameResult.away_score }}</span>
              </div>
              <div class="score-divider">
                <span class="final-badge">{{ t('result.final') }}</span>
              </div>
              <div class="score-team">
                <span class="score-abbr">{{ gameResult.home_abbr }}</span>
                <span class="score-number">{{ gameResult.home_score }}</span>
              </div>
            </div>
            <div v-if="gameResult.hit_status" class="hit-status-row">
              <div
                v-for="m in ['moneyline', 'spread', 'total']"
                :key="m"
                class="hit-market"
              >
                <span class="hit-market-label">{{ marketLabel(m) }}</span>
                <span
                  class="hit-market-badge"
                  :class="hitClass(gameResult.hit_status[m + '_hit'])"
                >
                  {{ hitLabel(gameResult.hit_status[m + '_hit']) }}
                </span>
              </div>
            </div>
          </div>
        </div>

        <!-- Fetch Game Result Button (no game_result yet) -->
        <div v-else-if="viewState === 'result'" class="fetch-result-row">
          <button
            class="fetch-result-btn"
            :disabled="fetchingGameResult"
            @click="handleFetchGameResult"
          >
            {{ fetchingGameResult ? t('result.fetching_result') : t('result.fetch_game_result') }}
          </button>
          <span v-if="gameResultError" class="error-text game-result-error">{{ gameResultError }}</span>
        </div>

        <!-- L1: Betting Card -->
        <div class="result-card">
          <h3 class="card-title">{{ t('result.l1_title') }}</h3>
          <div class="betting-cards">
            <div v-for="card in bettingCard" :key="card.market" class="bet-card" :class="card.recommendation">
              <div class="bet-market">{{ marketLabel(card.market) }}</div>
              <div class="bet-versus">
                <div class="bet-side">
                  <div class="bet-pick">{{ card.pick }}</div>
                  <div class="bet-prob">{{ (card.model_probability * 100).toFixed(1) }}%</div>
                </div>
                <span class="bet-vs">vs</span>
                <div class="bet-side">
                  <div class="bet-pick opp">{{ card.opponent_pick }}</div>
                  <div class="bet-prob opp">{{ card.opponent_probability != null ? (card.opponent_probability * 100).toFixed(1) + '%' : '' }}</div>
                </div>
              </div>
              <div class="bet-label">{{ t('result.model_prob') }}</div>
              <div v-if="card.market_probability != null" class="bet-market-prob">
                {{ t('result.market_label') }} {{ (card.market_probability * 100).toFixed(1) }}%
              </div>
              <div v-if="card.edge != null" class="bet-edge" :class="{ positive: card.edge > 0 }">
                Edge: {{ (card.edge * 100).toFixed(1) }}%
              </div>
              <div class="bet-rec">{{ recLabel(card.recommendation) }}</div>
            </div>
          </div>
        </div>

        <!-- L2: Key Factors -->
        <div class="result-card collapsible" :class="{ expanded: showL2 }">
          <h3 class="card-title clickable" @click="showL2 = !showL2">
            {{ t('result.l2_title') }}
            <span class="expand-icon">{{ showL2 ? '-' : '+' }}</span>
          </h3>
          <div v-if="showL2" class="card-body">
            <div v-if="l2Data">
              <div class="consensus-badge">{{ l2Data.consensus }}</div>
              <ul class="factors-list">
                <li v-for="(factor, i) in l2Data.key_factors" :key="i">{{ factor }}</li>
              </ul>
            </div>
            <div v-else class="loading-text">{{ t('result.loading') }}</div>
          </div>
        </div>

        <!-- L3: Debate Log -->
        <div class="result-card collapsible" :class="{ expanded: showL3 }">
          <h3 class="card-title clickable" @click="toggleL3">
            {{ t('result.l3_title') }}
            <span class="expand-icon">{{ showL3 ? '-' : '+' }}</span>
          </h3>
          <div v-if="showL3" class="card-body">
            <div v-if="l3Data">
              <div class="debate-stats">
                {{ t('result.llm_calls') }} {{ l3Data.debate_log.total_llm_calls }}{{ t('result.calls_unit') }} |
                {{ t('result.duration') }} {{ l3Data.debate_log.total_duration_seconds.toFixed(1) }}{{ t('result.seconds_unit') }}
              </div>
              <div v-for="round in l3Data.debate_log.rounds" :key="round.round_num" class="debate-round">
                <h4 class="round-title">Round {{ round.round_num }}</h4>
                <div v-for="pred in round.predictions" :key="pred.analyst_id" class="analyst-pred">
                  <div class="analyst-name">{{ t(`analyst.${pred.analyst_id}.name`, pred.analyst_id) }}</div>
                  <div class="analyst-role-desc">{{ t(`analyst.${pred.analyst_id}.desc`, '') }}</div>
                  <div class="analyst-picks">
                    ML: {{ pred.moneyline_pick }} ({{ (pred.moneyline_confidence * 100).toFixed(0) }}%) |
                    Spread: {{ pred.spread_pick }} |
                    Total: {{ pred.total_pick }}
                  </div>
                  <div class="analyst-reasoning">{{ pred.reasoning }}</div>
                  <div v-if="pred.changed_from_previous" class="analyst-change">
                    Changed: {{ pred.change_reasoning }}
                  </div>
                </div>
              </div>
            </div>
            <div v-else class="loading-text">{{ t('result.loading') }}</div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  getPolymarketEvents,
  createPrediction,
  getPredictionTask,
  getPredictionResult,
  fetchGameResult,
} from '../api/prediction'
import { getBalance } from '../api/deposit'
import { isLoggedIn, openAuthModal } from '../stores/auth'
import GraphPanel from '../components/GraphPanel.vue'
import StepCard from '../components/StepCard.vue'

const route = useRoute()
const { t, locale } = useI18n()

// ---- State machine: select | progress | result ----
const viewState = ref('select')

// Date select — default to tomorrow in US Eastern time
function getTomorrowET() {
  const now = new Date()
  // Get current date parts in America/New_York timezone
  const etParts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'America/New_York',
    year: 'numeric', month: '2-digit', day: '2-digit',
  }).format(now) // returns "YYYY-MM-DD" in en-CA locale
  // Add 1 day
  const d = new Date(etParts + 'T12:00:00')
  d.setDate(d.getDate() + 1)
  return d.toISOString().slice(0, 10)
}
const selectedDate = ref(getTomorrowET())
const fetchingEvents = ref(false)
const fetchError = ref('')
const events = ref([])
const eventsFetched = ref(false)

// Active game info (for progress/result headers)
const activeHome = ref('')
const activeAway = ref('')
const activeGameDate = ref('')
const activeGameTime = ref('')

// Progress
const taskId = ref('')
const matchupId = ref('')
const taskProgress = ref(0)
const taskMessage = ref('')
const submitError = ref('')
let pollTimer = null
let pollStartTime = null

const etaText = computed(() => {
  const p = taskProgress.value
  if (!pollStartTime || p <= 0 || p >= 100) return ''
  const elapsed = (Date.now() - pollStartTime) / 1000
  const totalEstimate = elapsed / (p / 100)
  const remaining = Math.max(0, totalEstimate - elapsed)
  const mins = Math.floor(remaining / 60)
  const secs = Math.floor(remaining % 60)
  return mins > 0 ? `~${mins}:${String(secs).padStart(2, '0')}` : `~${secs}s`
})

// Rich progress data
const detailSteps = ref([])
const graphData = ref(null)

// Results
const bettingCard = ref([])
const showL2 = ref(false)
const showL3 = ref(false)
const l2Data = ref(null)
const l3Data = ref(null)

// Game result
const gameResult = ref(null)
const fetchingGameResult = ref(false)
const gameResultError = ref('')

const formattedGameTime = computed(() => {
  const gt = activeGameTime.value
  if (!gt) return ''
  try {
    const d = new Date(gt)
    if (isNaN(d.getTime())) return gt
    const et = d.toLocaleString('en-US', {
      timeZone: 'America/New_York',
      month: 'numeric', day: 'numeric', year: 'numeric',
      hour: 'numeric', minute: '2-digit', hour12: true,
    })
    if (locale.value !== 'zh') return `${et} ET`
    const bj = d.toLocaleString('zh-CN', {
      timeZone: 'Asia/Shanghai',
      month: 'numeric', day: 'numeric', year: 'numeric',
      hour: 'numeric', minute: '2-digit', hour12: false,
    })
    return `${et} ET (${bj} ${t('history.beijing')})`
  } catch {
    return gt
  }
})

// ---- Date select ----

async function fetchEvents() {
  fetchError.value = ''
  fetchingEvents.value = true
  eventsFetched.value = false

  try {
    const res = await getPolymarketEvents(selectedDate.value)
    events.value = res.events || []
    eventsFetched.value = true
  } catch (err) {
    fetchError.value = err.message || t('date_select.fetch_error')
  } finally {
    fetchingEvents.value = false
  }
}

// ---- Prediction type selection ----
const showTypePanel = ref(false)
const userBalance = ref(0)
const selectedEvent = ref(null)

async function selectGame(event) {
  // 未登录时弹出登录框
  if (!isLoggedIn()) {
    openAuthModal('login')
    return
  }

  submitError.value = ''
  selectedEvent.value = event
  activeHome.value = event.home_team.abbreviation
  activeAway.value = event.away_team.abbreviation
  activeGameDate.value = event.game_date || selectedDate.value
  activeGameTime.value = event.game_time || ''

  // 获取余额
  try {
    const balRes = await getBalance()
    userBalance.value = balRes.balance || 0
  } catch {
    userBalance.value = 0
  }

  showTypePanel.value = true
}

async function confirmPredict(predictionType) {
  showTypePanel.value = false
  const event = selectedEvent.value
  if (!event) return

  const payload = {
    home_team: { name: event.home_team.name, abbreviation: event.home_team.abbreviation },
    away_team: { name: event.away_team.name, abbreviation: event.away_team.abbreviation },
    market_odds: event.market_odds,
    game_date: event.game_date,
    game_time: event.game_time || '',
    condition_id: event.condition_id || '',
    token_ids: event.token_ids || [],
    source: 'polymarket',
    lang: locale.value,
    fast_mode: localStorage.getItem('fastMode') === 'true',
    debate_rounds: parseInt(localStorage.getItem('debateRounds') || '3', 10),
  }

  try {
    const res = await createPrediction(payload, predictionType)
    taskId.value = res.task_id
    matchupId.value = res.matchup_id
    viewState.value = 'progress'
    // 持久化活跃任务，防止页面关闭后丢失
    _saveActiveTask()
    startPolling()
  } catch (err) {
    const errData = err?.response?.data
    if (errData?.error === '余额不足') {
      submitError.value = t('predict_type.insufficient')
    } else {
      submitError.value = err.message || t('game_select.submit_error')
    }
  }
}

// ---- Progress polling ----

function startPolling() {
  taskProgress.value = 0
  taskMessage.value = t('progress.task_submitted')
  detailSteps.value = []
  graphData.value = null
  pollStartTime = Date.now()

  pollTimer = setInterval(async () => {
    try {
      const res = await getPredictionTask(taskId.value)
      const task = res.task
      taskProgress.value = task.progress || 0
      taskMessage.value = task.message || ''

      // 提取丰富进度数据
      const detail = task.progress_detail || {}
      if (detail.steps) {
        detailSteps.value = detail.steps
      }
      if (detail.graph_data && detail.graph_data.nodes) {
        graphData.value = detail.graph_data
      }

      if (task.status === 'completed') {
        stopPolling()
        _clearActiveTask()
        await loadResult()
      } else if (task.status === 'failed') {
        stopPolling()
        _clearActiveTask()
        submitError.value = task.error || t('result.prediction_failed')
        viewState.value = 'select'
      }
    } catch {
      // retry silently
    }
  }, 2000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

// ---- Active task persistence (survive page close / screen lock) ----

function _saveActiveTask() {
  try {
    localStorage.setItem('activeTask', JSON.stringify({
      taskId: taskId.value,
      matchupId: matchupId.value,
      home: activeHome.value,
      away: activeAway.value,
      gameDate: activeGameDate.value,
      gameTime: activeGameTime.value,
      ts: Date.now(),
    }))
  } catch {}
}

function _clearActiveTask() {
  localStorage.removeItem('activeTask')
}

function _loadActiveTask() {
  try {
    const raw = localStorage.getItem('activeTask')
    if (!raw) return null
    const data = JSON.parse(raw)
    // 超过 24 小时的视为过期
    if (Date.now() - (data.ts || 0) > 24 * 3600 * 1000) {
      _clearActiveTask()
      return null
    }
    return data
  } catch {
    return null
  }
}

// ---- Result ----

async function loadResult() {
  try {
    const res = await getPredictionResult(matchupId.value, 'L1')
    bettingCard.value = res.prediction.betting_card || []
    if (res.prediction.graph_data) {
      graphData.value = res.prediction.graph_data
    }
    if (res.prediction.game_result) {
      gameResult.value = res.prediction.game_result
    }
    viewState.value = 'result'

    // Pre-fetch L2
    const l2res = await getPredictionResult(matchupId.value, 'L2')
    l2Data.value = l2res.prediction
  } catch (err) {
    submitError.value = t('result.fetch_error') + ': ' + (err.message || '')
    viewState.value = 'select'
  }
}

async function toggleL3() {
  showL3.value = !showL3.value
  if (showL3.value && !l3Data.value) {
    try {
      const res = await getPredictionResult(matchupId.value, 'L3')
      l3Data.value = res.prediction
    } catch {
      // silently fail
    }
  }
}

// ---- Game Result ----

async function handleFetchGameResult() {
  if (!matchupId.value) return
  fetchingGameResult.value = true
  gameResultError.value = ''
  try {
    const res = await fetchGameResult(matchupId.value, {
      home: activeHome.value,
      away: activeAway.value,
      game_date: activeGameDate.value,
    })
    gameResult.value = res.game_result
  } catch (err) {
    const errData = err?.response?.data || err
    if (errData?.error === 'game_not_ended') {
      gameResultError.value = t('result.fetch_result_failed')
    } else {
      gameResultError.value = t('result.fetch_result_failed')
    }
  } finally {
    fetchingGameResult.value = false
  }
}

function hitClass(val) {
  if (val === true) return 'hit-yes'
  if (val === false) return 'hit-no'
  return 'hit-push'
}

function hitLabel(val) {
  if (val === true) return t('result.hit')
  if (val === false) return t('result.miss')
  return t('result.push')
}

// ---- Helpers ----

function marketLabel(market) {
  const key = `odds.${market}`
  return t(key) || market
}

function recLabel(rec) {
  const key = `rec.${rec}`
  return t(key) || rec
}

function formatVolume(vol) {
  if (vol >= 1_000_000) return (vol / 1_000_000).toFixed(1) + 'M'
  if (vol >= 1_000) return (vol / 1_000).toFixed(1) + 'K'
  return vol.toFixed(0)
}

function resetToDateSelect() {
  stopPolling()
  _clearActiveTask()
  viewState.value = 'select'
  events.value = []
  eventsFetched.value = false
  bettingCard.value = []
  l2Data.value = null
  l3Data.value = null
  showL2.value = false
  showL3.value = false
  taskId.value = ''
  matchupId.value = ''
  taskProgress.value = 0
  submitError.value = ''
  fetchError.value = ''
  detailSteps.value = []
  graphData.value = null
  gameResult.value = null
  fetchingGameResult.value = false
  gameResultError.value = ''
  activeGameDate.value = ''
  activeGameTime.value = ''
  showTypePanel.value = false
  selectedEvent.value = null
}

// 导航栏点击"预测"时，query._t 变化 → 重置到选赛页
watch(() => route.query._t, (newT) => {
  if (newT && viewState.value !== 'select') {
    resetToDateSelect()
    fetchEvents()
  }
})

// 支持从 URL 参数恢复结果（历史记录跳转）+ 恢复活跃任务
onMounted(async () => {
  // 1. URL 参数优先（历史记录跳转）
  const qMatchupId = route.query.matchup_id
  if (qMatchupId) {
    matchupId.value = qMatchupId
    activeHome.value = route.query.home || ''
    activeAway.value = route.query.away || ''
    activeGameDate.value = route.query.game_date || ''
    activeGameTime.value = route.query.game_time || ''
    try {
      const res = await getPredictionResult(qMatchupId, 'L1')
      bettingCard.value = res.prediction.betting_card || []
      if (res.prediction.graph_data) {
        graphData.value = res.prediction.graph_data
      }
      if (res.prediction.game_result) {
        gameResult.value = res.prediction.game_result
      }
      viewState.value = 'result'

      // Pre-fetch L2
      const l2res = await getPredictionResult(qMatchupId, 'L2')
      l2Data.value = l2res.prediction
    } catch {
      // 结果不存在，回到默认状态
    }
    return
  }

  // 2. 恢复活跃任务（页面关闭/锁屏后重新打开）
  const saved = _loadActiveTask()
  if (saved && saved.taskId) {
    try {
      const res = await getPredictionTask(saved.taskId)
      const task = res.task
      if (task.status === 'completed') {
        // 任务已完成，直接展示结果
        _clearActiveTask()
        taskId.value = saved.taskId
        matchupId.value = saved.matchupId
        activeHome.value = saved.home || ''
        activeAway.value = saved.away || ''
        activeGameDate.value = saved.gameDate || ''
        activeGameTime.value = saved.gameTime || ''
        await loadResult()
      } else if (task.status === 'failed') {
        // 任务已失败，清除并提示
        _clearActiveTask()
      } else {
        // 任务仍在运行，恢复进度页和轮询
        taskId.value = saved.taskId
        matchupId.value = saved.matchupId
        activeHome.value = saved.home || ''
        activeAway.value = saved.away || ''
        activeGameDate.value = saved.gameDate || ''
        activeGameTime.value = saved.gameTime || ''
        taskProgress.value = task.progress || 0
        taskMessage.value = task.message || ''
        const detail = task.progress_detail || {}
        if (detail.steps) detailSteps.value = detail.steps
        if (detail.graph_data && detail.graph_data.nodes) graphData.value = detail.graph_data
        viewState.value = 'progress'
        startPolling()
      }
    } catch {
      _clearActiveTask()
    }
  }

  // 3. Auto-fetch events for the default date when landing fresh
  if (viewState.value === 'select' && !eventsFetched.value) {
    fetchEvents()
  }
})
</script>

<style scoped>
.prediction-container {
  min-height: calc(100vh - 56px);
  background: var(--white);
  font-family: var(--font-sans);
  color: var(--black);
  overflow: hidden;
}

.main-content {
  max-width: 1400px;
  margin: 0 auto;
  padding: 40px 20px;
}

/* ===== SELECT / RESULT: cap width ===== */
.input-section, .result-section { max-width: 960px; margin: 0 auto; }

/* ===== DATE SELECT ===== */
.section-header { margin-bottom: 40px; }

.page-title {
  font-size: 2.5rem;
  font-weight: 600;
  margin: 0 0 10px 0;
}

.page-desc {
  color: var(--gray-text);
  font-size: 1rem;
}

.date-picker-row {
  display: flex;
  gap: 16px;
  align-items: center;
  max-width: 480px;
}

.timezone-hint {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--gray-text);
  white-space: nowrap;
}

.date-input {
  flex: 1;
}

.form-input {
  border: 1px solid var(--border);
  background: #FAFAFA;
  padding: 12px 16px;
  font-family: var(--font-mono);
  font-size: 0.9rem;
  outline: none;
  transition: border-color 0.2s;
}

.form-input:focus { border-color: var(--black); }

.fetch-btn {
  background: var(--black);
  color: var(--white);
  border: none;
  padding: 12px 28px;
  font-family: var(--font-mono);
  font-weight: 700;
  font-size: 0.95rem;
  cursor: pointer;
  transition: background 0.3s;
  white-space: nowrap;
}

.fetch-btn:not(:disabled):hover { background: var(--orange); }
.fetch-btn:disabled { background: #E5E5E5; color: #999; cursor: not-allowed; }

.error-text {
  color: #CC0000;
  font-size: 0.85rem;
  margin-top: 12px;
}

/* ===== GAMES AREA ===== */
.games-area {
  margin-top: 40px;
}

.games-header {
  margin-bottom: 24px;
}

.games-title {
  font-family: var(--font-mono);
  font-size: 1.4rem;
  font-weight: 700;
  margin: 0 0 6px 0;
}

.games-count {
  color: var(--gray-text);
  font-size: 0.9rem;
  margin: 0;
}

/* ===== GAME CARDS ===== */

.empty-state {
  text-align: center;
  padding: 60px 0;
  color: var(--gray-text);
  font-size: 1.1rem;
}

.game-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(420px, 1fr));
  gap: 20px;
}

.game-card {
  border: 1px solid var(--border);
  background: #FAFAFA;
  padding: 24px;
  cursor: pointer;
  transition: all 0.2s;
}

.game-card:hover {
  border-color: var(--black);
  box-shadow: 0 2px 12px rgba(0,0,0,0.08);
}

.game-teams {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  margin-bottom: 20px;
}

.team {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.team-abbr {
  font-family: var(--font-mono);
  font-size: 1.6rem;
  font-weight: 800;
  letter-spacing: 1px;
}

.team-name {
  font-size: 0.75rem;
  color: var(--gray-text);
  text-align: center;
}

.at-symbol {
  font-family: var(--font-mono);
  font-size: 1.1rem;
  color: #999;
}

.game-odds {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 16px;
}

.odds-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-family: var(--font-mono);
  font-size: 0.8rem;
}

.odds-label {
  color: #999;
  text-transform: uppercase;
  font-size: 0.7rem;
  min-width: 50px;
}

.odds-values {
  color: #333;
}

.odds-values strong {
  color: var(--black);
}

.volume-row .odds-values {
  color: var(--orange);
  font-weight: 600;
}

.card-action {
  text-align: center;
  font-family: var(--font-mono);
  font-size: 0.8rem;
  color: #999;
  padding-top: 12px;
  border-top: 1px solid #F0F0F0;
  transition: color 0.2s;
}

.game-card:hover .card-action { color: var(--orange); }

/* ===== PROGRESS (双栏布局) ===== */
.progress-section { padding: 0; }

.progress-top-bar {
  position: sticky;
  top: 0;
  z-index: 10;
  background: var(--white);
  padding: 20px 0;
  margin-bottom: 20px;
}

.progress-matchup {
  font-family: var(--font-mono);
  font-size: 1.4rem;
  font-weight: 800;
  margin-bottom: 4px;
}

.progress-status-text {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  color: var(--gray-text);
  margin-bottom: 12px;
}

.progress-bar-container {
  width: 100%;
  height: 6px;
  background: #EEE;
  margin-bottom: 8px;
}

.progress-bar {
  height: 100%;
  background: var(--orange);
  transition: width 0.5s ease;
}

.progress-info {
  display: flex;
  justify-content: space-between;
  font-family: var(--font-mono);
  font-size: 0.8rem;
  color: #666;
}

.progress-percent { font-weight: 700; color: var(--black); }

.progress-eta {
  color: var(--gray-text);
  font-size: 0.8rem;
}

/* 双栏 */
.dual-panel {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  min-height: 600px;
}

.panel-left {
  position: sticky;
  top: 20px;
  align-self: start;
  height: calc(100vh - 200px);
  min-height: 500px;
}

.panel-right {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.dual-panel.no-graph {
  grid-template-columns: 1fr;
  min-height: auto;
}

.system-dashboard {
  margin-top: 12px;
  background: #1A1A2E;
  color: #AAA;
  padding: 12px 16px;
  font-family: var(--font-mono);
  font-size: 0.7rem;
}

.dashboard-label {
  color: #666;
  font-size: 0.6rem;
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-bottom: 6px;
}

.dashboard-log {
  color: #4ECDC4;
}

/* ===== RESULT ===== */
.result-header {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 32px;
  gap: 4px 16px;
}

.result-header h2 {
  font-family: var(--font-mono);
  font-size: 1.5rem;
}

.result-game-time {
  width: 100%;
  font-family: var(--font-mono);
  font-size: 0.8rem;
  color: #888;
  order: 3;
}

.new-btn {
  background: none;
  border: 1px solid var(--black);
  padding: 8px 20px;
  font-family: var(--font-mono);
  font-size: 0.85rem;
  cursor: pointer;
  transition: all 0.2s;
}

.new-btn:hover { background: var(--black); color: var(--white); }

.result-card {
  border: 1px solid var(--border);
  padding: 24px;
  margin-bottom: 20px;
}

.card-title {
  font-family: var(--font-mono);
  font-size: 0.9rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 1px;
  margin: 0 0 20px 0;
  color: #333;
}

.card-title.clickable {
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-title.clickable:hover { color: var(--orange); }

.expand-icon {
  font-size: 1.2rem;
  font-weight: 400;
}

.collapsible .card-title { margin-bottom: 0; }
.collapsible.expanded .card-title { margin-bottom: 20px; }

/* Betting Cards */
.betting-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.bet-card {
  border: 1px solid var(--border);
  padding: 20px;
  text-align: center;
  transition: border-color 0.2s;
}

.bet-card.value_bet { border-color: #00AA00; background: #F0FFF0; }
.bet-card.lean { border-color: #0066CC; background: #F0F6FF; }
.bet-card.fade { border-color: #CC0000; background: #FFF0F0; }

.bet-market {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: #999;
  text-transform: uppercase;
  margin-bottom: 8px;
}

.bet-versus {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin-bottom: 8px;
}

.bet-side {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 80px;
}

.bet-vs {
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: #999;
}

.bet-pick {
  font-family: var(--font-mono);
  font-size: 1.2rem;
  font-weight: 700;
}

.bet-pick.opp {
  color: #999;
  font-weight: 600;
}

.bet-prob {
  font-family: var(--font-mono);
  font-size: 1rem;
  font-weight: 700;
  color: var(--black);
}

.bet-prob.opp {
  color: #999;
  font-weight: 600;
}

.bet-label {
  font-family: var(--font-mono);
  font-size: 0.65rem;
  color: #999;
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-bottom: 8px;
}

.bet-market-prob {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  color: #666;
  margin-bottom: 4px;
}

.bet-edge {
  font-family: var(--font-mono);
  font-size: 0.85rem;
  font-weight: 600;
  color: #CC0000;
  margin-bottom: 8px;
}

.bet-edge.positive { color: #00AA00; }

.bet-rec {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 1px;
  padding: 4px 8px;
  background: #F5F5F5;
  display: inline-block;
}

/* Graph in result */
.graph-result-card {
  padding: 0;
  overflow: hidden;
}

.graph-result-container {
  height: 450px;
}

/* L2 */
.consensus-badge {
  background: var(--black);
  color: var(--white);
  padding: 8px 16px;
  font-family: var(--font-mono);
  font-size: 0.85rem;
  display: inline-block;
  margin-bottom: 16px;
}

.factors-list {
  list-style: none;
  padding: 0;
}

.factors-list li {
  padding: 8px 0;
  border-bottom: 1px solid #F0F0F0;
  font-size: 0.95rem;
  line-height: 1.6;
}

.factors-list li::before {
  content: '> ';
  font-family: var(--font-mono);
  color: var(--orange);
  font-weight: 700;
}

/* L3 */
.debate-stats {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  color: #999;
  margin-bottom: 20px;
}

.debate-round {
  margin-bottom: 24px;
}

.round-title {
  font-family: var(--font-mono);
  font-size: 0.85rem;
  font-weight: 700;
  border-bottom: 2px solid var(--black);
  padding-bottom: 8px;
  margin-bottom: 12px;
}

.analyst-pred {
  padding: 12px 0;
  border-bottom: 1px solid #F0F0F0;
}

.analyst-name {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  font-weight: 700;
  color: var(--orange);
  margin-bottom: 2px;
}

.analyst-role-desc {
  font-size: 0.75rem;
  color: #999;
  margin-bottom: 6px;
  line-height: 1.4;
}

.analyst-picks {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  color: #333;
  margin-bottom: 6px;
}

.analyst-reasoning {
  font-size: 0.85rem;
  color: #666;
  line-height: 1.5;
}

.analyst-change {
  font-size: 0.8rem;
  color: #CC6600;
  font-style: italic;
  margin-top: 4px;
}

.loading-text {
  font-family: var(--font-mono);
  font-size: 0.85rem;
  color: #999;
}

/* Game Result Card */
.game-result-card {
  border-color: #333;
}

.game-result-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.game-score-display {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 32px;
}

.score-team {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.score-abbr {
  font-family: var(--font-mono);
  font-size: 1rem;
  font-weight: 700;
  color: #666;
  letter-spacing: 1px;
}

.score-number {
  font-family: var(--font-mono);
  font-size: 2.5rem;
  font-weight: 800;
  color: var(--black);
}

.score-divider {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.final-badge {
  font-family: var(--font-mono);
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 1px;
  color: var(--white);
  background: var(--black);
  padding: 3px 10px;
}

.hit-status-row {
  display: flex;
  justify-content: center;
  gap: 24px;
}

.hit-market {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}

.hit-market-label {
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: #999;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.hit-market-badge {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  font-weight: 700;
  padding: 3px 12px;
  letter-spacing: 0.5px;
}

.hit-market-badge.hit-yes {
  background: #F0FFF0;
  color: #00AA00;
  border: 1px solid #00AA00;
}

.hit-market-badge.hit-no {
  background: #FFF0F0;
  color: #CC0000;
  border: 1px solid #CC0000;
}

.hit-market-badge.hit-push {
  background: #F5F5F5;
  color: #999;
  border: 1px solid #E5E5E5;
}

.fetch-result-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}

.fetch-result-btn {
  background: none;
  border: 1px solid var(--border);
  padding: 10px 24px;
  font-family: var(--font-mono);
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.fetch-result-btn:not(:disabled):hover {
  border-color: var(--orange);
  color: var(--orange);
}

.fetch-result-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.game-result-error {
  font-family: var(--font-mono);
  font-size: 0.8rem;
}

/* ===== Type Selection Panel ===== */
.type-panel-overlay {
  position: fixed;
  top: 0; left: 0;
  width: 100%; height: 100%;
  background: rgba(0, 0, 0, 0.5);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.type-panel {
  background: var(--white);
  max-width: 520px;
  width: 90%;
  padding: 32px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
}

.type-panel-title {
  font-family: var(--font-mono);
  font-size: 1.1rem;
  font-weight: 700;
  margin: 0 0 8px 0;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.type-panel-balance {
  font-family: var(--font-mono);
  font-size: 0.85rem;
  color: var(--gray-text);
  margin: 0 0 24px 0;
}

.type-panel-balance strong {
  color: var(--orange);
}

.type-options {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}

.type-card {
  border: 2px solid var(--border);
  padding: 20px;
  cursor: pointer;
  transition: all 0.2s;
  text-align: center;
}

.type-card:hover:not(.disabled) {
  border-color: var(--black);
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

.type-card.premium {
  border-color: var(--orange);
}

.type-card.premium:hover:not(.disabled) {
  border-color: var(--orange);
  box-shadow: 0 2px 12px rgba(255, 69, 0, 0.15);
}

.type-card.disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.type-name {
  font-family: var(--font-mono);
  font-size: 1rem;
  font-weight: 700;
  margin-bottom: 8px;
}

.type-desc {
  font-size: 0.8rem;
  color: var(--gray-text);
  margin-bottom: 12px;
  line-height: 1.4;
}

.type-cost {
  font-family: var(--font-mono);
  font-size: 0.9rem;
  font-weight: 700;
  color: var(--orange);
}

.type-eta {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: #999;
  margin-top: 4px;
}

.insufficient-text {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  color: #CC0000;
  text-align: center;
  margin: 0;
}

/* Responsive */
@media (max-width: 1024px) {
  .dual-panel { grid-template-columns: 1fr; }
  .panel-left { position: static; height: 400px; min-height: 400px; }
}

@media (max-width: 768px) {
  .game-grid { grid-template-columns: 1fr; }
  .betting-cards { grid-template-columns: 1fr; }
  .date-picker-row { flex-direction: column; }
  .type-options { grid-template-columns: 1fr; }
}
</style>
