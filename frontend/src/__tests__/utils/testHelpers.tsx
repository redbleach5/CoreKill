/**
 * Общие helpers для frontend тестов.
 */
import { ReactElement } from 'react'
import { render, RenderOptions } from '@testing-library/react'
import { setupTestMocks, cleanupTestMocks } from './mocks'

/**
 * Обертка для render с автоматической настройкой моков.
 */
export function renderWithMocks(
  ui: ReactElement,
  options?: Omit<RenderOptions, 'wrapper'>
) {
  setupTestMocks()
  return render(ui, options)
}

/**
 * Создает мок для API ответа.
 */
export function mockApiResponse<T>(data: T, options?: { ok?: boolean; status?: number }) {
  return {
    ok: options?.ok ?? true,
    status: options?.status ?? 200,
    statusText: 'OK',
    json: async () => data,
    text: async () => JSON.stringify(data),
    headers: new Headers(),
  }
}

/**
 * Создает мок для API ошибки.
 */
export function mockApiError(
  status: number = 500,
  message: string = 'Internal Server Error'
) {
  return {
    ok: false,
    status,
    statusText: message,
    json: async () => ({ detail: message }),
    text: async () => JSON.stringify({ detail: message }),
    headers: new Headers(),
  }
}

/**
 * Ожидает завершения async операции.
 */
export async function waitForAsync(callback: () => Promise<void>, timeout = 5000) {
  const startTime = Date.now()
  
  while (Date.now() - startTime < timeout) {
    try {
      await callback()
      return
    } catch {
      await new Promise(resolve => setTimeout(resolve, 100))
    }
  }
  
  throw new Error(`Timeout waiting for async operation (${timeout}ms)`)
}
