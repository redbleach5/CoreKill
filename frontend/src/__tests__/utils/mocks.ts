/**
 * Общие моки для frontend тестов.
 * 
 * Централизованное место для всех моков, чтобы избежать дублирования.
 */
import { vi } from 'vitest'

/**
 * Мок для localStorage.
 * Используется во всех тестах, которые работают с localStorage.
 */
export function createLocalStorageMock() {
  let store: Record<string, string> = {}
  
  return {
    getItem: (key: string) => store[key] || null,
    setItem: (key: string, value: string) => {
      store[key] = value.toString()
    },
    removeItem: (key: string) => {
      delete store[key]
    },
    clear: () => {
      store = {}
    },
    // Для отладки
    _getStore: () => ({ ...store }),
  }
}

/**
 * Мок для window.location.
 */
export function createLocationMock(overrides: Partial<Location> = {}) {
  return {
    port: '5173',
    href: 'http://localhost:5173',
    origin: 'http://localhost:5173',
    protocol: 'http:',
    host: 'localhost:5173',
    hostname: 'localhost',
    pathname: '/',
    search: '',
    hash: '',
    ...overrides,
  }
}

/**
 * Мок для fetch ответа.
 */
export function createFetchMockResponse(
  data: unknown,
  options: { ok?: boolean; status?: number; statusText?: string } = {}
) {
  return {
    ok: options.ok ?? true,
    status: options.status ?? 200,
    statusText: options.statusText ?? 'OK',
    json: async () => data,
    text: async () => JSON.stringify(data),
    headers: new Headers(),
  }
}

/**
 * Мок для fetch с ошибкой сети.
 */
export function createFetchNetworkError() {
  return Promise.reject(new TypeError('Failed to fetch'))
}

/**
 * Мок для fetch с HTTP ошибкой.
 */
export function createFetchHttpError(
  status: number = 500,
  statusText: string = 'Internal Server Error',
  data: unknown = { detail: 'Error' }
) {
  return Promise.resolve({
    ok: false,
    status,
    statusText,
    json: async () => data,
    text: async () => JSON.stringify(data),
    headers: new Headers(),
  })
}

/**
 * Настраивает моки для тестовой среды.
 */
export function setupTestMocks() {
  // Мокаем localStorage
  const localStorageMock = createLocalStorageMock()
  Object.defineProperty(window, 'localStorage', {
    value: localStorageMock,
    writable: true,
  })

  // Мокаем location
  Object.defineProperty(window, 'location', {
    value: createLocationMock(),
    writable: true,
  })

  // Мокаем fetch
  globalThis.fetch = vi.fn() as any

  return {
    localStorage: localStorageMock,
    fetch: globalThis.fetch as ReturnType<typeof vi.fn>,
  }
}

/**
 * Очищает все моки после теста.
 */
export function cleanupTestMocks() {
  vi.clearAllMocks()
  if (window.localStorage && typeof window.localStorage.clear === 'function') {
    window.localStorage.clear()
  }
}
