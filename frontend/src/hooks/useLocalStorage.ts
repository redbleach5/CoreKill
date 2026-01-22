/**
 * Хук для работы с localStorage.
 * 
 * Предоставляет:
 * - Типобезопасное чтение/запись данных
 * - Автоматическую сериализацию/десериализацию JSON
 * - Обработку ошибок парсинга
 * - Синхронизацию между вкладками (опционально)
 * 
 * Пример использования:
 *   const [value, setValue] = useLocalStorage<string>('myKey', 'default')
 *   const [settings, setSettings] = useLocalStorage<Settings>('settings', defaultSettings)
 */
import { useState, useEffect, useCallback } from 'react'

interface UseLocalStorageOptions {
  /** Значение по умолчанию, если ключ отсутствует */
  defaultValue?: unknown
  /** Синхронизировать изменения между вкладками */
  sync?: boolean
}

/**
 * Хук для работы с localStorage.
 * 
 * @param key - Ключ в localStorage
 * @param initialValue - Начальное значение (если ключ отсутствует)
 * @param options - Опции хука
 * @returns Кортеж [значение, функция установки значения]
 */
export function useLocalStorage<T>(
  key: string,
  initialValue: T,
  options: UseLocalStorageOptions = {}
): [T, (value: T | ((prev: T) => T)) => void] {
  const { sync = false } = options
  
  // Функция чтения из localStorage
  const readValue = useCallback((): T => {
    try {
      const item = window.localStorage.getItem(key)
      if (item === null) {
        return initialValue
      }
      return JSON.parse(item) as T
    } catch (error) {
      console.warn(`Ошибка чтения из localStorage ключа "${key}":`, error)
      return initialValue
    }
  }, [key, initialValue])
  
  // Состояние с начальным значением
  const [storedValue, setStoredValue] = useState<T>(readValue)
  
  // Функция установки значения
  const setValue = useCallback(
    (value: T | ((prev: T) => T)) => {
      try {
        // Поддерживаем функцию обновления (как в useState)
        const valueToStore = value instanceof Function ? value(storedValue) : value
        
        // Сохраняем в состояние
        setStoredValue(valueToStore)
        
        // Сохраняем в localStorage
        window.localStorage.setItem(key, JSON.stringify(valueToStore))
      } catch (error) {
        console.error(`Ошибка записи в localStorage ключа "${key}":`, error)
      }
    },
    [key, storedValue]
  )
  
  // Синхронизация между вкладками
  useEffect(() => {
    if (!sync) return
    
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === key && e.newValue !== null) {
        try {
          setStoredValue(JSON.parse(e.newValue) as T)
        } catch (error) {
          console.warn(`Ошибка синхронизации localStorage ключа "${key}":`, error)
        }
      }
    }
    
    window.addEventListener('storage', handleStorageChange)
    return () => {
      window.removeEventListener('storage', handleStorageChange)
    }
  }, [key, sync])
  
  return [storedValue, setValue]
}

/**
 * Хук для работы с простыми строками в localStorage (без JSON).
 * 
 * @param key - Ключ в localStorage
 * @param initialValue - Начальное значение
 * @returns Кортеж [значение, функция установки значения]
 */
export function useLocalStorageString(
  key: string,
  initialValue: string = ''
): [string, (value: string | ((prev: string) => string)) => void] {
  const readValue = useCallback((): string => {
    try {
      const item = window.localStorage.getItem(key)
      return item ?? initialValue
    } catch (error) {
      console.warn(`Ошибка чтения из localStorage ключа "${key}":`, error)
      return initialValue
    }
  }, [key, initialValue])
  
  const [storedValue, setStoredValue] = useState<string>(readValue)
  
  const setValue = useCallback(
    (value: string | ((prev: string) => string)) => {
      try {
        const valueToStore = value instanceof Function ? value(storedValue) : value
        setStoredValue(valueToStore)
        window.localStorage.setItem(key, valueToStore)
      } catch (error) {
        console.error(`Ошибка записи в localStorage ключа "${key}":`, error)
      }
    },
    [key, storedValue]
  )
  
  return [storedValue, setValue]
}
