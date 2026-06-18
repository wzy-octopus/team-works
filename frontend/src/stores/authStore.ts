import { create } from 'zustand'

interface User {
  id: string
  email: string
  name: string
  role?: string
  project_ids?: string[]
}

interface AuthState {
  user: User | null
  tenantId: string | null
  setUser: (user: User) => void
  setTenantId: (id: string) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  tenantId: localStorage.getItem('tenant_id'),
  setUser: (user) => set({ user }),
  setTenantId: (id) => {
    localStorage.setItem('tenant_id', id)
    set({ tenantId: id })
  },
  logout: () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('tenant_id')
    set({ user: null, tenantId: null })
  },
}))
