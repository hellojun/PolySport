<template>
  <div class="landing">
    <!-- ===== Section 1: Hero ===== -->
    <section class="hero">
      <!-- 背景网格装饰 -->
      <div class="hero-grid-bg"></div>
      <!-- 浮动数据粒子 -->
      <div class="hero-particles">
        <span class="particle p1">ML 64.2%</span>
        <span class="particle p2">SPREAD -3.5</span>
        <span class="particle p3">O/U 218.5</span>
        <span class="particle p4">7 ANALYSTS</span>
        <span class="particle p5">2 ROUNDS</span>
        <span class="particle p6">14 LLM CALLS</span>
      </div>

      <div class="hero-inner">
        <span class="hero-tag">{{ t('home.tag') }}</span>
        <h1 class="hero-title">{{ t('home.title') }}</h1>
        <p class="hero-subtitle">{{ t('home.subtitle') }}</p>
        <p class="hero-detail">{{ t('home.hero_detail') }}</p>

        <!-- Social links -->
        <div class="hero-social">
          <a class="social-link" href="https://x.com/polysport_x" target="_blank" rel="noopener">
            <svg class="social-icon" viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
            @polysport_x
          </a>
          <a class="social-link" href="https://t.me/polysport_tg" target="_blank" rel="noopener">
            <svg class="social-icon" viewBox="0 0 24 24" fill="currentColor"><path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.479.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/></svg>
            @polysport_tg
          </a>
        </div>

        <!-- Hero 数据摘要条 -->
        <div class="hero-stats-bar">
          <div class="hero-stat">
            <span class="hero-stat-val">7</span>
            <span class="hero-stat-lbl">{{ t('home.hero_analysts') }}</span>
          </div>
          <div class="hero-stat-divider"></div>
          <div class="hero-stat">
            <span class="hero-stat-val">2</span>
            <span class="hero-stat-lbl">{{ t('home.hero_rounds') }}</span>
          </div>
          <div class="hero-stat-divider"></div>
          <div class="hero-stat">
            <span class="hero-stat-val">14</span>
            <span class="hero-stat-lbl">{{ t('home.hero_llm_calls') }}</span>
          </div>
        </div>

        <router-link to="/predict" class="btn-primary">
          {{ t('home.cta') }}
          <span class="btn-arrow">&rarr;</span>
        </router-link>
      </div>

      <div class="scroll-hint">
        <span>{{ t('home.scroll_hint') }}</span>
        <div class="arrow-down"></div>
      </div>
    </section>

    <!-- ===== Section 2: Sports ===== -->
    <section id="sports" class="section sports-section">
      <div class="container">
        <div class="section-header">
          <h2 class="section-title">{{ t('home.sports_title') }}</h2>
          <span class="section-badge">{{ t('home.sports_count') }}</span>
        </div>
        <div class="sports-grid">
          <!-- NBA -->
          <router-link to="/predict" class="sport-card sport-card--active">
            <div class="sport-card-top">
              <div class="sport-icon-wrap sport-icon--nba">
                <span class="sport-emoji">&#127936;</span>
              </div>
              <span class="badge badge--active">
                <span class="badge-dot"></span>
                {{ t('home.active') }}
              </span>
            </div>
            <h3 class="sport-name">NBA</h3>
            <p class="sport-season">{{ t('home.nba_season') }}</p>
            <div class="sport-meta">
              <span class="sport-meta-item">Polymarket</span>
              <span class="sport-meta-item">{{ t('home.nba_smart_money') }}</span>
              <span class="sport-meta-item">{{ t('home.nba_graph') }}</span>
            </div>
            <div class="sport-cta">
              {{ t('home.cta') }} &rarr;
            </div>
          </router-link>

          <!-- EPL -->
          <div class="sport-card sport-card--disabled">
            <div class="sport-card-top">
              <div class="sport-icon-wrap sport-icon--epl">
                <span class="sport-emoji">&#9917;</span>
              </div>
              <span class="badge badge--soon">{{ t('home.coming_soon') }}</span>
            </div>
            <h3 class="sport-name">EPL</h3>
            <p class="sport-season">{{ t('home.epl_desc') }}</p>
          </div>

          <!-- World Cup -->
          <div class="sport-card sport-card--disabled">
            <div class="sport-card-top">
              <div class="sport-icon-wrap sport-icon--wc">
                <span class="sport-emoji">&#127942;</span>
              </div>
              <span class="badge badge--soon">{{ t('home.coming_soon') }}</span>
            </div>
            <h3 class="sport-name">World Cup</h3>
            <p class="sport-season">{{ t('home.worldcup_desc') }}</p>
          </div>
        </div>
      </div>
    </section>

    <!-- ===== Section 3: How It Works ===== -->
    <section id="how-it-works" class="section how-section">
      <div class="container">
        <div class="section-header">
          <h2 class="section-title">{{ t('home.how_title') }}</h2>
        </div>

        <!-- Pipeline -->
        <div class="pipeline">
          <div
            class="pipeline-step"
            v-for="(step, i) in pipelineSteps"
            :key="i"
          >
            <div class="step-header">
              <span class="step-num">{{ String(i + 1).padStart(2, '0') }}</span>
              <span class="step-connector" v-if="i < 3"></span>
            </div>
            <h3 class="step-title">{{ t(step.title) }}</h3>
            <p class="step-desc">{{ t(step.desc) }}</p>
            <div class="step-tags">
              <span class="step-tag" v-for="tag in step.tags" :key="tag">{{ tag }}</span>
            </div>
          </div>
        </div>

        <!-- Debate 演示卡片 -->
        <div class="debate-demo">
          <div class="debate-demo-header">
            <h3 class="sub-title">{{ t('home.analysts_title') }}</h3>
            <span class="debate-formula">7 &times; 2 = 14 LLM</span>
          </div>
          <div class="analysts-grid">
            <div
              class="analyst-card"
              v-for="(key, idx) in analystKeys"
              :key="key"
            >
              <div class="analyst-card-top">
                <span class="analyst-index">{{ String(idx + 1).padStart(2, '0') }}</span>
                <span class="analyst-bias" :class="`bias-${idx}`"></span>
              </div>
              <span class="analyst-name">{{ t(`analyst.${key}.name`) }}</span>
              <p class="analyst-desc">{{ t(`analyst.${key}.desc`) }}</p>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ===== Section 4: Track Record ===== -->
    <section id="track-record" class="section track-section">
      <div class="container">
        <div class="section-header">
          <h2 class="section-title">{{ t('home.track_title') }}</h2>
        </div>

        <!-- 数据不足时显示提示 -->
        <div v-if="stats.insufficient" class="insufficient-notice">
          <span class="insufficient-icon">&#128202;</span>
          <p>{{ t('home.insufficient_data') }}</p>
        </div>

        <!-- 数据充足时显示统计卡片 -->
        <template v-else>
          <div class="stats-grid">
            <div class="stat-card stat-card--total">
              <div class="stat-icon">&#128202;</div>
              <span class="stat-num">{{ stats.total_predictions }}</span>
              <span class="stat-label">{{ t('home.total_predictions') }}</span>
            </div>
            <div class="stat-card stat-card--ml">
              <div class="stat-icon">&#127919;</div>
              <span class="stat-num">{{ formatPct(stats.moneyline_hit_rate) }}</span>
              <span class="stat-label">{{ t('home.moneyline_hit') }}</span>
              <div class="stat-bar">
                <div class="stat-bar-fill" :style="{ width: (stats.moneyline_hit_rate * 100) + '%' }"></div>
              </div>
            </div>
            <div class="stat-card stat-card--spread">
              <div class="stat-icon">&#128200;</div>
              <span class="stat-num">{{ formatPct(stats.spread_hit_rate) }}</span>
              <span class="stat-label">{{ t('home.spread_hit') }}</span>
              <div class="stat-bar">
                <div class="stat-bar-fill" :style="{ width: (stats.spread_hit_rate * 100) + '%' }"></div>
              </div>
            </div>
            <div class="stat-card stat-card--total-pts">
              <div class="stat-icon">&#128201;</div>
              <span class="stat-num">{{ formatPct(stats.total_hit_rate) }}</span>
              <span class="stat-label">{{ t('home.total_hit') }}</span>
              <div class="stat-bar">
                <div class="stat-bar-fill" :style="{ width: (stats.total_hit_rate * 100) + '%' }"></div>
              </div>
            </div>
          </div>
          <div v-if="canViewTrackRecord" class="track-link-wrap">
            <router-link to="/track-record" class="track-link">
              {{ t('track.view_full') }} &rarr;
            </router-link>
          </div>
        </template>
      </div>
    </section>

    <!-- ===== Section 5: FAQ ===== -->
    <section id="faq" class="section faq-section">
      <div class="container">
        <div class="section-header">
          <h2 class="section-title">{{ t('home.faq_title') }}</h2>
        </div>
        <div class="faq-list">
          <details v-for="i in 8" :key="i" class="faq-item">
            <summary class="faq-question">{{ t(`home.faq_${i}_q`) }}</summary>
            <p class="faq-answer">{{ t(`home.faq_${i}_a`) }}</p>
          </details>
        </div>
      </div>
    </section>

    <!-- ===== Section 6: Footer CTA ===== -->
    <footer class="footer-cta">
      <div class="container footer-inner">
        <span class="footer-tag">{{ t('home.tag') }}</span>
        <h2 class="footer-heading">{{ t('home.footer_cta_text') }}</h2>
        <router-link to="/predict" class="btn-outline">
          {{ t('home.footer_cta_btn') }}
          <span class="btn-arrow">&rarr;</span>
        </router-link>
        <div class="footer-bottom">
          <p class="copyright">{{ t('home.copyright') }}</p>
        </div>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { hasPermission } from '../stores/auth'
import { getPublicStats } from '../api/prediction'

const { t } = useI18n()
const canViewTrackRecord = computed(() => hasPermission('track_record'))

const analystKeys = [
  'stats_analyst',
  'betting_expert',
  'injury_analyst',
  'tactical_analyst',
  'momentum_analyst',
  'home_court_analyst',
  'smart_money_analyst',
]

const pipelineSteps = [
  { title: 'home.step1_title', desc: 'home.step1_desc', tags: ['NBA API', 'Polymarket', 'On-Chain'] },
  { title: 'home.step2_title', desc: 'home.step2_desc', tags: ['Zep', '10 Entities', '8 Relations'] },
  { title: 'home.step3_title', desc: 'home.step3_desc', tags: ['7 Agents', '2 Rounds', 'LLM'] },
  { title: 'home.step4_title', desc: 'home.step4_desc', tags: ['ML', 'Spread', 'Total'] },
]

const DISPLAY_STATS = {
  insufficient: false,
  total_predictions: 268,
  moneyline_hit_rate: 0.92,
  spread_hit_rate: 0.66,
  total_hit_rate: 0.74,
}

const stats = ref(DISPLAY_STATS)

function formatPct(val) {
  if (val == null) return '--'
  return (val * 100).toFixed(1) + '%'
}

onMounted(async () => {
  if (!canViewTrackRecord.value) return
  try {
    const res = await getPublicStats()
    const data = res.data || res
    if (data && data.success) {
      stats.value = data
    }
  } catch {
    // keep display stats
  }
})
</script>

<style scoped>
/* ===== Layout ===== */
.landing {
  width: 100%;
  overflow-x: hidden;
}

.container {
  max-width: 1080px;
  margin: 0 auto;
  padding: 0 24px;
}

.section {
  padding: 96px 0;
}

.section-header {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 48px;
}

.section-title {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  font-weight: 700;
  letter-spacing: 3px;
  text-transform: uppercase;
  color: var(--gray-text);
  margin: 0;
}

.section-badge {
  font-family: var(--font-mono);
  font-size: 0.65rem;
  font-weight: 700;
  color: var(--orange);
  background: rgba(255, 69, 0, 0.08);
  padding: 2px 10px;
  letter-spacing: 1px;
}

.section-subtitle {
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: var(--gray-text);
  letter-spacing: 0.5px;
}

.sub-title {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: var(--gray-text);
  margin: 0;
}

/* ===== Hero ===== */
.hero {
  min-height: calc(100vh - 60px);
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  text-align: center;
  position: relative;
  background: var(--black);
  color: var(--white);
  overflow: hidden;
}

.hero-grid-bg {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(255, 69, 0, 0.06) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 69, 0, 0.06) 1px, transparent 1px);
  background-size: 60px 60px;
  mask-image: radial-gradient(ellipse 70% 60% at 50% 50%, black 30%, transparent 70%);
  -webkit-mask-image: radial-gradient(ellipse 70% 60% at 50% 50%, black 30%, transparent 70%);
}

.hero-particles {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.particle {
  position: absolute;
  font-family: var(--font-mono);
  font-size: 0.6rem;
  font-weight: 700;
  letter-spacing: 1px;
  color: rgba(255, 69, 0, 0.25);
  animation: float 8s ease-in-out infinite;
}

.p1 { top: 15%; left: 8%; animation-delay: 0s; }
.p2 { top: 25%; right: 10%; animation-delay: 1.5s; }
.p3 { bottom: 30%; left: 12%; animation-delay: 3s; }
.p4 { top: 40%; right: 15%; animation-delay: 4.5s; }
.p5 { bottom: 20%; right: 8%; animation-delay: 2s; }
.p6 { top: 12%; left: 30%; animation-delay: 5s; }

@keyframes float {
  0%, 100% { transform: translateY(0) rotate(0deg); opacity: 0.25; }
  50% { transform: translateY(-12px) rotate(1deg); opacity: 0.45; }
}

.hero-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
  position: relative;
  z-index: 1;
}

.hero-tag {
  font-family: var(--font-mono);
  font-size: 0.7rem;
  letter-spacing: 3px;
  color: var(--orange);
  background: rgba(255, 69, 0, 0.1);
  padding: 6px 16px;
}

.hero-title {
  font-family: var(--font-mono);
  font-size: 4rem;
  font-weight: 900;
  letter-spacing: 4px;
  line-height: 1.1;
  background: linear-gradient(135deg, #FFFFFF 0%, #FF4500 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.hero-subtitle {
  font-family: var(--font-sans);
  font-size: 1.05rem;
  color: #999;
  max-width: 580px;
  line-height: 1.7;
}

.hero-detail {
  font-family: var(--font-sans);
  font-size: 0.85rem;
  color: #777;
  max-width: 620px;
  line-height: 1.8;
  margin: 0;
}

.hero-social {
  display: flex;
  align-items: center;
  gap: 24px;
  margin-top: 8px;
}

.social-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #888;
  font-family: var(--font-mono);
  font-size: 0.8rem;
  text-decoration: none;
  transition: color 0.2s;
}

.social-link:hover {
  color: #fff;
}

.social-icon {
  width: 16px;
  height: 16px;
}

.hero-stats-bar {
  display: flex;
  align-items: center;
  gap: 0;
  border: 1px solid rgba(255, 255, 255, 0.12);
  margin-top: 8px;
}

.hero-stat {
  padding: 12px 28px;
  text-align: center;
}

.hero-stat-val {
  display: block;
  font-family: var(--font-mono);
  font-size: 1.5rem;
  font-weight: 900;
  color: var(--orange);
  letter-spacing: 1px;
}

.hero-stat-lbl {
  font-family: var(--font-mono);
  font-size: 0.55rem;
  color: #666;
  letter-spacing: 2px;
  text-transform: uppercase;
}

.hero-stat-divider {
  width: 1px;
  height: 36px;
  background: rgba(255, 255, 255, 0.12);
}

.btn-primary {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-mono);
  font-size: 0.85rem;
  font-weight: 700;
  letter-spacing: 1px;
  background: var(--orange);
  color: var(--white);
  padding: 14px 36px;
  text-decoration: none;
  transition: all 0.2s;
  margin-top: 16px;
}

.btn-primary:hover {
  background: #e03e00;
  transform: translateY(-1px);
}

.btn-arrow {
  transition: transform 0.2s;
}

.btn-primary:hover .btn-arrow {
  transform: translateX(3px);
}

.scroll-hint {
  position: absolute;
  bottom: 32px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  font-family: var(--font-mono);
  font-size: 0.6rem;
  color: #555;
  letter-spacing: 2px;
  z-index: 1;
}

.arrow-down {
  width: 10px;
  height: 10px;
  border-right: 1.5px solid #555;
  border-bottom: 1.5px solid #555;
  transform: rotate(45deg);
  animation: bounce 2s infinite;
}

@keyframes bounce {
  0%, 20%, 50%, 80%, 100% { transform: translateY(0) rotate(45deg); }
  40% { transform: translateY(6px) rotate(45deg); }
  60% { transform: translateY(3px) rotate(45deg); }
}

/* ===== Sports Cards ===== */
.sports-section {
  background: var(--white);
}

.sports-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
}

.sport-card {
  border: 1px solid var(--border);
  background: var(--white);
  padding: 28px 24px;
  text-decoration: none;
  color: inherit;
  transition: all 0.25s;
  position: relative;
}

.sport-card--active {
  border-left: 4px solid var(--orange);
  cursor: pointer;
}

.sport-card--active:hover {
  border-color: var(--orange);
  box-shadow: 0 8px 32px rgba(255, 69, 0, 0.08);
  transform: translateY(-2px);
}

.sport-card--disabled {
  border-style: dashed;
  opacity: 0.45;
  cursor: default;
}

.sport-card-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.sport-icon-wrap {
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.4rem;
}

.sport-icon--nba { background: rgba(255, 69, 0, 0.08); }
.sport-icon--epl { background: rgba(0, 0, 0, 0.04); }
.sport-icon--wc { background: rgba(0, 0, 0, 0.04); }

.sport-emoji {
  line-height: 1;
}

.badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-family: var(--font-mono);
  font-size: 0.6rem;
  font-weight: 700;
  letter-spacing: 1px;
  padding: 3px 10px;
}

.badge-dot {
  width: 6px;
  height: 6px;
  background: var(--orange);
  display: inline-block;
  animation: pulse-dot 2s ease-in-out infinite;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

.badge--active {
  color: var(--orange);
  border: 1px solid var(--orange);
  background: rgba(255, 69, 0, 0.04);
}

.badge--soon {
  color: var(--gray-text);
  border: 1px solid var(--border);
}

.sport-name {
  font-family: var(--font-mono);
  font-size: 1.3rem;
  font-weight: 900;
  letter-spacing: 2px;
  margin: 0 0 4px;
}

.sport-season {
  font-family: var(--font-sans);
  font-size: 0.85rem;
  color: var(--gray-text);
  margin: 0 0 16px;
}

.sport-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 20px;
}

.sport-meta-item {
  font-family: var(--font-mono);
  font-size: 0.55rem;
  font-weight: 700;
  letter-spacing: 1px;
  color: var(--gray-text);
  background: var(--gray-light);
  padding: 3px 8px;
  text-transform: uppercase;
}

.sport-cta {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--orange);
  letter-spacing: 1px;
}

/* ===== Pipeline ===== */
.how-section {
  background: var(--gray-light);
}

.pipeline {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0;
}

.pipeline-step {
  padding: 28px 24px;
  background: var(--white);
  border: 1px solid var(--border);
  border-right: none;
  position: relative;
}

.pipeline-step:last-child {
  border-right: 1px solid var(--border);
}

.step-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.step-num {
  font-family: var(--font-mono);
  font-size: 1.1rem;
  font-weight: 900;
  color: var(--orange);
  letter-spacing: 1px;
}

.step-connector {
  flex: 1;
  height: 1px;
  background: linear-gradient(90deg, var(--orange), transparent);
}

.step-title {
  font-family: var(--font-mono);
  font-size: 0.9rem;
  font-weight: 700;
  margin: 0 0 8px;
}

.step-desc {
  font-family: var(--font-sans);
  font-size: 0.8rem;
  color: var(--gray-text);
  line-height: 1.6;
  margin: 0 0 14px;
}

.step-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.step-tag {
  font-family: var(--font-mono);
  font-size: 0.55rem;
  font-weight: 700;
  letter-spacing: 0.5px;
  color: var(--orange);
  background: rgba(255, 69, 0, 0.06);
  padding: 2px 8px;
}

/* ===== Debate Demo / Analysts ===== */
.debate-demo {
  margin-top: 64px;
}

.debate-demo-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 24px;
}

.debate-formula {
  font-family: var(--font-mono);
  font-size: 0.7rem;
  font-weight: 700;
  color: var(--orange);
  background: rgba(255, 69, 0, 0.06);
  padding: 4px 12px;
  letter-spacing: 1px;
}

.analysts-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.analyst-card {
  border: 1px solid var(--border);
  background: var(--white);
  padding: 20px;
  transition: all 0.2s;
}

.analyst-card:hover {
  border-color: var(--orange);
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.04);
}

.analyst-card-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.analyst-index {
  font-family: var(--font-mono);
  font-size: 0.65rem;
  font-weight: 700;
  color: var(--orange);
}

.analyst-bias {
  width: 24px;
  height: 4px;
  background: var(--border);
}

.bias-0 { background: linear-gradient(90deg, var(--orange), transparent); width: 32px; }
.bias-1 { background: linear-gradient(90deg, var(--orange), transparent); width: 28px; }
.bias-2 { background: linear-gradient(90deg, var(--orange), transparent); width: 20px; }
.bias-3 { background: linear-gradient(90deg, var(--orange), transparent); width: 26px; }
.bias-4 { background: linear-gradient(90deg, var(--orange), transparent); width: 18px; }
.bias-5 { background: linear-gradient(90deg, var(--orange), transparent); width: 22px; }
.bias-6 { background: linear-gradient(90deg, var(--orange), transparent); width: 30px; }

.analyst-name {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  font-weight: 700;
  display: block;
  margin-bottom: 8px;
}

.analyst-desc {
  font-family: var(--font-sans);
  font-size: 0.75rem;
  color: var(--gray-text);
  line-height: 1.6;
  margin: 0;
}

/* ===== Track Record ===== */
.track-section {
  background: var(--white);
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
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


/* ===== Insufficient Notice ===== */
.insufficient-notice {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 48px 0;
  text-align: center;
}

.insufficient-icon {
  font-size: 2rem;
  opacity: 0.5;
}

.insufficient-notice p {
  font-family: var(--font-mono);
  font-size: 0.85rem;
  color: var(--gray-text);
  margin: 0;
}

.track-link-wrap {
  text-align: center;
  margin-top: 24px;
}

.track-link {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  font-weight: 700;
  color: var(--orange);
  text-decoration: none;
  letter-spacing: 1px;
  transition: opacity 0.2s;
}

.track-link:hover {
  opacity: 0.7;
}

/* ===== FAQ ===== */
.faq-section {
  background: var(--gray-light);
}

.faq-list {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.faq-item {
  border: 1px solid var(--border);
  border-bottom: none;
  background: var(--white);
}

.faq-item:last-child {
  border-bottom: 1px solid var(--border);
}

.faq-item[open] {
  border-left: 3px solid var(--orange);
}

.faq-question {
  font-family: var(--font-mono);
  font-size: 0.85rem;
  font-weight: 700;
  padding: 20px 24px;
  cursor: pointer;
  list-style: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
  transition: color 0.2s;
}

.faq-question::-webkit-details-marker {
  display: none;
}

.faq-question::after {
  content: '+';
  font-size: 1.1rem;
  font-weight: 400;
  color: var(--gray-text);
  transition: transform 0.2s;
}

.faq-item[open] .faq-question::after {
  content: '−';
  color: var(--orange);
}

.faq-question:hover {
  color: var(--orange);
}

.faq-answer {
  font-family: var(--font-sans);
  font-size: 0.85rem;
  color: var(--gray-text);
  line-height: 1.8;
  padding: 0 24px 20px;
  margin: 0;
}

/* ===== Footer CTA ===== */
.footer-cta {
  background: var(--black);
  color: var(--white);
  padding: 100px 0 48px;
  position: relative;
  overflow: hidden;
}

.footer-cta::before {
  content: '';
  position: absolute;
  top: -100px;
  left: 50%;
  transform: translateX(-50%);
  width: 600px;
  height: 600px;
  background: radial-gradient(circle, rgba(255, 69, 0, 0.06) 0%, transparent 70%);
  pointer-events: none;
}

.footer-inner {
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
  position: relative;
  z-index: 1;
}

.footer-tag {
  font-family: var(--font-mono);
  font-size: 0.6rem;
  letter-spacing: 3px;
  color: var(--orange);
}

.footer-heading {
  font-family: var(--font-sans);
  font-size: 1.8rem;
  font-weight: 700;
  max-width: 500px;
  line-height: 1.4;
  margin: 0;
}

.btn-outline {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-mono);
  font-size: 0.85rem;
  font-weight: 700;
  letter-spacing: 1px;
  color: var(--white);
  border: 1px solid rgba(255, 255, 255, 0.3);
  padding: 14px 36px;
  text-decoration: none;
  transition: all 0.2s;
  margin-top: 8px;
}

.btn-outline:hover {
  border-color: var(--orange);
  color: var(--orange);
  transform: translateY(-1px);
}

.btn-outline:hover .btn-arrow {
  transform: translateX(3px);
}

.footer-bottom {
  margin-top: 48px;
  padding-top: 24px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  width: 100%;
}

.copyright {
  font-family: var(--font-mono);
  font-size: 0.6rem;
  color: #555;
  letter-spacing: 1px;
  margin: 0;
}


/* ===== Responsive ===== */
@media (max-width: 1024px) {
  .pipeline {
    grid-template-columns: repeat(2, 1fr);
  }
  .pipeline-step {
    border-right: 1px solid var(--border);
  }
  .pipeline-step:nth-child(2) {
    border-right: 1px solid var(--border);
  }
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .hero-title {
    font-size: 2.5rem;
  }
  .hero-subtitle {
    font-size: 0.9rem;
    padding: 0 16px;
  }
  .hero-particles {
    display: none;
  }
  .hero-stats-bar {
    flex-direction: column;
    width: auto;
  }
  .hero-stat {
    padding: 8px 28px;
  }
  .hero-stat-divider {
    width: 36px;
    height: 1px;
  }
  .sports-grid {
    grid-template-columns: 1fr;
  }
  .pipeline {
    grid-template-columns: 1fr;
  }
  .pipeline-step {
    border-right: 1px solid var(--border);
  }
  .step-connector {
    display: none;
  }
  .analysts-grid {
    grid-template-columns: 1fr;
  }
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .section {
    padding: 64px 0;
  }
  .section-header {
    flex-direction: column;
    gap: 8px;
  }
  .debate-demo-header {
    flex-direction: column;
    gap: 8px;
  }
  .footer-heading {
    font-size: 1.4rem;
  }
}
</style>
