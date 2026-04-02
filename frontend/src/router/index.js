import { createRouter, createWebHistory } from 'vue-router'
import { isLoggedIn } from '../stores/auth'
import Home from '../views/Home.vue'
import PredictionView from '../views/PredictionView.vue'
import HistoryView from '../views/HistoryView.vue'

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
  next()
})

export default router
