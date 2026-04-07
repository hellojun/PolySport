<template>
  <div class="track-record">
    <div class="container">
      <div class="page-header">
        <h1 class="page-title">{{ t('track.title') }}</h1>
        <p class="page-desc">{{ t('track.desc') }}</p>
        <p class="page-note">{{ t('track.auto_only_note') }}</p>
      </div>

      <!-- Loading -->
      <div v-if="loading" class="loading-state">
        <span class="loading-spinner"></span>
        {{ t('history.loading') }}
      </div>

      <!-- No data -->
      <div v-else-if="!overview || overview.insufficient" class="empty-state">
        <div class="empty-icon">&#128202;</div>
        <p>{{ t('track.no_data') }}</p>
      </div>

      <template v-else>
        <!-- 1. Overview cards -->
        <section class="overview-section">
          <div class="stats-grid">
            <div class="stat-card stat-card--total">
              <div class="stat-icon">&#128202;</div>
              <span class="stat-num">{{ overview.total_predictions }}</span>
              <span class="stat-label">{{ t('home.total_predictions') }}</span>
            </div>
            <div class="stat-card stat-card--ml">
              <div class="stat-icon">&#127919;</div>
              <span class="stat-num">{{ formatPct(overview.moneyline_hit_rate) }}</span>
              <span class="stat-label">{{ t('home.moneyline_hit') }}</span>
              <div class="stat-bar">
                <div class="stat-bar-fill" :style="{ width: (overview.moneyline_hit_rate * 100) + '%' }"></div>
              </div>
            </div>
            <div class="stat-card stat-card--spread">
              <div class="stat-icon">&#128200;</div>
              <span class="stat-num">{{ formatPct(overview.spread_hit_rate) }}</span>
              <span class="stat-label">{{ t('home.spread_hit') }}</span>
              <div class="stat-bar">
                <div class="stat-bar-fill" :style="{ width: (overview.spread_hit_rate * 100) + '%' }"></div>
              </div>
            </div>
            <div class="stat-card stat-card--total-pts">
              <div class="stat-icon">&#128201;</div>
              <span class="stat-num">{{ formatPct(overview.total_hit_rate) }}</span>
              <span class="stat-label">{{ t('home.total_hit') }}</span>
              <div class="stat-bar">
                <div class="stat-bar-fill" :style="{ width: (overview.total_hit_rate * 100) + '%' }"></div>
              </div>
            </div>
          </div>
        </section>

        <!-- 2. Trend chart -->
        <section class="trend-section">
          <h2 class="section-title">{{ t('track.trend_title') }}</h2>
          <div ref="chartRef" class="trend-chart"></div>
        </section>

        <!-- 3. Records table -->
        <section class="records-section">
          <h2 class="section-title">{{ t('track.records_title') }}</h2>
          <div class="records-table-wrap">
            <table class="records-table">
              <thead>
                <tr>
                  <th>{{ t('track.date') }}</th>
                  <th>{{ t('track.matchup') }}</th>
                  <th>{{ t('track.score') }}</th>
                  <th>ML</th>
                  <th>Spread</th>
                  <th>Total</th>
                  <th>{{ t('track.hits') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(rec, idx) in records" :key="idx">
                  <td class="td-date">{{ rec.game_date }}</td>
                  <td class="td-matchup">{{ rec.away }} @ {{ rec.home }}</td>
                  <td class="td-score">{{ rec.away_score }} - {{ rec.home_score }}</td>
                  <td>
                    <span class="pick-text">{{ pickLabel(rec.picks?.moneyline) }}</span>
                    <span :class="hitClass(rec.hit_status?.moneyline_hit)">
                      {{ hitLabel(rec.hit_status?.moneyline_hit) }}
                    </span>
                  </td>
                  <td>
                    <span class="pick-text">{{ pickLabel(rec.picks?.spread) }}</span>
                    <span :class="hitClass(rec.hit_status?.spread_hit)">
                      {{ hitLabel(rec.hit_status?.spread_hit) }}
                    </span>
                  </td>
                  <td>
                    <span class="pick-text">{{ pickLabel(rec.picks?.total) }}</span>
                    <span :class="hitClass(rec.hit_status?.total_hit)">
                      {{ hitLabel(rec.hit_status?.total_hit) }}
                    </span>
                  </td>
                  <td class="td-hits">
                    {{ rec.hit_status?.hit_count ?? 0 }}/{{ rec.hit_status?.total_markets ?? 0 }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import * as d3 from 'd3'
import { getTrackRecord } from '../api/prediction'

const { t, locale } = useI18n()

const loading = ref(true)
const overview = ref(null)
const records = ref([])
const dailySummary = ref([])
const chartRef = ref(null)

function formatPct(val) {
  if (val == null) return '--'
  return (val * 100).toFixed(1) + '%'
}

function pickLabel(pick) {
  if (!pick) return '--'
  return pick.pick || '--'
}

function hitLabel(val) {
  if (val === true) return t('track.hit')
  if (val === false) return t('track.miss')
  if (val === 'push') return t('track.push')
  return '--'
}

function hitClass(val) {
  if (val === true) return 'hit-badge hit-badge--hit'
  if (val === false) return 'hit-badge hit-badge--miss'
  if (val === 'push') return 'hit-badge hit-badge--push'
  return 'hit-badge'
}

function drawChart() {
  if (!chartRef.value || !dailySummary.value.length) return

  // 清除旧图表
  d3.select(chartRef.value).selectAll('*').remove()

  const el = chartRef.value
  const rect = el.getBoundingClientRect()
  if (rect.width < 100) return  // 容器还没布局完

  const data = [...dailySummary.value].reverse()  // 按日期升序

  const margin = { top: 24, right: 48, bottom: 48, left: 56 }
  const width = rect.width - 16 - margin.left - margin.right  // 减去 padding
  const height = 260 - margin.top - margin.bottom

  const svg = d3.select(el)
    .append('svg')
    .attr('width', width + margin.left + margin.right)
    .attr('height', height + margin.top + margin.bottom)
    .append('g')
    .attr('transform', `translate(${margin.left},${margin.top})`)

  // X scale
  const x = d3.scaleBand()
    .domain(data.map(d => d.date))
    .range([0, width])
    .padding(0.3)

  // Y scale (hit_rate 0-1)
  const yRate = d3.scaleLinear()
    .domain([0, 1])
    .range([height, 0])

  // Y scale right (predictions count)
  const maxPred = d3.max(data, d => d.predictions) || 5
  const yCount = d3.scaleLinear()
    .domain([0, maxPred * 1.2])
    .range([height, 0])

  // 坐标轴样式辅助
  function styleAxis(g) {
    g.selectAll('.domain').attr('stroke', '#ccc')
    g.selectAll('.tick line').attr('stroke', '#ddd')
    g.selectAll('.tick text')
      .attr('font-family', 'JetBrains Mono, monospace')
      .attr('font-size', '11px')
      .attr('fill', '#999')
  }

  // X axis
  const xAxisG = svg.append('g')
    .attr('transform', `translate(0,${height})`)
    .call(d3.axisBottom(x).tickFormat(d => d.slice(5)))  // MM-DD
  styleAxis(xAxisG)
  xAxisG.selectAll('.tick text')
    .attr('transform', 'rotate(-45)')
    .attr('text-anchor', 'end')

  // Y axis left
  const yAxisG = svg.append('g')
    .call(d3.axisLeft(yRate).ticks(5).tickFormat(d3.format('.0%')))
  styleAxis(yAxisG)

  // Y axis right
  const yAxisRG = svg.append('g')
    .attr('transform', `translate(${width},0)`)
    .call(d3.axisRight(yCount).ticks(4).tickFormat(d3.format('d')))
  styleAxis(yAxisRG)

  // 50% baseline
  svg.append('line')
    .attr('x1', 0).attr('x2', width)
    .attr('y1', yRate(0.5)).attr('y2', yRate(0.5))
    .attr('stroke', '#ddd')
    .attr('stroke-dasharray', '4 4')

  svg.append('text')
    .attr('x', width - 4)
    .attr('y', yRate(0.5) - 6)
    .attr('text-anchor', 'end')
    .attr('font-family', 'JetBrains Mono, monospace')
    .attr('font-size', '10px')
    .attr('fill', '#bbb')
    .text('50%')

  // Bars (predictions count)
  svg.selectAll('.bar')
    .data(data)
    .join('rect')
    .attr('x', d => x(d.date))
    .attr('y', d => yCount(d.predictions))
    .attr('width', x.bandwidth())
    .attr('height', d => height - yCount(d.predictions))
    .attr('fill', 'rgba(0, 0, 0, 0.12)')
    .attr('rx', 2)

  // Line (hit_rate)
  const line = d3.line()
    .x(d => x(d.date) + x.bandwidth() / 2)
    .y(d => yRate(d.hit_rate))
    .curve(d3.curveMonotoneX)

  svg.append('path')
    .datum(data)
    .attr('fill', 'none')
    .attr('stroke', '#FF4500')
    .attr('stroke-width', 2.5)
    .attr('d', line)

  // Dots
  svg.selectAll('.dot')
    .data(data)
    .join('circle')
    .attr('cx', d => x(d.date) + x.bandwidth() / 2)
    .attr('cy', d => yRate(d.hit_rate))
    .attr('r', 4)
    .attr('fill', '#FF4500')
    .attr('stroke', '#fff')
    .attr('stroke-width', 1.5)

  // Dot labels (hit rate %)
  svg.selectAll('.dot-label')
    .data(data)
    .join('text')
    .attr('x', d => x(d.date) + x.bandwidth() / 2)
    .attr('y', d => yRate(d.hit_rate) - 10)
    .attr('text-anchor', 'middle')
    .attr('font-family', 'JetBrains Mono, monospace')
    .attr('font-size', '10px')
    .attr('font-weight', '700')
    .attr('fill', '#FF4500')
    .text(d => (d.hit_rate * 100).toFixed(0) + '%')
}

async function fetchData() {
  loading.value = true
  try {
    const res = await getTrackRecord()
    // axios 拦截器已解包 response.data，res 直接是 { success, overview, ... }
    const data = res.data || res
    if (data && data.success) {
      overview.value = data.overview
      records.value = data.recent_records || []
      dailySummary.value = data.daily_summary || []
      // 等待 DOM 渲染 + 布局完成后再绘制图表
      await nextTick()
      requestAnimationFrame(() => drawChart())
    }
  } catch {
    // keep empty
  } finally {
    loading.value = false
  }
}

// Redraw chart on locale change
watch(locale, () => {
  nextTick(() => drawChart())
})

onMounted(fetchData)
</script>

<style scoped>
.track-record {
  min-height: calc(100vh - 60px);
  background: var(--white);
  padding-bottom: 64px;
}

.container {
  max-width: 1080px;
  margin: 0 auto;
  padding: 0 24px;
}

.page-header {
  padding: 48px 0 32px;
}

.page-title {
  font-family: var(--font-mono);
  font-size: 1.2rem;
  font-weight: 900;
  letter-spacing: 2px;
  text-transform: uppercase;
  margin: 0 0 8px;
}

.page-desc {
  font-family: var(--font-sans);
  font-size: 0.85rem;
  color: var(--gray-text);
  margin: 0;
}

.page-note {
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: var(--orange);
  letter-spacing: 1px;
  text-transform: uppercase;
  margin: 6px 0 0;
}

/* Loading / Empty */
.loading-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 80px 0;
  font-family: var(--font-mono);
  font-size: 0.85rem;
  color: var(--gray-text);
}

.loading-spinner {
  width: 20px;
  height: 20px;
  border: 2px solid var(--border);
  border-top-color: var(--orange);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.empty-icon {
  font-size: 2rem;
  opacity: 0.5;
}

/* Overview */
.overview-section {
  margin-bottom: 48px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.stat-card {
  text-align: center;
  padding: 32px 20px 28px;
  background: var(--gray-light);
  border: 1px solid var(--border);
  position: relative;
  overflow: hidden;
}

.stat-icon {
  font-size: 1.2rem;
  margin-bottom: 12px;
  opacity: 0.7;
}

.stat-num {
  display: block;
  font-family: var(--font-mono);
  font-size: 2.2rem;
  font-weight: 900;
  letter-spacing: 1px;
  margin-bottom: 8px;
  color: var(--black);
}

.stat-card--ml .stat-num,
.stat-card--spread .stat-num,
.stat-card--total-pts .stat-num {
  color: var(--orange);
}

.stat-label {
  font-family: var(--font-mono);
  font-size: 0.65rem;
  color: var(--gray-text);
  letter-spacing: 1.5px;
  text-transform: uppercase;
}

.stat-bar {
  margin-top: 16px;
  height: 4px;
  background: var(--border);
  width: 100%;
}

.stat-bar-fill {
  height: 100%;
  background: var(--orange);
  transition: width 1s ease-out;
}

/* Trend */
.trend-section {
  margin-bottom: 48px;
}

.section-title {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  font-weight: 700;
  letter-spacing: 3px;
  text-transform: uppercase;
  color: var(--gray-text);
  margin: 0 0 20px;
}

.trend-chart {
  width: 100%;
  min-height: 260px;
  border: 1px solid var(--border);
  background: var(--gray-light);
  padding: 8px;
}

/* Records table */
.records-section {
  margin-bottom: 48px;
}

.records-table-wrap {
  overflow-x: auto;
  border: 1px solid var(--border);
}

.records-table {
  width: 100%;
  border-collapse: collapse;
  font-family: var(--font-mono);
  font-size: 0.75rem;
}

.records-table th {
  background: var(--black);
  color: var(--white);
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
  padding: 10px 12px;
  text-align: left;
  font-size: 0.65rem;
  white-space: nowrap;
}

.records-table td {
  padding: 10px 12px;
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}

.records-table tbody tr:hover {
  background: var(--gray-light);
}

.td-date {
  color: var(--gray-text);
  font-size: 0.7rem;
}

.td-matchup {
  font-weight: 700;
}

.td-score {
  font-weight: 700;
  color: var(--orange);
}

.td-hits {
  font-weight: 700;
}

.pick-text {
  display: inline-block;
  font-size: 0.65rem;
  color: var(--gray-text);
  margin-right: 6px;
}

.hit-badge {
  display: inline-block;
  font-size: 0.6rem;
  font-weight: 700;
  letter-spacing: 0.5px;
  padding: 2px 6px;
}

.hit-badge--hit {
  color: #16a34a;
  background: rgba(22, 163, 74, 0.08);
}

.hit-badge--miss {
  color: #dc2626;
  background: rgba(220, 38, 38, 0.08);
}

.hit-badge--push {
  color: #ca8a04;
  background: rgba(202, 138, 4, 0.08);
}

/* Responsive */
@media (max-width: 768px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .page-header {
    padding: 32px 0 24px;
  }
}
</style>
