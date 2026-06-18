import { create } from 'zustand'

interface ThemeState {
  dark: boolean
  toggle: () => void
}

const saved = localStorage.getItem('theme')
const initialDark = saved ? saved === 'dark' : window.matchMedia('(prefers-color-scheme: dark)').matches

export const useThemeStore = create<ThemeState>((set) => ({
  dark: initialDark,
  toggle: () =>
    set((s) => {
      const next = !s.dark
      localStorage.setItem('theme', next ? 'dark' : 'light')
      return { dark: next }
    }),
}))
