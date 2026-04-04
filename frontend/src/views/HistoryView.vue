<template>
  <div class="history-container">
    <div class="main-content">
      <div class="section-header">
        <h1 class="page-title">{{ t('history.title') }}</h1>
        <p class="page-desc">{{ t('history.desc') }}</p>
      </div>

      <div v-if="loading" class="loading-text">{{ t('history.loading') }}</div>

      <div v-else-if="predictions.length === 0" class="empty-state">
        <p>{{ t('history.no_records') }}</p>
        <router-link to="/predict" class="back-btn">{{ t('history.go_predict') }}</router-link>
      </div>

      <div v-else class="history-list">
        <div
          v-for="item in predictions"
          :key="item.task_id"
          class="history-card"
          :class="{ clickable: item.status === 'completed', failed: item.status === 'failed' }"
          @click="viewResult(item)"
        >
          <div class="card-left">
            <div class="matchup">
              <span class="team-abbr">{{ item.away }}</span>
              <span class="team-name">{{ t(`team.${item.away}`, '') }}</span>
              <span class="at-symbol">@</span>
              <span class="team-abbr">{{ item.home }}</span>
              <span class="team-name">{{ t(`team.${item.home}`, '') }}</span>
              <span v-if="item.game_time || item.game_date" class="game-time-badge">
                {{ formatGameTime(item.game_time, item.game_date) }}
              </span>
            </div>
            <div class="card-meta">
              <span class="meta-time">{{ formatTime(item.created_at) }}</span>
            </div>
          </div>

          <div class="card-right">
            <!-- 比赛结果：比分 + 命中 badge -->
            <div v-if="item.game_result" class="game-result-info">
              <span class="score-text">
                {{ item.away }} {{ item.game_result.away_score }} - {{ item.game_result.home_score }} {{ item.home }}
              </span>
              <span
                class="hit-badge"
                :class="hitBadgeClass(item.game_result.hit_status)"
              >
                {{ item.game_result.hit_status.hit_count }}/{{ item.game_result.hit_status.total_markets }}
              </span>
            </div>
            <!-- 获取结果按钮 -->
            <button
              v-else-if="item.status === 'completed'"
              class="fetch-result-btn"
              :disabled="item._fetching || !canFetchResult(item)"
              @click.stop="handleFetchResult(item)"
            >
              {{ item._fetching ? t('history.fetching_result') : t('history.fetch_result_btn') }}
            </button>

            <div v-if="item.status === 'completed' && !item.game_result && item.duration_seconds != null" class="card-stats">
              <span class="stat">{{ item.duration_seconds.toFixed(1) }}s</span>
            </div>
            <div v-if="item.status === 'failed'" class="error-info">
              {{ item.error || t('history.prediction_failed') }}
            </div>
            <div class="status-badge" :class="item.status">
              {{ item.status === 'completed' ? 'COMPLETED' : 'FAILED' }}
            </div>
            <button
              class="delete-btn"
              :title="t('history.delete')"
              @click.stop="confirmDelete(item)"
            >&times;</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { getPredictionHistory, deletePrediction, fetchGameResult } from '../api/prediction'

const router = useRouter()
const { t, locale } = useI18n()
const loading = ref(true)
const predictions = ref([])

onMounted(async () => {
  try {
    const res = await getPredictionHistory()
    predictions.value = res.predictions || []
  } catch {
    // silently fail
  } finally {
    loading.value = false
  }
})

function viewResult(item) {
  if (item.status !== 'completed') return
  router.push({
    path: '/predict',
    query: { matchup_id: item.matchup_id, home: item.home, away: item.away, game_date: item.game_date, game_time: item.game_time || '' },
  })
}

async function confirmDelete(item) {
  if (!confirm(t('history.confirm_delete'))) return
  try {
    await deletePrediction(item.task_id)
    predictions.value = predictions.value.filter(p => p.task_id !== item.task_id)
  } catch {
    // silently fail
  }
}

function canFetchResult(item) {
  // 粗判: game_date + 28h > now → 比赛可能还没结束
  if (!item.game_date) return false
  const gameEnd = new Date(item.game_date + 'T00:00:00')
  gameEnd.setHours(gameEnd.getHours() + 28)
  return new Date() > gameEnd
}

async function handleFetchResult(item) {
  if (!item.matchup_id) return
  item._fetching = true
  try {
    const res = await fetchGameResult(item.matchup_id, {
      home: item.home,
      away: item.away,
      game_date: item.game_date,
    })
    item.game_result = res.game_result
  } catch (err) {
    const errData = err?.response?.data || err
    if (errData?.error === 'game_not_ended') {
      alert(t('history.game_not_ended'))
    } else {
      alert(t('history.fetch_result_failed'))
    }
  } finally {
    item._fetching = false
  }
}

function hitBadgeClass(hitStatus) {
  if (!hitStatus) return ''
  const { hit_count, total_markets } = hitStatus
  if (hit_count === total_markets) return 'hit-all'
  if (hit_count === 0) return 'hit-none'
  return 'hit-partial'
}

function formatTime(isoStr) {
  if (!isoStr) return ''
  const d = new Date(isoStr)
  return d.toLocaleString()
}

function formatGameTime(gameTime, gameDate) {
  if (gameTime) {
    const d = new Date(gameTime)
    if (!isNaN(d.getTime())) {
      const et = d.toLocaleString('en-US', {
        timeZone: 'America/New_York',
        year: 'numeric', month: 'numeric', day: 'numeric',
        hour: 'numeric', minute: '2-digit',
        hour12: true,
      })
      const bj = d.toLocaleString('zh-CN', {
        timeZone: 'Asia/Shanghai',
        year: 'numeric', month: 'numeric', day: 'numeric',
        hour: 'numeric', minute: '2-digit',
        hour12: false,
      })
      if (locale.value === 'zh') {
        return `${et} ET (${bj} ${t('history.beijing')})`
      }
      return `${et} ET`
    }
  }
  if (gameDate) {
    return gameDate
  }
  return ''
}
</script>

<style scoped>
.history-container {
  min-height: 100vh;
  background: var(--white, #FFFFFF);
  font-family: 'Space Grotesk', 'Noto Sans SC', system-ui, sans-serif;
  color: var(--black, #000000);
}

.main-content {
  max-width: 960px;
  margin: 0 auto;
  padding: 40px 20px;
}

.section-header { margin-bottom: 40px; }

.page-title {
  font-size: 2.5rem;
  font-weight: 600;
  margin: 0 0 10px 0;
}

.page-desc {
  color: #666666;
  font-size: 1rem;
}

.loading-text {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.85rem;
  color: #999;
  text-align: center;
  padding: 60px 0;
}

.empty-state {
  text-align: center;
  padding: 60px 0;
  color: #666666;
  font-size: 1.1rem;
}

.back-btn {
  display: inline-block;
  margin-top: 20px;
  background: none;
  border: 1px solid #E5E5E5;
  padding: 8px 16px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.8rem;
  cursor: pointer;
  color: #666;
  text-decoration: none;
  transition: all 0.2s;
}

.back-btn:hover { border-color: #000; color: #000; }

/* History list */
.history-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.history-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border: 1px solid #E5E5E5;
  padding: 20px 24px;
  transition: all 0.2s;
}

.history-card.clickable {
  cursor: pointer;
}

.history-card.clickable:hover {
  border-color: #000;
  box-shadow: 0 2px 12px rgba(0,0,0,0.08);
}

.history-card.failed {
  opacity: 0.7;
  cursor: default;
}

.card-left {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.matchup {
  display: flex;
  align-items: center;
  gap: 12px;
}

.team-abbr {
  font-family: 'JetBrains Mono', monospace;
  font-size: 1.3rem;
  font-weight: 800;
  letter-spacing: 1px;
}

.team-name {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  color: #888;
  font-weight: 400;
}

.at-symbol {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.9rem;
  color: #999;
}

.game-time-badge {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  color: #666;
  background: #F5F5F5;
  padding: 2px 8px;
  border: 1px solid #E5E5E5;
  white-space: nowrap;
}

.card-meta {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  color: #999;
}

.card-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.card-stats {
  display: flex;
  gap: 12px;
}

.stat {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.8rem;
  color: #666;
}

.error-info {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  color: #CC0000;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-badge {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 1px;
  padding: 4px 10px;
}

.status-badge.completed {
  background: #F0FFF0;
  color: #00AA00;
  border: 1px solid #00AA00;
}

.status-badge.failed {
  background: #FFF0F0;
  color: #CC0000;
  border: 1px solid #CC0000;
}

.delete-btn {
  background: none;
  border: 1px solid transparent;
  color: #CCC;
  font-size: 1.2rem;
  line-height: 1;
  padding: 4px 8px;
  cursor: pointer;
  transition: all 0.2s;
  font-family: 'JetBrains Mono', monospace;
}

.delete-btn:hover {
  color: #CC0000;
  border-color: #CC0000;
}

/* Game result info */
.game-result-info {
  display: flex;
  align-items: center;
  gap: 10px;
}

.score-text {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.85rem;
  font-weight: 700;
  color: #333;
}

.hit-badge {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  font-weight: 700;
  padding: 2px 8px;
  letter-spacing: 0.5px;
}

.hit-badge.hit-all {
  background: #F0FFF0;
  color: #00AA00;
  border: 1px solid #00AA00;
}

.hit-badge.hit-partial {
  background: #FFFBF0;
  color: #CC8800;
  border: 1px solid #CC8800;
}

.hit-badge.hit-none {
  background: #FFF0F0;
  color: #CC0000;
  border: 1px solid #CC0000;
}

.fetch-result-btn {
  background: none;
  border: 1px solid #E5E5E5;
  color: #666;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  font-weight: 600;
  padding: 4px 12px;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.fetch-result-btn:not(:disabled):hover {
  border-color: #FF4500;
  color: #FF4500;
}

.fetch-result-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

@media (max-width: 768px) {
  .main-content { padding: 24px 16px; }
  .page-title { font-size: 1.8rem; }

  .history-card {
    flex-direction: column;
    align-items: stretch;
    gap: 12px;
    padding: 16px;
  }

  .matchup {
    flex-wrap: wrap;
    gap: 8px;
  }

  .game-time-badge {
    width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    font-size: 0.6rem;
  }

  .card-right {
    flex-wrap: wrap;
    gap: 10px;
    justify-content: flex-end;
  }

  .card-stats { gap: 8px; }

  .error-info { max-width: 100%; }
}
</style>
