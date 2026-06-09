import { ref, computed } from 'vue'

const role = ref(localStorage.getItem('role') || 'user')

export function useAuth() {
  const isAdmin = computed(() => role.value === 'admin')

  function setRole(r: string) {
    role.value = r
    localStorage.setItem('role', r)
  }

  function clearAuth() {
    role.value = 'user'
    localStorage.removeItem('token')
    localStorage.removeItem('role')
  }

  return { isAdmin, role, setRole, clearAuth }
}
