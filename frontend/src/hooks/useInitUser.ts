import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import { useAuthStore } from '../stores/authStore'
import { useProjectStore } from '../stores/projectStore'

export function useInitUser() {
  const { setUser, tenantId } = useAuthStore()
  const { setProjects } = useProjectStore()

  const token = localStorage.getItem('access_token')
  const enabled = !!tenantId && !!token

  const { data: user } = useQuery({
    queryKey: ['me', tenantId],
    queryFn: async () => {
      const res = await api.get('/auth/me')
      return res.data
    },
    enabled,
    retry: false,
    staleTime: 5 * 60 * 1000,
  })

  const { data: projects } = useQuery({
    queryKey: ['projects', tenantId],
    queryFn: async () => {
      const res = await api.get('/admin/projects')
      return res.data
    },
    enabled,
    retry: false,
    staleTime: 5 * 60 * 1000,
  })

  useEffect(() => {
    if (user) setUser(user)
  }, [user, setUser])

  useEffect(() => {
    if (projects) setProjects(projects)
  }, [projects, setProjects])
}
