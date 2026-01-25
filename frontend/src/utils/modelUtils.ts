/**
 * Утилиты для работы с моделями
 */
import { api } from '../services/apiClient'
import { extractErrorMessage } from './apiErrorHandler'

// Кэш информации о моделях с сервера
let modelsCache: Map<string, { is_reasoning?: boolean }> = new Map()
let cacheTimestamp = 0
const CACHE_TTL = 60000 // 1 минута

/**
 * Загружает информацию о моделях с сервера и кэширует её.
 * Определение reasoning моделей происходит через Ollama API на backend.
 * Экспортируется для явной загрузки при старте приложения.
 */
export async function loadModelsInfo(): Promise<void> {
  const now = Date.now()
  if (now - cacheTimestamp < CACHE_TTL && modelsCache.size > 0) {
    return // Используем кэш
  }

  try {
    const data = await api.models.list()
    modelsCache.clear()
    
    // Обрабатываем детальную информацию о моделях
    if (data.models_detailed && Array.isArray(data.models_detailed)) {
      for (const model of data.models_detailed) {
        if (model.name) {
          modelsCache.set(model.name, {
            is_reasoning: model.is_reasoning || false
          })
        }
      }
    }
    
    cacheTimestamp = now
  } catch (error) {
    console.warn('Ошибка загрузки информации о моделях:', extractErrorMessage(error))
  }
}

/**
 * Проверяет, является ли модель reasoning (с встроенным CoT).
 * 
 * Определение происходит через Ollama API на backend, а не через хардкод паттернов.
 * Reasoning модели (DeepSeek-R1, QwQ, o1, o3) автоматически рассуждают
 * в <think> блоках, не требуя промптов вроде "think step by step".
 * 
 * @param modelName - Название модели
 * @returns Promise<boolean> - true если модель с reasoning capabilities
 */
export async function isReasoningModel(modelName: string): Promise<boolean> {
  if (!modelName) return false
  
  // Загружаем информацию о моделях если кэш устарел
  await loadModelsInfo()
  
  // Проверяем в кэше
  const modelInfo = modelsCache.get(modelName)
  if (modelInfo) {
    return modelInfo.is_reasoning || false
  }
  
  // Если модели нет в кэше, возвращаем false
  return false
}

/**
 * Синхронная версия проверки (использует кэш, может быть устаревшим).
 * Используйте для случаев, когда нужна синхронная проверка.
 * 
 * @param modelName - Название модели
 * @returns true если модель с reasoning capabilities (из кэша)
 */
export function isReasoningModelSync(modelName: string): boolean {
  if (!modelName) return false
  const modelInfo = modelsCache.get(modelName)
  return modelInfo?.is_reasoning || false
}

/**
 * Форматирует название модели для отображения.
 * 
 * @param modelName - Название модели
 * @returns Название модели без изменений (иконка отображается отдельно)
 */
export function formatModelName(modelName: string): string {
  return modelName || ''
}
