import { createRouter, createWebHistory } from 'vue-router'
import { isLoggedIn, hasPermission } from '../stores/auth'
import Home from '../views/Home.vue'
import PredictionView from '../views/PredictionView.vue'
import HistoryView from '../views/HistoryView.vue'
import TrackRecordView from '../views/TrackRecordView.vue'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: Home,
    meta: { title: 'PolySport — AI NBA Prediction Engine', description: 'AI-powered NBA game prediction using multi-agent debate, knowledge graphs, and on-chain smart money from Polymarket.' }
  },
  {
    path: '/predict',
    name: 'Prediction',
    component: PredictionView,
    meta: { title: 'NBA Game Prediction | PolySport', description: 'Select an NBA game and get AI-powered predictions with multi-agent debate analysis.' }
  },
  {
    path: '/track-record',
    name: 'TrackRecord',
    component: TrackRecordView,
    meta: { auth: true, permission: 'track_record', title: 'Track Record | PolySport', description: 'Verified prediction track record — moneyline, spread, and totals hit rates for NBA games.' }
  },
  {
    path: '/history',
    name: 'History',
    component: HistoryView,
    meta: { auth: true, title: 'Prediction History | PolySport', description: 'View your past NBA game prediction records and results.' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  const loggedIn = isLoggedIn()

  if (to.meta.auth && !loggedIn) {
    return next('/predict')
  }
  if (to.meta.permission && !hasPermission(to.meta.permission)) {
    return next('/')
  }
  next()
})

router.afterEach((to) => {
  document.title = to.meta.title || 'PolySport'
  const descEl = document.querySelector('meta[name="description"]')
  if (descEl) {
    descEl.setAttribute('content', to.meta.description || '')
  }
})

export default router
