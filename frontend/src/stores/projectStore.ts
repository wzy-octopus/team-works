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
    set((s) => {
      // 現在の選択が新しい（フィルタ済み）一覧に無い場合は先頭へリセットする。
      // 非表示/未所属 project に選択が残って 403 になるのを防ぐ（BUG-024）。
      const stillVisible = !!s.activeProjectId && projects.some((p) => p.id === s.activeProjectId)
      return {
        projects,
        activeProjectId: stillVisible ? s.activeProjectId : (projects[0]?.id ?? null),
      }
    }),
  setActiveProject: (id) => set({ activeProjectId: id }),
}))
