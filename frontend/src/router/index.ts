import { createRouter, createWebHistory } from 'vue-router'
import Login from '../views/Login.vue'
import Register from '../views/Register.vue'
import Home from '../views/Home.vue'
import Dashboard from '../views/Dashboard.vue'
import Admin from '../views/Admin.vue'
import Groups from '../views/Groups.vue'
import Study from '../views/Study.vue'
import Review from '../views/Review.vue'
import Backup from '../views/Backup.vue'
import TestLab from '../views/TestLab.vue'
import { useAuth } from '../composables/useAuth'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: Home,
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: Dashboard,
        meta: { title: '仪表板' }
      },
      {
        path: 'admin',
        name: 'Admin',
        component: Admin,
        meta: { title: '管理', adminOnly: true }
      },
      {
        path: 'groups',
        name: 'Groups',
        component: Groups,
        meta: { title: '学习组' }
      },
      {
        path: 'study/:id?',
        name: 'Study',
        component: Study,
        meta: { title: '学习' }
      },
      {
        path: 'review',
        name: 'Review',
        component: Review,
        meta: { title: '复习计划' }
      },
      {
        path: 'backup',
        name: 'Backup',
        component: Backup,
        meta: { title: '数据备份', adminOnly: true }
      },
      {
        path: 'test-lab',
        name: 'TestLab',
        component: TestLab,
        meta: { title: '时间实验室' }
      },
    ]
  },
  {
    path: '/login',
    name: 'Login',
    component: Login,
    meta: { public: true }
  },
  {
    path: '/register',
    name: 'Register',
    component: Register,
    meta: { public: true }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 全局路由守卫
router.beforeEach(async (to) => {
  const token = localStorage.getItem('token')
  const { ensureAuth, isAdmin } = useAuth()

  if (to.meta.public) {
    if (token && await ensureAuth()) return '/'
    return true
  }
  if (!token || !await ensureAuth()) return '/login'
  if (to.meta.adminOnly && !isAdmin.value) return '/dashboard'
  return true
})

export default router
