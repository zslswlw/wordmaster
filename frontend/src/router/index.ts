import { createRouter, createWebHistory } from 'vue-router'
import Login from '../views/Login.vue'
import Register from '../views/Register.vue'
import Home from '../views/Home.vue'
import Dashboard from '../views/Dashboard.vue'
import Banks from '../views/Banks.vue'
import Groups from '../views/Groups.vue'
import Study from '../views/Study.vue'
import Review from '../views/Review.vue'
import Backup from '../views/Backup.vue'

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
        path: 'banks',
        name: 'Banks',
        component: Banks,
        meta: { title: '词库管理' }
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
        meta: { title: '数据备份' }
      }
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
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  
  // 如果访问公开页面（登录/注册）
  if (to.meta.public) {
    // 如果已登录，跳转到首页
    if (token) {
      next('/')
    } else {
      next()
    }
  } else {
    // 访问需要认证的页面
    if (!token) {
      next('/login')
    } else {
      next()
    }
  }
})

export default router
