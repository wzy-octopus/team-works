// 業務日付（JST, +09:00）ユーティリティ。
// ブラウザのタイムゾーンに依存せず Asia/Tokyo の暦日付で算出する（BUG-022）。
// DB 全体のタイムゾーンは変更せず、画面で扱う「業務日付」だけを JST 基準に統一する。

// 指定した日時を Asia/Tokyo の暦日付 YYYY-MM-DD で返す。
// en-CA ロケールは YYYY-MM-DD 形式を返す。
function jstDateString(d: Date): string {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Tokyo',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(d)
}

// 今日の業務日付（JST）を YYYY-MM-DD で返す。
export function jstToday(): string {
  return jstDateString(new Date())
}

// YYYY-MM-DD に日数を加減算した YYYY-MM-DD を返す。
// 正午 UTC を基準に UTC 演算のみを行うため、タイムゾーンによる日付ズレが起きない。
export function addDays(dateStr: string, days: number): string {
  const d = new Date(`${dateStr}T12:00:00Z`)
  d.setUTCDate(d.getUTCDate() + days)
  return d.toISOString().split('T')[0]
}

// 指定 YYYY-MM-DD を含む週の月曜日を YYYY-MM-DD で返す。
export function mondayOf(dateStr: string): string {
  const d = new Date(`${dateStr}T12:00:00Z`)
  const day = d.getUTCDay() // 0=日, 1=月, ... 6=土
  const diff = day === 0 ? -6 : 1 - day
  return addDays(dateStr, diff)
}

// 今週（JST 基準）の月曜日を YYYY-MM-DD で返す。
export function jstThisMonday(): string {
  return mondayOf(jstToday())
}
