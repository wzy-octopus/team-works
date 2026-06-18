import { create } from 'zustand'

interface Project {
  id: string
  name: string
  color: string
}

interface ProjectState {
  projects: Project[]
  activeProjectId: string | null
  setProjects: (projects: Project[]) => void
  setActiveProject: (id: string) => void
}

export const useProjectStore = create<ProjectState>((set) => ({
  projects: [],
  activeProjectId: null,
  setProjects: (projects) =>
    set((s) => ({
      projects,
      activeProjectId: s.activeProjectId ?? projects[0]?.id ?? null,
    })),
  setActiveProject: (id) => set({ activeProjectId: id }),
}))
