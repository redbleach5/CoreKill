/**
 * Хук для работы с моделями.
 * 
 * Предоставляет:
 * - Список доступных моделей
 * - Информацию о reasoning моделях
 * - Автоматическое обновление списка
 * - Кэширование данных
 * 
 * Пример использования:
 *   const { models, modelsDetailed, loading, error, refresh } = useModels()
 */
import { useState, useCallback, useEffect } from 'react'
import { api } from '../services/apiClient'
import { ModelsResponse, ModelInfo } from '../types/api'
import { loadModelsInfo, isReasoningModelSync } from '../utils/modelUtils'

interface UseModelsReturn {
  /** Список названий моделей */
  models: string[]
  /** Детальная информация о моделях */
  modelsDetailed: ModelInfo[]
  /** Состояние загрузки */
  loading: boolean
  /** Сообщение об ошибке */
  error: string | null
  /** Обновить список моделей */
  refresh: () => Promise<void>
  /** Проверить, является ли модель reasoning */
  isReasoning: (modelName: string) => boolean
  /** Получить рекомендации моделей по сложности */
  getRecommendation: (complexity: 'simple' | 'medium' | 'complex') => string | undefined
}

/**
 * Хук для работы с моделями.
 * 
 * Автоматически загружает список моделей при монтировании компонента
 * и кэширует информацию о reasoning моделях.
 */
export function useModels(): UseModelsReturn {
  const [models, setModels] = useState<string[]>([])
  const [modelsDetailed, setModelsDetailed] = useState<ModelInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [recommendations, setRecommendations] = useState<{
    simple?: string
    medium?: string
    complex?: string
  }>({})
  
  const loadModels = useCallback(async () => {
    setLoading(true)
    setError(null)
    
    try {
      const data: ModelsResponse = await api.models.list()
      setModels(data.models || [])
      setModelsDetailed(data.models_detailed || [])
      setRecommendations(data.recommendations || {})
      
      // Загружаем информацию о reasoning моделях для кэша
      await loadModelsInfo()
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Ошибка загрузки моделей'
      setError(errorMessage)
      setModels([])
      setModelsDetailed([])
    } finally {
      setLoading(false)
    }
  }, [])
  
  const refresh = useCallback(async () => {
    await loadModels()
    // Также обновляем список на сервере
    try {
      await api.models.refresh()
      await loadModels()
    } catch (err) {
      console.error('Ошибка обновления списка моделей:', err)
    }
  }, [loadModels])
  
  const isReasoning = useCallback((modelName: string): boolean => {
    return isReasoningModelSync(modelName)
  }, [])
  
  const getRecommendation = useCallback(
    (complexity: 'simple' | 'medium' | 'complex'): string | undefined => {
      return recommendations[complexity]
    },
    [recommendations]
  )
  
  // Загружаем модели при монтировании
  useEffect(() => {
    loadModels()
  }, [loadModels])
  
  return {
    models,
    modelsDetailed,
    loading,
    error,
    refresh,
    isReasoning,
    getRecommendation
  }
}
