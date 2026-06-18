import { useThemeStore } from '../stores/themeStore'

export function ThemeToggle() {
  const { dark, toggle } = useThemeStore()
  return (
    <button
      onClick={toggle}
      className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 transition-colors"
      title={dark ? 'ライトモード' : 'ダークモード'}
    >
      {dark ? '☀️' : '🌙'}
    </button>
  )
}
