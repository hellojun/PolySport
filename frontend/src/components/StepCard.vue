<template>
  <div class="step-card" :class="{ active: step.status === 'running', completed: step.status === 'completed' }">
    <div class="step-header">
      <div class="step-number">{{ String(step.step).padStart(2, '0') }}</div>
      <h4 class="step-title">{{ step.title }}</h4>
      <span class="step-badge" :class="step.status">
        {{ badgeText }}
      </span>
    </div>

    <p class="step-desc">{{ step.desc }}</p>

    <!-- Step 1: 创建知识图谱 -->
    <div v-if="step.step === 1 && d" class="step-details">
      <div class="detail-row">
        <span class="detail-label">GRAPH ID</span>
        <span class="detail-value mono">{{ d.graph_id }}</span>
      </div>
      <div class="detail-row">
        <span class="detail-label">MATCHUP ID</span>
        <span class="detail-value mono">{{ d.matchup_id }}</span>
      </div>
      <div v-if="d.entity_types" class="detail-tags">
        <span class="tag-label">ENTITY TYPES</span>
        <div class="tags">
          <span v-for="tp in d.entity_types" :key="tp" class="tag">{{ tp }}</span>
        </div>
      </div>
      <div v-if="d.relation_types" class="detail-tags">
        <span class="tag-label">RELATION TYPES</span>
        <div class="tags">
          <span v-for="tp in d.relation_types" :key="tp" class="tag edge-tag">{{ tp }}</span>
        </div>
      </div>
    </div>

    <!-- Step 2: NBA 数据 -->
    <div v-if="step.step === 2 && d && !d.warning && !d.info" class="step-details">
      <div class="stats-grid">
        <div v-for="(side, label) in {home: homeAbbr, away: awayAbbr}" :key="side" class="team-stats-card">
          <div class="stats-team-name">{{ label }}</div>
          <div v-if="d[side + '_record']" class="stats-row">
            <span class="stats-label">{{ t('step.record') }}</span>
            <span class="stats-value">{{ d[side + '_record'] }} ({{ (d[side + '_win_pct'] * 100).toFixed(1) }}%)</span>
          </div>
          <div v-if="d[side + '_conf_rank']" class="stats-row">
            <span class="stats-label">{{ t('step.conf_rank') }}</span>
            <span class="stats-value">#{{ d[side + '_conf_rank'] }}</span>
          </div>
          <div v-if="d[side + '_net_rtg'] != null" class="stats-row">
            <span class="stats-label">Net Rating</span>
            <span class="stats-value" :class="{ positive: d[side + '_net_rtg'] > 0, negative: d[side + '_net_rtg'] < 0 }">
              {{ d[side + '_net_rtg'] > 0 ? '+' : '' }}{{ d[side + '_net_rtg'] }}
            </span>
          </div>
          <div v-if="d[side + '_top_players']" class="players-list">
            <div v-for="p in d[side + '_top_players']" :key="p.name" class="player-row">
              {{ p.name }}: {{ p.ppg }} PPG, {{ p.rpg }} RPG, {{ p.apg }} APG
            </div>
          </div>
        </div>
      </div>
      <div v-if="d.warning" class="detail-warning">{{ d.warning }}</div>
    </div>

    <!-- Step 3: 注入图谱 -->
    <div v-if="step.step === 3 && d" class="step-details">
      <div class="stat-numbers">
        <div class="stat-box">
          <div class="stat-num">{{ d.text_chunks || '—' }}</div>
          <div class="stat-label">{{ t('step.text_chunks') }}</div>
        </div>
        <div class="stat-box">
          <div class="stat-num">{{ d.episodes || '—' }}</div>
          <div class="stat-label">{{ t('step.episodes') }}</div>
        </div>
      </div>
    </div>

    <!-- Step 4: 图谱构建完成 -->
    <div v-if="step.step === 4 && d" class="step-details">
      <div class="stat-numbers">
        <div class="stat-box">
          <div class="stat-num">{{ d.node_count || '—' }}</div>
          <div class="stat-label">{{ t('step.entity_nodes') }}</div>
        </div>
        <div class="stat-box">
          <div class="stat-num">{{ d.edge_count || '—' }}</div>
          <div class="stat-label">{{ t('step.relation_edges') }}</div>
        </div>
        <div class="stat-box">
          <div class="stat-num">{{ entityTypeCount }}</div>
          <div class="stat-label">{{ t('step.schema_types') }}</div>
        </div>
      </div>
    </div>

    <!-- Step 5: 辩论分析 -->
    <div v-if="step.step === 5 && d" class="step-details">
      <div v-if="d.total_llm_calls" class="debate-meta">
        {{ t('step.llm_calls') }} {{ d.total_llm_calls }}{{ t('result.calls_unit') }} | {{ t('step.duration') }} {{ d.duration_seconds }}s
      </div>
      <div v-if="d.rounds && d.rounds.length > 0" class="debate-rounds">
        <div v-for="rd in d.rounds" :key="rd.round" class="round-block">
          <div class="round-label">Round {{ rd.round }}</div>
          <div class="analysts-grid">
            <div v-for="p in rd.predictions" :key="p.analyst" class="analyst-chip"
                 :class="{ changed: p.changed }">
              <div class="analyst-id">{{ p.analyst }}</div>
              <div class="analyst-pick">{{ p.ml_pick }} {{ (p.ml_conf * 100).toFixed(0) }}%</div>
            </div>
          </div>
        </div>
      </div>
      <div v-else-if="d.current_round" class="debate-progress-text">
        {{ d.current_round }}
      </div>
    </div>

    <!-- Step 6: 生成预测 -->
    <div v-if="step.step === 6 && step.status === 'completed'" class="step-details">
      <div class="detail-row">
        <span class="detail-value">{{ t('step.prediction_generated') }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = defineProps({
  step: { type: Object, required: true },
  homeAbbr: { type: String, default: '' },
  awayAbbr: { type: String, default: '' },
})

const d = computed(() => props.step.details || null)

const badgeText = computed(() => {
  const map = { completed: t('step.completed'), running: t('step.running'), pending: t('step.pending') }
  return map[props.step.status] || props.step.status
})

const entityTypeCount = computed(() => {
  if (!d.value || !d.value.entity_type_distribution) return '—'
  return Object.keys(d.value.entity_type_distribution).length
})
</script>

<style scoped>
.step-card {
  border: 1px solid #E5E5E5;
  padding: 20px;
  margin-bottom: 12px;
  background: #FFF;
  transition: border-color 0.3s;
}

.step-card.active {
  border-left: 3px solid #FF4500;
}

.step-card.completed {
  border-left: 3px solid #4CAF50;
}

.step-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.step-number {
  font-family: 'JetBrains Mono', monospace;
  font-size: 1.4rem;
  font-weight: 800;
  color: #333;
  min-width: 32px;
}

.step-title {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.95rem;
  font-weight: 700;
  margin: 0;
  flex: 1;
}

.step-badge {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.65rem;
  font-weight: 700;
  padding: 3px 10px;
  border-radius: 3px;
  white-space: nowrap;
}

.step-badge.completed {
  background: #E8F5E9;
  color: #2E7D32;
}

.step-badge.running {
  background: #FFF3E0;
  color: #E65100;
  animation: pulse 1.5s infinite;
}

.step-badge.pending {
  background: #F5F5F5;
  color: #999;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.step-desc {
  font-size: 0.8rem;
  color: #999;
  margin: 0 0 12px 0;
  font-family: 'JetBrains Mono', monospace;
}

.step-details {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #F0F0F0;
}

/* Detail rows */
.detail-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 0;
  border-bottom: 1px dashed #F0F0F0;
}

.detail-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  color: #999;
  text-transform: uppercase;
}

.detail-value {
  font-size: 0.8rem;
  color: #333;
}

.detail-value.mono {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
}

/* Tags */
.detail-tags {
  margin-top: 10px;
}

.tag-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.65rem;
  color: #999;
  text-transform: uppercase;
  display: block;
  margin-bottom: 6px;
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tag {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  padding: 3px 10px;
  border: 1px solid #E5E5E5;
  background: #FAFAFA;
  color: #333;
}

.edge-tag {
  font-size: 0.65rem;
  color: #666;
}

/* Stat numbers */
.stat-numbers {
  display: flex;
  gap: 20px;
}

.stat-box {
  flex: 1;
  text-align: center;
  padding: 12px;
  background: #FAFAFA;
}

.stat-num {
  font-family: 'JetBrains Mono', monospace;
  font-size: 1.6rem;
  font-weight: 800;
  color: #333;
}

.stat-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.65rem;
  color: #999;
  text-transform: uppercase;
  margin-top: 4px;
}

/* Team stats */
.stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.team-stats-card {
  padding: 12px;
  background: #FAFAFA;
  border: 1px solid #F0F0F0;
}

.stats-team-name {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.9rem;
  font-weight: 800;
  margin-bottom: 8px;
  color: #333;
}

.stats-row {
  display: flex;
  justify-content: space-between;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  padding: 3px 0;
}

.stats-label { color: #999; }
.stats-value { color: #333; font-weight: 600; }
.stats-value.positive { color: #2E7D32; }
.stats-value.negative { color: #C62828; }

.players-list {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed #E5E5E5;
}

.player-row {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  color: #666;
  padding: 2px 0;
}

/* Debate */
.debate-meta {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  color: #999;
  margin-bottom: 12px;
}

.debate-rounds {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.round-block {
  padding: 10px;
  background: #FAFAFA;
  border: 1px solid #F0F0F0;
}

.round-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  font-weight: 700;
  color: #333;
  margin-bottom: 8px;
  padding-bottom: 4px;
  border-bottom: 1px solid #E5E5E5;
}

.analysts-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 6px;
}

.analyst-chip {
  padding: 6px 8px;
  background: #FFF;
  border: 1px solid #E5E5E5;
  text-align: center;
}

.analyst-chip.changed {
  border-color: #FF9800;
  background: #FFF8E1;
}

.analyst-id {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.6rem;
  color: #FF4500;
  font-weight: 700;
  margin-bottom: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.analyst-pick {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  font-weight: 600;
  color: #333;
}

.debate-progress-text {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.8rem;
  color: #666;
}

.detail-warning {
  font-size: 0.8rem;
  color: #E65100;
}
</style>
