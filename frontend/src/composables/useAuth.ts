import { ref, computed } from 'vue'
import { authAPI } from '../api'

const role = ref('user')
const username = ref('')
const verified = ref(false)
let verification: Promise<boolean> | null = null

export function useAuth() {
  const isAdmin = computed(() => role.value === 'admin')

  function setRole(r: string) {
    role.value = r
    verified.value = true
  }

  async function ensureAuth(force = false) {
    if (!localStorage.getItem('token')) {
      clearAuth()
      return false
    }
    if (verified.value && !force) return true
    if (verification) return verification
    verification = authAPI.me().then(({ data }) => {
      role.value = data.role || 'user'
      username.value = data.username || ''
      verified.value = true
      return true
    }).catch(() => {
      clearAuth()
      return false
    }).finally(() => {
      verification = null
    })
    return verification
  }

  function clearAuth() {
    role.value = 'user'
    username.value = ''
    verified.value = false
    localStorage.removeItem('token')
    localStorage.removeItem('role')
  }

  return { isAdmin, role, username, verified, setRole, ensureAuth, clearAuth }
}
