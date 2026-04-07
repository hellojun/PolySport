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
    component: Home
  },
  {
    path: '/predict',
    name: 'Prediction',
    component: PredictionView
  },
  {
    path: '/track-record',
    name: 'TrackRecord',
    component: TrackRecordView,
    meta: { auth: true, permission: 'track_record' }
  },
  {
    path: '/history',
    name: 'History',
    component: HistoryView,
    meta: { auth: true }
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

export default router
