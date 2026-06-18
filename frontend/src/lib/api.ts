import axios from 'axios'
import { queryClient } from './queryClient'

export const api = axios.create({
  baseURL: '/api',
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  const tenantId = localStorage.getItem('tenant_id')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  if (tenantId) {
    config.headers['X-Tenant-ID'] = tenantId
  }
  return config
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    const status = err.response?.status
    if (status === 401) {
      if (!window.location.pathname.includes('/login')) {
        localStorage.removeItem('access_token')
        localStorage.removeItem('tenant_id')
        queryClient.clear()
        window.location.href = '/login'
      }
    }
    return Promise.reject(err)
  }
)
