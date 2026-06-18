import { QueryClient } from '@tanstack/react-query'

// アプリ全体で共有する単一の QueryClient インスタンス。
// App.tsx と lib/api.ts の循環 import を避けるため独立モジュールに切り出している。
export const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
})
