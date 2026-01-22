/**
 * Централизованная обработка ошибок API
 * 
 * Унифицирует обработку ошибок от backend, обеспечивая единообразный формат.
 */

export interface ApiError {
  detail?: string
  error?: string
  message?: string
  error_message?: string
  error_type?: string
}

/**
 * Извлекает сообщение об ошибке из различных форматов ответа API.
 * 
 * Backend может возвращать ошибки в разных форматах:
 * - HTTPException: { detail: "..." }
 * - SSE error event: { error: "...", error_message: "..." }
 * - Custom error: { message: "..." }
 * 
 * @param error - Ошибка (может быть Error, объект, строка)
 * @returns Сообщение об ошибке на русском языке
 */
export function extractErrorMessage(error: unknown): string {
  // Если это строка, возвращаем как есть
  if (typeof error === 'string') {
    return error
  }
  
  // Если это Error объект
  if (error instanceof Error) {
    return error.message
  }
  
  // Если это объект с полями ошибки
  if (typeof error === 'object' && error !== null) {
    const apiError = error as ApiError
    
    // Приоритет: detail > error_message > error > message
    return (
      apiError.detail ||
      apiError.error_message ||
      apiError.error ||
      apiError.message ||
      'Неизвестная ошибка'
    )
  }
  
  return 'Неизвестная ошибка'
}

/**
 * Обрабатывает ответ от fetch запроса и извлекает ошибку если есть.
 * 
 * @param response - Response объект от fetch
 * @returns Promise с сообщением об ошибке или null если успешно
 */
export async function handleApiResponse(response: Response): Promise<string | null> {
  if (response.ok) {
    return null
  }
  
  try {
    const errorData = await response.json()
    return extractErrorMessage(errorData)
  } catch {
    // Если не удалось распарсить JSON, используем статус
    return `Ошибка ${response.status}: ${response.statusText}`
  }
}

/**
 * Обёртка для fetch с автоматической обработкой ошибок.
 * 
 * @param url - URL для запроса
 * @param options - Опции для fetch
 * @returns Promise с Response или выбрасывает ошибку с понятным сообщением
 */
export async function fetchWithErrorHandling(
  url: string,
  options: RequestInit = {}
): Promise<Response> {
  try {
    const response = await fetch(url, {
      ...options,
      signal: AbortSignal.timeout(30000) // 30 секунд timeout
    })
    
    if (!response.ok) {
      const errorMessage = await handleApiResponse(response)
      throw new Error(errorMessage || `HTTP ${response.status}: ${response.statusText}`)
    }
    
    return response
  } catch (error) {
    // Обрабатываем AbortError (timeout)
    if (error instanceof Error && error.name === 'AbortError') {
      throw new Error('Превышено время ожидания ответа от сервера (30 секунд)')
    }
    
    // Обрабатываем сетевые ошибки
    if (error instanceof TypeError && error.message.includes('fetch')) {
      throw new Error('Ошибка подключения к серверу. Проверьте, что backend запущен.')
    }
    
    // Пробрасываем остальные ошибки
    throw error
  }
}

/**
 * Обрабатывает SSE ошибки.
 * 
 * @param eventData - Данные из SSE события error
 * @returns Сообщение об ошибке
 */
export function handleSSEError(eventData: unknown): string {
  return extractErrorMessage(eventData)
}
