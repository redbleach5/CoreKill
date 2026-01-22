/**
 * Универсальный хук для работы с API запросами.
 * 
 * Упрощает работу с асинхронными запросами, автоматически управляя:
 * - Состоянием загрузки (loading)
 * - Обработкой ошибок (error)
 * - Кэшированием данных (опционально)
 * 
 * Пример использования:
 *   const { data, loading, error, refetch } = useApi(() => api.models.list())
 */
import { useState, useCallback, useEffect, useRef } from 'react'

interface UseApiOptions {
  /** Автоматически выполнить запрос при монтировании компонента */
  immediate?: boolean
  /** Кэшировать результат (в памяти) */
  cache?: boolean
  /** TTL кэша в миллисекундах */
  cacheTTL?: number
}

interface UseApiReturn<T> {
  /** Данные ответа */
  data: T | null
  /** Состояние загрузки */
  loading: boolean
  /** Сообщение об ошибке */
  error: string | null
  /** Выполнить запрос вручную */
  refetch: () => Promise<void>
  /** Сбросить состояние (очистить данные и ошибки) */
  reset: () => void
}

/**
 * Универсальный хук для работы с API запросами.
 * 
 * @param apiCall - Функция, возвращающая Promise с данными
 * @param options - Опции хука
 * @returns Объект с данными, состоянием загрузки, ошибкой и методами управления
 */
export function useApi<T>(
  apiCall: () => Promise<T>,
  options: UseApiOptions = {}
): UseApiReturn<T> {
  const { immediate = true, cache = false, cacheTTL = 60000 } = options
  
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(immediate)
  const [error, setError] = useState<string | null>(null)
  
  // Кэш в памяти
  const cacheRef = useRef<{ data: T; timestamp: number } | null>(null)
  
  const execute = useCallback(async () => {
    // Проверяем кэш
    if (cache && cacheRef.current) {
      const now = Date.now()
      if (now - cacheRef.current.timestamp < cacheTTL) {
        setData(cacheRef.current.data)
        setLoading(false)
        return
      }
    }
    
    setLoading(true)
    setError(null)
    
    try {
      const result = await apiCall()
      setData(result)
      
      // Сохраняем в кэш
      if (cache) {
        cacheRef.current = {
          data: result,
          timestamp: Date.now()
        }
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Произошла ошибка'
      setError(errorMessage)
      setData(null)
    } finally {
      setLoading(false)
    }
  }, [apiCall, cache, cacheTTL])
  
  const refetch = useCallback(async () => {
    // Очищаем кэш при ручном обновлении
    if (cache) {
      cacheRef.current = null
    }
    await execute()
  }, [execute, cache])
  
  const reset = useCallback(() => {
    setData(null)
    setError(null)
    setLoading(false)
    if (cache) {
      cacheRef.current = null
    }
  }, [cache])
  
  // Автоматическое выполнение при монтировании
  useEffect(() => {
    if (immediate) {
      execute()
    }
  }, [immediate, execute])
  
  return {
    data,
    loading,
    error,
    refetch,
    reset
  }
}
