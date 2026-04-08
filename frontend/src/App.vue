<template>
  <div id="app-shell">
    <!-- 全局导航栏 -->
    <nav class="navbar">
      <router-link to="/" class="nav-brand">
        <img src="/favicon.svg" alt="NBA" class="nav-logo" />
        <span>PolySport</span>
      </router-link>
      <div class="nav-links">
        <template v-if="loggedIn">
          <a class="nav-link" :class="{ 'router-link-active': $route.path === '/predict' }" @click="goPredict">{{ t('nav.predict') }}</a>
          <router-link to="/track-record" class="nav-link">{{ t('nav.track_record') }}</router-link>
          <router-link to="/history" class="nav-link">{{ t('nav.history') }}</router-link>
          <button class="lang-switch" @click="toggleLocale">
            {{ locale === 'zh' ? 'EN' : '中' }}
          </button>
          <button class="account-btn" @click="openAccountModal('info')">{{ t('nav.my_account') }}</button>
        </template>
        <template v-else>
          <button class="lang-switch" @click="toggleLocale">
            {{ locale === 'zh' ? 'EN' : '中' }}
          </button>
          <button class="nav-link login-btn" @click="openAuthModal('login')">{{ t('nav.login') }}</button>
        </template>
      </div>
    </nav>

    <AuthModal />
    <AccountModal />
    <router-view />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter, useRoute } from 'vue-router'
import { isLoggedIn, openAuthModal, openAccountModal } from './stores/auth'
import AuthModal from './components/AuthModal.vue'
import AccountModal from './components/AccountModal.vue'

const router = useRouter()
const route = useRoute()
const { t, locale } = useI18n()

function goPredict() {
  if (route.path === '/predict') {
    // 已在 /predict，加时间戳 query 强制触发路由变化
    router.push({ path: '/predict', query: { _t: Date.now() } })
  } else {
    router.push('/predict')
  }
}

// ---- Auth state ----
const loggedIn = computed(() => isLoggedIn())

// ---- Language toggle ----
function toggleLocale() {
  const newLocale = locale.value === 'zh' ? 'en' : 'zh'
  locale.value = newLocale
  localStorage.setItem('locale', newLocale)
}
</script>

<style>
/* 全局样式重置 */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

:root {
  --black: #000000;
  --white: #FFFFFF;
  --orange: #FF4500;
  --gray-light: #F5F5F5;
  --gray-text: #666666;
  --border: #E5E5E5;
  --font-mono: 'JetBrains Mono', monospace;
  --font-sans: 'Space Grotesk', 'Noto Sans SC', system-ui, sans-serif;
}

#app {
  font-family: var(--font-mono);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: var(--black);
  background-color: var(--white);
}

/* 滚动条样式 */
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: #f1f1f1; }
::-webkit-scrollbar-thumb { background: #000000; }
::-webkit-scrollbar-thumb:hover { background: #333333; }

button { font-family: inherit; }

/* ===== Global Navbar ===== */
.navbar {
  height: 60px;
  background: var(--black);
  color: var(--white);
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 40px;
}

.nav-brand {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-mono);
  font-weight: 800;
  letter-spacing: 1px;
  font-size: 1.2rem;
  text-decoration: none;
  color: var(--white);
  cursor: pointer;
}

.nav-logo {
  height: 32px;
  width: auto;
}

.nav-links {
  display: flex;
  gap: 24px;
  align-items: center;
}

.nav-link {
  font-family: var(--font-mono);
  font-size: 0.85rem;
  color: #999;
  text-decoration: none;
  transition: color 0.2s;
  cursor: pointer;
}

.nav-link:hover { color: var(--white); }
.nav-link.router-link-exact-active,
.nav-link.router-link-active { color: var(--orange); }

.login-btn {
  background: none;
  border: none;
  cursor: pointer;
}

.lang-switch {
  background: none;
  border: 1px solid #666;
  color: #CCC;
  font-family: var(--font-mono);
  font-size: 0.75rem;
  font-weight: 700;
  padding: 4px 10px;
  cursor: pointer;
  transition: all 0.2s;
  letter-spacing: 0.5px;
}

.lang-switch:hover {
  border-color: var(--orange);
  color: var(--orange);
}

.account-btn {
  background: none;
  border: 1px solid #666;
  color: #CCC;
  font-family: var(--font-mono);
  font-size: 0.75rem;
  font-weight: 700;
  padding: 4px 14px;
  cursor: pointer;
  transition: all 0.2s;
  letter-spacing: 0.5px;
}

.account-btn:hover {
  border-color: var(--orange);
  color: var(--orange);
}

@media (max-width: 768px) {
  .navbar { padding: 0 12px; }
  .nav-brand span { display: none; }
  .nav-links { gap: 12px; }
}
</style>
