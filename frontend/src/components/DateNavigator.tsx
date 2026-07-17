import { addDays } from '../lib/date'

type DateNavigatorProps = {
  value: string
  max: string
  active?: boolean
  onActivate?: () => void
  onChange: (date: string) => void
}

export function DateNavigator({
  value,
  max,
  active = false,
  onActivate,
  onChange,
}: DateNavigatorProps) {
  return (
    <div
      className={`flex items-center rounded-lg border border-[var(--border)] bg-[var(--bg-input)] ${
        active ? 'ring-1 ring-indigo-500' : ''
      }`}
    >
      <button
        type="button"
        title="前の日"
        aria-label="前の日"
        onClick={() => {
          onActivate?.()
          onChange(addDays(value, -1))
        }}
        className="w-8 h-8 shrink-0 text-[var(--text-muted)] hover:text-[var(--text-primary)]"
      >
        ‹
      </button>
      <input
        type="date"
        value={value}
        max={max}
        onFocus={onActivate}
        onChange={(event) => onChange(event.target.value || max)}
        className="h-8 px-2 bg-transparent border-x border-[var(--border)] text-[var(--text-primary)] text-sm focus:outline-none"
      />
      <button
        type="button"
        title="次の日"
        aria-label="次の日"
        disabled={value >= max}
        onClick={() => {
          onActivate?.()
          onChange(addDays(value, 1))
        }}
        className="w-8 h-8 shrink-0 text-[var(--text-muted)] hover:text-[var(--text-primary)] disabled:opacity-30 disabled:cursor-not-allowed"
      >
        ›
      </button>
    </div>
  )
}
