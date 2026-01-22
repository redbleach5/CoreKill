/**
 * Утилиты для работы с SSE событиями.
 * 
 * Устраняет дублирование кода обработки SSE событий.
 */
import type React from 'react'

/**
 * Создаёт обработчик SSE события с валидацией и обработкой ошибок.
 * 
 * @param handler - Функция обработки данных события
 * @param eventName - Имя события для логирования
 * @param requiredFields - Обязательные поля в данных события
 * @returns Обработчик события для addEventListener
 */
export function createSSEEventHandler<T = unknown>(
  handler: (data: T) => void,
  eventName: string,
  requiredFields: string[] = []
): (event: MessageEvent) => void {
  return (event: MessageEvent) => {
    try {
      // Проверяем наличие данных
      if (!event.data || event.data.trim() === '') {
        return
      }

      // Парсим JSON
      const data = JSON.parse(event.data) as T

      // Проверяем обязательные поля
      if (requiredFields.length > 0) {
        const missingFields = requiredFields.filter(field => !(field in data))
        if (missingFields.length > 0) {
          console.warn(`⚠️ ${eventName}: отсутствуют обязательные поля:`, missingFields, data)
          return
        }
      }

      // Вызываем обработчик
      handler(data)
    } catch (e) {
      console.error(`❌ Ошибка парсинга ${eventName}:`, e, event.data)
    }
  }
}

/**
 * Создаёт обработчик SSE события с обновлением времени последнего события.
 * 
 * @param handler - Функция обработки данных события
 * @param eventName - Имя события для логирования
 * @param lastEventTimeRef - Ref для хранения времени последнего события
 * @param requiredFields - Обязательные поля в данных события
 * @returns Обработчик события для addEventListener
 */
export function createSSEEventHandlerWithTime<T = unknown>(
  handler: (data: T) => void,
  eventName: string,
  lastEventTimeRef: React.MutableRefObject<number>,
  requiredFields: string[] = []
): (event: MessageEvent) => void {
  return createSSEEventHandler<T>(
    (data) => {
      lastEventTimeRef.current = Date.now()
      handler(data)
    },
    eventName,
    requiredFields
  )
}
