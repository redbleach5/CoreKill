/**
 * Hook для персистентности задач (localStorage + backend API)
 * 
 * Сохраняет состояние UI в localStorage и синхронизирует с backend checkpoints.
 * Позволяет восстановить состояние после обновления страницы или падения.
 */
import { useState, useEffect, useCallback } from 'react'
import { ChatMessage } from '../types/chat'
import { StageStatus, AgentResults, Metrics } from './useAgentStream'

// Ключи для localStorage
const STORAGE_KEYS = {
  MESSAGES: 'cursor_killer_messages',
  STAGES: 'cursor_killer_stages',
  RESULTS: 'cursor_killer_results',
  METRICS: 'cursor_killer_metrics',
  CURRENT_TASK_ID: 'cursor_killer_current_task_id',
  CONVERSATION_ID: 'cursor_killer_conversation_id',
  OPTIONS: 'cursor_killer_options',
  LAST_UPDATED: 'cursor_killer_last_updated'
}

// Максимальный возраст сохраненного состояния (24 часа)
const MAX_STATE_AGE_MS = 24 * 60 * 60 * 1000

// Типы для активной задачи с backend
export interface ActiveTask {
  task_id: string
  task_text: string
  created_at: string
  updated_at: string
  last_stage: string
  status: 'running' | 'paused' | 'completed' | 'failed'
  iteration: number
  model: string | null
}

// Состояние UI для сохранения
export interface PersistedUIState {
  messages: ChatMessage[]
  stages: Record<string, StageStatus>
  results: AgentResults
  metrics: Metrics
  currentTaskId: string | null
  conversationId: string | null
  lastUpdated: number
}

// Возвращаемые данные хука
interface UseTaskPersistenceReturn {
  // Сохраненное состояние
  persistedState: PersistedUIState | null
  // Активные задачи с backend
  activeTasks: ActiveTask[]
  // Флаг наличия восстанавливаемого состояния
  hasRecoverableState: boolean
  // Флаг загрузки
  isLoading: boolean
  // Ошибка
  error: string | null
  
  // Методы
  saveState: (state: Partial<PersistedUIState>) => void
  loadState: () => PersistedUIState | null
  clearState: () => void
  fetchActiveTasks: () => Promise<void>
  resumeTask: (taskId: string) => Promise<Response>
  deleteTask: (taskId: string) => Promise<void>
  cancelTask: (taskId: string) => Promise<void>
}

export function useTaskPersistence(): UseTaskPersistenceReturn {
  const [persistedState, setPersistedState] = useState<PersistedUIState | null>(null)
  const [activeTasks, setActiveTasks] = useState<ActiveTask[]>([])
  const [hasRecoverableState, setHasRecoverableState] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  /**
   * Сохраняет состояние в localStorage
   */
  const saveState = useCallback((state: Partial<PersistedUIState>) => {
    try {
      const now = Date.now()
      
      if (state.messages !== undefined && state.messages.length > 0) {
        // Сериализуем с преобразованием Date в строку
        const serializedMessages = state.messages.map(msg => ({
          ...msg,
          timestamp: msg.timestamp instanceof Date 
            ? msg.timestamp.toISOString() 
            : msg.timestamp
        }))
        localStorage.setItem(STORAGE_KEYS.MESSAGES, JSON.stringify(serializedMessages))
        console.log('[Persistence] Saved messages:', serializedMessages.length)
      }
      
      if (state.stages !== undefined && Object.keys(state.stages).length > 0) {
        localStorage.setItem(STORAGE_KEYS.STAGES, JSON.stringify(state.stages))
      }
      
      if (state.results !== undefined) {
        localStorage.setItem(STORAGE_KEYS.RESULTS, JSON.stringify(state.results))
      }
      
      if (state.metrics !== undefined) {
        localStorage.setItem(STORAGE_KEYS.METRICS, JSON.stringify(state.metrics))
      }
      
      if (state.currentTaskId !== undefined) {
        if (state.currentTaskId) {
          localStorage.setItem(STORAGE_KEYS.CURRENT_TASK_ID, state.currentTaskId)
        } else {
          localStorage.removeItem(STORAGE_KEYS.CURRENT_TASK_ID)
        }
      }
      
      if (state.conversationId !== undefined) {
        if (state.conversationId) {
          localStorage.setItem(STORAGE_KEYS.CONVERSATION_ID, state.conversationId)
          console.log('[Persistence] Saved conversationId:', state.conversationId)
        } else {
          localStorage.removeItem(STORAGE_KEYS.CONVERSATION_ID)
        }
      }
      
      localStorage.setItem(STORAGE_KEYS.LAST_UPDATED, now.toString())
      
    } catch (e) {
      console.error('Ошибка сохранения состояния:', e)
    }
  }, [])

  /**
   * Загружает состояние из localStorage
   */
  const loadState = useCallback((): PersistedUIState | null => {
    try {
      const lastUpdated = localStorage.getItem(STORAGE_KEYS.LAST_UPDATED)
      
      // Проверяем возраст состояния
      if (lastUpdated) {
        const age = Date.now() - parseInt(lastUpdated, 10)
        if (age > MAX_STATE_AGE_MS) {
          // Состояние слишком старое, очищаем напрямую
          Object.values(STORAGE_KEYS).forEach(key => {
            localStorage.removeItem(key)
          })
          return null
        }
      } else {
        return null
      }
      
      const messagesStr = localStorage.getItem(STORAGE_KEYS.MESSAGES)
      const stagesStr = localStorage.getItem(STORAGE_KEYS.STAGES)
      const resultsStr = localStorage.getItem(STORAGE_KEYS.RESULTS)
      const metricsStr = localStorage.getItem(STORAGE_KEYS.METRICS)
      const currentTaskId = localStorage.getItem(STORAGE_KEYS.CURRENT_TASK_ID)
      const conversationId = localStorage.getItem(STORAGE_KEYS.CONVERSATION_ID)
      
      // Парсим сообщения с восстановлением Date
      let messages: ChatMessage[] = []
      if (messagesStr) {
        try {
          const parsed = JSON.parse(messagesStr)
          messages = parsed.map((msg: ChatMessage & { timestamp: string }) => ({
            ...msg,
            timestamp: new Date(msg.timestamp)
          }))
        } catch {
          console.warn('Не удалось распарсить сообщения из localStorage')
        }
      }
      
      const state: PersistedUIState = {
        messages,
        stages: stagesStr ? JSON.parse(stagesStr) : {},
        results: resultsStr ? JSON.parse(resultsStr) : {},
        metrics: metricsStr ? JSON.parse(metricsStr) : {
          planning: 0, research: 0, testing: 0, coding: 0, overall: 0
        },
        currentTaskId: currentTaskId || null,
        conversationId: conversationId || null,
        lastUpdated: parseInt(lastUpdated, 10)
      }
      
      console.log('[Persistence] Loaded state:', { 
        messagesCount: state.messages.length,
        hasConversationId: !!state.conversationId
      })
      
      return state
      
    } catch (e) {
      console.error('Ошибка загрузки состояния:', e)
      return null
    }
  }, [])

  /**
   * Очищает сохраненное состояние
   */
  const clearState = useCallback(() => {
    try {
      Object.values(STORAGE_KEYS).forEach(key => {
        localStorage.removeItem(key)
      })
      setPersistedState(null)
      setHasRecoverableState(false)
    } catch (e) {
      console.error('Ошибка очистки состояния:', e)
    }
  }, [])

  /**
   * Получает список активных задач с backend
   */
  const fetchActiveTasks = useCallback(async () => {
    try {
      const response = await fetch('/api/tasks/active')
      
      if (!response.ok) {
        throw new Error('Ошибка получения активных задач')
      }
      
      const data = await response.json()
      
      if (data.persistence_enabled === false) {
        setActiveTasks([])
        return
      }
      
      setActiveTasks(data.tasks || [])
      
    } catch (e) {
      console.error('Ошибка получения активных задач:', e)
      setError('Не удалось получить список активных задач')
    }
  }, [])

  /**
   * Возобновляет выполнение задачи
   */
  const resumeTask = useCallback(async (taskId: string): Promise<Response> => {
    const response = await fetch(`/api/tasks/${taskId}/resume`, {
      method: 'POST'
    })
    
    if (!response.ok) {
      throw new Error('Ошибка возобновления задачи')
    }
    
    return response
  }, [])

  /**
   * Удаляет задачу
   */
  const deleteTask = useCallback(async (taskId: string) => {
    const response = await fetch(`/api/tasks/${taskId}`, {
      method: 'DELETE'
    })
    
    if (!response.ok) {
      throw new Error('Ошибка удаления задачи')
    }
    
    // Обновляем список активных задач
    setActiveTasks(prev => prev.filter(t => t.task_id !== taskId))
  }, [])

  /**
   * Отменяет/приостанавливает задачу
   */
  const cancelTask = useCallback(async (taskId: string) => {
    const response = await fetch(`/api/tasks/${taskId}/cancel`, {
      method: 'POST'
    })
    
    if (!response.ok) {
      throw new Error('Ошибка отмены задачи')
    }
    
    // Обновляем список активных задач
    await fetchActiveTasks()
  }, [fetchActiveTasks])

  /**
   * Инициализация: загружаем состояние и проверяем backend
   */
  useEffect(() => {
    const init = async () => {
      setIsLoading(true)
      setError(null)
      
      try {
        // Загружаем локальное состояние
        const localState = loadState()
        setPersistedState(localState)
        
        // Проверяем есть ли активные задачи на backend
        let backendTasks: ActiveTask[] = []
        try {
          const response = await fetch('/api/tasks/active')
          if (response.ok) {
            const data = await response.json()
            if (data.persistence_enabled !== false) {
              backendTasks = data.tasks || []
              setActiveTasks(backendTasks)
            }
          }
        } catch {
          console.warn('Не удалось загрузить активные задачи с backend')
        }
        
        // Определяем есть ли что восстанавливать
        const hasLocalMessages = localState && localState.messages.length > 0
        const hasBackendTasks = backendTasks.length > 0
        
        console.log('[Persistence] Init complete:', {
          hasLocalMessages,
          localMessagesCount: localState?.messages?.length || 0,
          hasBackendTasks,
          backendTasksCount: backendTasks.length
        })
        
        setHasRecoverableState(hasLocalMessages || hasBackendTasks)
        
      } catch (e) {
        console.error('Ошибка инициализации persistence:', e)
        setError('Ошибка инициализации системы сохранения')
      } finally {
        setIsLoading(false)
      }
    }
    
    init()
  }, [loadState]) // Запускаем только при монтировании

  // Обновляем hasRecoverableState при изменении activeTasks или persistedState
  useEffect(() => {
    const hasLocalMessages = persistedState && persistedState.messages.length > 0
    const hasBackendTasks = activeTasks.length > 0
    setHasRecoverableState(Boolean(hasLocalMessages || hasBackendTasks))
  }, [activeTasks, persistedState])

  return {
    persistedState,
    activeTasks,
    hasRecoverableState,
    isLoading,
    error,
    saveState,
    loadState,
    clearState,
    fetchActiveTasks,
    resumeTask,
    deleteTask,
    cancelTask
  }
}
