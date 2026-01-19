import { useState, useCallback, useRef, useEffect } from 'react'
import { SSE_EVENTS, AGENT_STAGES } from '../constants/sse'

// Результат этапа (stage result) — структура зависит от типа этапа
export interface StageResult {
  message?: string
  success?: boolean
  // Результаты валидации
  pytest_passed?: boolean
  mypy_passed?: boolean
  bandit_passed?: boolean
  // Результаты рефлексии
  planning_score?: number
  research_score?: number
  testing_score?: number
  coding_score?: number
  overall_score?: number
  analysis?: string
  improvements?: string
  should_retry?: boolean
  // Дополнительные данные
  [key: string]: unknown
}

export interface StageStatus {
  stage: string
  status: 'idle' | 'start' | 'progress' | 'end' | 'error'
  message: string
  progress?: number
  result?: StageResult
  error?: string
}

// Результат проверки одного инструмента
export interface ToolValidationResult {
  success: boolean
  output?: string
  errors?: string
  issues?: string
}

// Результат валидации (pytest, mypy, bandit)
export interface ValidationResult {
  success: boolean
  pytest_passed: boolean
  mypy_passed: boolean
  bandit_passed: boolean
  pytest?: ToolValidationResult
  mypy?: ToolValidationResult
  bandit?: ToolValidationResult
  errors?: string[]
}

// Результат рефлексии
export interface ReflectionResult {
  planning_score: number
  research_score: number
  testing_score: number
  coding_score: number
  overall_score: number
  analysis: string
  improvements: string
  should_retry: boolean
}

export interface AgentResults {
  task?: string
  intent?: {
    type: string
    confidence: number
    description: string
  }
  plan?: string
  context?: string
  tests?: string
  code?: string
  codeChunks?: string[] // Чанки кода для стриминга
  validation?: ValidationResult
  reflection?: ReflectionResult
  greeting_message?: string
}

export interface Metrics {
  planning: number
  research: number
  testing: number
  coding: number
  overall: number
}

interface UseAgentStreamReturn {
  stages: Record<string, StageStatus>
  results: AgentResults
  metrics: Metrics
  isRunning: boolean
  error: string | null
  startTask: (task: string, options: TaskOptions) => void
  stopTask: () => void
  reset: () => void
}

export interface TaskOptions {
  model: string
  temperature: number
  disableWebSearch: boolean
  maxIterations: number
  mode: 'auto' | 'chat' | 'code'
  conversationId?: string
  projectPath?: string  // Путь к проекту для индексации кодовой базы
  fileExtensions?: string  // Расширения файлов через запятую, например ".py,.js"
}

export function useAgentStream(): UseAgentStreamReturn {
  const [stages, setStages] = useState<Record<string, StageStatus>>({})
  const [results, setResults] = useState<AgentResults>({})
  const [metrics, setMetrics] = useState<Metrics>({
    planning: 0,
    research: 0,
    testing: 0,
    coding: 0,
    overall: 0
  })
  const [isRunning, setIsRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const eventSourceRef = useRef<EventSource | null>(null)
  const isCompletedRef = useRef<boolean>(false)  // Флаг завершения, сохраняется между переподключениями

  const updateStage = useCallback((stage: string, status: StageStatus) => {
    setStages(prev => ({
      ...prev,
      [stage]: status
    }))
  }, [])

  const startTask = useCallback((task: string, options: TaskOptions) => {
    // Защита: если задача уже выполняется или есть активное соединение, блокируем новый запрос
    if (isRunning) return
    
    if (eventSourceRef.current) {
      const currentState = eventSourceRef.current.readyState
      if (currentState === EventSource.OPEN || currentState === EventSource.CONNECTING) {
        return
      }
      // Если соединение закрыто, закрываем его явно перед созданием нового
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }

    // АДАПТИВНАЯ ЗАДЕРЖКА: ждем завершения предыдущей задачи (если флаг завершения еще не сброшен)
    if (isCompletedRef.current) {
      // Небольшая задержка для гарантии очистки состояния
      setTimeout(() => {
        // Сброс состояния
        setStages({})
        setResults({})
        setMetrics({
          planning: 0,
          research: 0,
          testing: 0,
          coding: 0,
          overall: 0
        })
        setError(null)
        setIsRunning(true)
        isCompletedRef.current = false
        _createEventSource(task, options)
      }, 100)
      return
    }

    // Сброс состояния
    setStages({})
    setResults({})
    setMetrics({
      planning: 0,
      research: 0,
      testing: 0,
      coding: 0,
      overall: 0
    })
    setError(null)
    setIsRunning(true)
    isCompletedRef.current = false  // Сбрасываем флаг завершения для новой задачи
    
    _createEventSource(task, options)
  }, [isRunning, updateStage])

  // Выносим создание EventSource в отдельную функцию для переиспользования
  const _createEventSource = useCallback((task: string, options: TaskOptions) => {

    // Формируем URL для SSE
    const params = new URLSearchParams({
      task,
      mode: options.mode || 'auto',
      model: options.model,
      temperature: options.temperature.toString(),
      disable_web_search: options.disableWebSearch.toString(),
      max_iterations: options.maxIterations.toString()
    })
    
    // Добавляем conversation_id если есть
    if (options.conversationId) {
      params.set('conversation_id', options.conversationId)
    }
    
    // Добавляем project_path если указан (для codebase indexing)
    if (options.projectPath) {
      params.set('project_path', options.projectPath)
    }
    
    // Добавляем file_extensions если указаны
    if (options.fileExtensions) {
      params.set('file_extensions', options.fileExtensions)
    }

    // В dev режиме подключаемся напрямую к backend (Vite proxy не поддерживает SSE)
    // В production можно использовать прокси
    const isDev = typeof window !== 'undefined' && window.location.port === '5173'
    const apiUrl = isDev
      ? `http://localhost:8000/api/stream?${params.toString()}`
      : `/api/stream?${params.toString()}`
    
    const eventSource = new EventSource(apiUrl)
    eventSourceRef.current = eventSource

    eventSource.onmessage = (event: MessageEvent) => {
      try {
        if (!event.data || event.data.trim() === '') return
        const data = JSON.parse(event.data)
        handleSSEEvent(data)
      } catch {
        // Игнорируем ошибки парсинга некорректных SSE событий
      }
    }

    eventSource.addEventListener(SSE_EVENTS.STAGE_START, (event: MessageEvent) => {
      try {
        if (!event.data || event.data.trim() === '') return
        const data = JSON.parse(event.data)
        updateStage(data.stage, {
          stage: data.stage,
          status: 'start',
          message: data.message || ''
        })
      } catch {
        // Игнорируем ошибки парсинга
      }
    })

    eventSource.addEventListener(SSE_EVENTS.STAGE_PROGRESS, (event: MessageEvent) => {
      try {
        if (!event.data || event.data.trim() === '') return
        const data = JSON.parse(event.data)
        updateStage(data.stage, {
          stage: data.stage,
          status: 'progress',
          message: data.message || '',
          progress: data.progress || 0
        })
      } catch {
        // Игнорируем ошибки парсинга
      }
    })

    eventSource.addEventListener(SSE_EVENTS.STAGE_END, (event: MessageEvent) => {
      try {
        if (!event.data || event.data.trim() === '') return
        const data = JSON.parse(event.data)
        
        // Для простых ответов (greeting/help/chat) сохраняем message в results
        const simpleStages = [AGENT_STAGES.GREETING, AGENT_STAGES.HELP, AGENT_STAGES.CHAT]
        if (simpleStages.includes(data.stage)) {
          const messageContent = data.result?.message || data.message
          if (messageContent) {
            setResults(prev => ({
              ...prev,
              greeting_message: messageContent
            }))
          }
        }
        
        updateStage(data.stage, {
          stage: data.stage,
          status: 'end',
          message: data.message || '',
          result: data.result
        })

        // Обновляем код в результатах если пришёл из coding/fixing этапа
        if ((data.stage === AGENT_STAGES.CODING || data.stage === AGENT_STAGES.FIXING) && data.result?.code) {
          setResults(prev => ({
            ...prev,
            code: data.result.code
          }))
        }

        // Обновляем метрики если это этап рефлексии
        if (data.stage === AGENT_STAGES.REFLECTION && data.result) {
          setMetrics({
            planning: data.result.planning_score || 0,
            research: data.result.research_score || 0,
            testing: data.result.testing_score || 0,
            coding: data.result.coding_score || 0,
            overall: data.result.overall_score || 0
          })
        }
      } catch {
        // Игнорируем ошибки парсинга
      }
    })

    // Обработчик стриминга кода (чанки по мере генерации)
    eventSource.addEventListener(SSE_EVENTS.CODE_CHUNK, (event: MessageEvent) => {
      try {
        if (!event.data || event.data.trim() === '') return
        const data = JSON.parse(event.data)
        
        if (data.chunk) {
          setResults(prev => {
            const chunks = prev.codeChunks || []
            const newChunks = [...chunks, data.chunk]
            return {
              ...prev,
              codeChunks: newChunks,
              code: newChunks.join('') // Собираем полный код из чанков
            }
          })
        }
      } catch {
        // Игнорируем ошибки парсинга
      }
    })

    // Обработчик кастомного события 'error' от backend (не путать с onerror)
    eventSource.addEventListener(SSE_EVENTS.ERROR, (event: MessageEvent) => {
      try {
        // Проверяем, что это действительно событие с данными от backend
        if (!event.data || event.data.trim() === '') return
        
        const data = JSON.parse(event.data)
        updateStage(data.stage || 'unknown', {
          stage: data.stage || 'unknown',
          status: 'error',
          message: data.error || 'Ошибка',
          error: data.error
        })
        setError(data.error || 'Произошла ошибка')
        isCompletedRef.current = true
        setIsRunning(false)
        eventSource.close()
        eventSourceRef.current = null
      } catch {
        setError('Ошибка обработки события')
        isCompletedRef.current = true
        setIsRunning(false)
        eventSource.close()
        eventSourceRef.current = null
      }
    })

    eventSource.addEventListener(SSE_EVENTS.COMPLETE, (event: MessageEvent) => {
      try {
        if (!event.data || event.data.trim() === '') {
          isCompletedRef.current = true
          setIsRunning(false)
          if (eventSourceRef.current) {
            eventSourceRef.current.close()
            eventSourceRef.current = null
          }
          return
        }
        const data = JSON.parse(event.data)
        // Объединяем с существующими results (сохраняет greeting_message из stage_end)
        setResults(prev => ({ ...prev, ...(data.results || {}) }))
        setMetrics(data.metrics || metrics)
        isCompletedRef.current = true
        setIsRunning(false)
        if (eventSourceRef.current) {
          eventSourceRef.current.close()
          eventSourceRef.current = null
        }
      } catch {
        isCompletedRef.current = true
        setIsRunning(false)
        if (eventSourceRef.current) {
          eventSourceRef.current.close()
          eventSourceRef.current = null
        }
      }
    })

    eventSource.addEventListener(SSE_EVENTS.WARNING, (event: MessageEvent) => {
      try {
        if (!event.data || event.data.trim() === '') return
        // Предупреждения от backend обрабатываются тихо
        // При необходимости можно добавить отображение в UI
      } catch {
        // Игнорируем ошибки парсинга предупреждений
      }
    })

    eventSource.onerror = () => {
      // Если задача уже завершена, закрываем соединение
      if (isCompletedRef.current) {
        if (eventSourceRef.current) {
          eventSourceRef.current.close()
          eventSourceRef.current = null
        }
        return
      }
      
      // Проверяем состояние подключения
      if (eventSource.readyState === EventSource.CLOSED) {
        // Подключение закрыто во время выполнения задачи
        setTimeout(() => {
          if (!isCompletedRef.current && eventSourceRef.current) {
            setError('Подключение к серверу закрыто. Задача была прервана.')
            setIsRunning(false)
            isCompletedRef.current = true
            eventSourceRef.current.close()
            eventSourceRef.current = null
          }
        }, 100)
      } else if (eventSource.readyState === EventSource.CONNECTING) {
        // Попытка переподключения - предотвращаем если задача завершена
        if (isCompletedRef.current && eventSourceRef.current) {
          eventSourceRef.current.close()
          eventSourceRef.current = null
        }
      } else if (isCompletedRef.current && eventSourceRef.current) {
        // Другие состояния - закрываем если задача завершена
        eventSourceRef.current.close()
        eventSourceRef.current = null
      }
    }
  }, [updateStage, isRunning])

  const handleSSEEvent = (data: Record<string, unknown>) => {
    // Fallback для событий, которые приходят через onmessage
    if (!data || typeof data !== 'object') return
    
    if (data.type === 'stage_start' && data.data) {
      const stageData = data.data as { stage: string; message?: string }
      updateStage(stageData.stage, {
        stage: stageData.stage,
        status: 'start',
        message: stageData.message || ''
      })
    }
  }

  const stopTask = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
    setIsRunning(false)
  }, [])

  const reset = useCallback(() => {
    // Сбрасываем все состояния для новой задачи
    setStages({})
    setResults({})
    setMetrics({
      planning: 0,
      research: 0,
      testing: 0,
      coding: 0,
      overall: 0
    })
    setError(null)
    isCompletedRef.current = false
    
    // Закрываем существующее подключение если есть
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
  }, [])

  // Очистка при размонтировании
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
      }
    }
  }, [])

  return {
    stages,
    results,
    metrics,
    isRunning,
    error,
    startTask,
    stopTask,
    reset
  }
}
