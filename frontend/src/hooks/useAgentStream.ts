import { useState, useCallback, useRef, useEffect } from 'react'
import { SSE_EVENTS, AGENT_STAGES } from '../constants/sse'
import { handleSSEError } from '../utils/apiErrorHandler'
import { api } from '../services/apiClient'
import { ValidationResult } from '../types/api'
import { createSSEEventHandler, createSSEEventHandlerWithTime } from '../utils/sseHelpers'

// Простой logger для frontend
// ИСПРАВЛЕНИЕ: Поддерживаем несколько аргументов для логирования (как console.warn/error)
const logger = {
  debug: (...args: unknown[]) => console.debug(...args),
  info: (...args: unknown[]) => console.info(...args),
  warn: (...args: unknown[]) => console.warn(...args),
  error: (...args: unknown[]) => console.error(...args)
}

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

// Состояние рассуждений (thinking) для reasoning моделей
export interface ThinkingState {
  status: 'idle' | 'started' | 'in_progress' | 'completed' | 'interrupted'
  content: string           // Накопленный текст рассуждений
  summary?: string          // Краткая сводка (после завершения)
  elapsedMs: number         // Время рассуждения в мс
  totalChars: number        // Общее количество символов
}

export interface StageStatus {
  stage: string
  status: 'idle' | 'start' | 'progress' | 'end' | 'error'
  message: string
  progress?: number
  result?: StageResult
  error?: string
  // Рассуждения reasoning модели для этого этапа
  thinking?: ThinkingState
  // Время начала этапа для расчета elapsed времени
  startTime?: number
}

// Результат проверки одного инструмента
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

// Phase 7: Under The Hood types
export interface LogEntry {
  timestamp: string
  level: 'debug' | 'info' | 'warning' | 'error'
  stage: string
  message: string
  details?: Record<string, unknown>
}

export interface ToolCall {
  id: string
  type: 'llm' | 'validation' | 'search' | 'file'
  name: string
  input_preview: string
  output_preview?: string
  tokens_in?: number
  tokens_out?: number
  duration_ms: number
  status: 'running' | 'success' | 'error'
}

// Инкрементальный прогресс (Compiler-in-the-Loop)
export interface IncrementalProgress {
  function: string
  status: 'generating' | 'validating' | 'fixing' | 'passed' | 'failed'
  fix_attempts: number
  progress: {
    current: number
    total: number
  }
  error?: string
  timestamp: string
}

// Совет от FastAdvisor
export interface AdvisorSuggestion {
  advice: string
  confidence: number
  priority: 'low' | 'medium' | 'high'
  model_used: string
  response_time_ms: number
  timestamp: string
}

interface UseAgentStreamReturn {
  stages: Record<string, StageStatus>
  results: AgentResults
  metrics: Metrics
  isRunning: boolean
  error: string | null
  // Phase 7: Under The Hood
  logs: LogEntry[]
  toolCalls: ToolCall[]
  // Дополнительные события
  incrementalProgress: IncrementalProgress[]
  advisorSuggestions: AdvisorSuggestion[]
  clearLogs: () => void
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
  const [incrementalProgress, setIncrementalProgress] = useState<IncrementalProgress[]>([])
  const [advisorSuggestions, setAdvisorSuggestions] = useState<AdvisorSuggestion[]>([])
  const [isRunning, setIsRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const eventSourceRef = useRef<EventSource | null>(null)
  const heartbeatTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const lastEventTimeRef = useRef<number>(Date.now())
  const reconnectAttemptsRef = useRef<number>(0)
  
  const HEARTBEAT_INTERVAL = 30000 // 30 секунд
  const MAX_RECONNECT_ATTEMPTS = 5
  const RECONNECT_DELAY = 1000 // 1 секунда
  const isCompletedRef = useRef<boolean>(false)  // Флаг завершения, сохраняется между переподключениями
  
  // Phase 7: Under The Hood
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [toolCalls, setToolCalls] = useState<ToolCall[]>([])
  
  const clearLogs = useCallback(() => {
    setLogs([])
    setToolCalls([])
  }, [])

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
    
    // Очищаем таймауты при старте новой задачи
    if (heartbeatTimeoutRef.current) {
      clearTimeout(heartbeatTimeoutRef.current)
      heartbeatTimeoutRef.current = null
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
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
    
    // ИСПРАВЛЕНИЕ: Добавляем project_path если указан и не пустой (для codebase indexing)
    // Пустая строка не считается валидным путем к проекту
    if (options.projectPath && options.projectPath.trim() !== '') {
      params.set('project_path', options.projectPath.trim())
    }
    
    // Добавляем file_extensions если указаны
    if (options.fileExtensions) {
      params.set('file_extensions', options.fileExtensions)
    }

    // Используем централизованный API клиент для создания SSE соединения
    // ИСПРАВЛЕНИЕ: EventSource создается синхронно и не выбрасывает исключения при создании
    // Ошибки подключения обрабатываются в onerror
    const eventSource = api.stream(params)
    eventSourceRef.current = eventSource
    
    // Сбрасываем счётчик переподключений при успешном подключении
    reconnectAttemptsRef.current = 0
    
    // Обновляем время последнего события
    lastEventTimeRef.current = Date.now()
    
    // Запускаем heartbeat проверку
    const startHeartbeat = () => {
      if (heartbeatTimeoutRef.current) {
        clearTimeout(heartbeatTimeoutRef.current)
      }
      
      heartbeatTimeoutRef.current = setTimeout(() => {
        const timeSinceLastEvent = Date.now() - lastEventTimeRef.current
        if (timeSinceLastEvent > HEARTBEAT_INTERVAL && !isCompletedRef.current) {
          // Нет событий в течение HEARTBEAT_INTERVAL - проверяем соединение
          if (eventSource.readyState === EventSource.OPEN) {
            // ИСПРАВЛЕНИЕ: Увеличиваем интервал предупреждения до 60 секунд
            // Backend теперь отправляет heartbeat каждые 15 секунд, поэтому 30 секунд - это нормально
            if (timeSinceLastEvent > 60000) {
              logger.warn('⚠️ Heartbeat timeout: нет событий в течение 60 секунд')
            }
            // Продолжаем проверку даже если нет событий (workflow может быть долгим)
            startHeartbeat()
          } else if (eventSource.readyState === EventSource.CLOSED) {
            // Соединение закрыто - пытаемся переподключиться
            handleReconnect(task, options)
          }
        } else if (!isCompletedRef.current) {
          // Продолжаем проверку
          startHeartbeat()
        }
      }, HEARTBEAT_INTERVAL)
    }
    
    eventSource.onopen = () => {
      logger.debug('✅ SSE соединение установлено')
      startHeartbeat()
    }

    eventSource.onmessage = (event: MessageEvent) => {
      try {
        if (!event.data || event.data.trim() === '') return
        const data = JSON.parse(event.data)
        
        // ИСПРАВЛЕНИЕ: Обновляем время последнего события для heartbeat
        // Heartbeat события не обрабатываются как обычные события, но обновляют таймер
        lastEventTimeRef.current = Date.now()
        
        // Игнорируем heartbeat события (они только для поддержания соединения)
        if (data.type === 'heartbeat' || event.type === 'heartbeat') {
          return
        }
        
        handleSSEEvent(data)
      } catch (error) {
        // ИСПРАВЛЕНИЕ: Логируем ошибки парсинга для диагностики
        logger.warn('⚠️ Ошибка парсинга SSE события в onmessage:', error, event.data)
      }
    }

    eventSource.addEventListener(SSE_EVENTS.STAGE_START, (event: MessageEvent) => {
      try {
        if (!event.data || event.data.trim() === '') return
        const data = JSON.parse(event.data)
        lastEventTimeRef.current = Date.now() // Обновляем время последнего события
        updateStage(data.stage, {
          stage: data.stage,
          status: 'start',
          message: data.message || '',
          startTime: Date.now() // ИСПРАВЛЕНИЕ: Сохраняем время начала этапа
        })
      } catch (error) {
        // ИСПРАВЛЕНИЕ: Логируем ошибки парсинга для диагностики
        logger.warn('⚠️ Ошибка парсинга STAGE_START:', error, event.data)
      }
    })

    eventSource.addEventListener(SSE_EVENTS.STAGE_PROGRESS, (event: MessageEvent) => {
      try {
        if (!event.data || event.data.trim() === '') return
        const data = JSON.parse(event.data)
        lastEventTimeRef.current = Date.now() // Обновляем время последнего события
        updateStage(data.stage, {
          stage: data.stage,
          status: 'progress',
          message: data.message || '',
          progress: data.progress || 0
        })
      } catch (error) {
        // ИСПРАВЛЕНИЕ: Логируем ошибки парсинга для диагностики
        logger.warn('⚠️ Ошибка парсинга STAGE_PROGRESS:', error, event.data)
      }
    })
    
    // ИСПРАВЛЕНИЕ: Обрабатываем heartbeat события для поддержания соединения
    eventSource.addEventListener('heartbeat', (event: MessageEvent) => {
      try {
        if (!event.data || event.data.trim() === '') return
        // Heartbeat события обновляют таймер, но не обрабатываются как обычные события
        lastEventTimeRef.current = Date.now()
      } catch (error) {
        // ИСПРАВЛЕНИЕ: Логируем ошибки парсинга heartbeat (хотя они редки)
        logger.debug('⚠️ Ошибка парсинга heartbeat:', error)
      }
    })

    eventSource.addEventListener(SSE_EVENTS.STAGE_END, (event: MessageEvent) => {
      try {
        if (!event.data || event.data.trim() === '') return
        const data = JSON.parse(event.data)
        lastEventTimeRef.current = Date.now() // Обновляем время последнего события
        
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
        
        // Определяем статус: error если явно указан, иначе end
        const stageStatus = data.status === 'error' ? 'error' : 'end'
        
        updateStage(data.stage, {
          stage: data.stage,
          status: stageStatus,
          message: data.message || data.error_type || '',
          result: data.result,
          error: data.status === 'error' ? (data.message || data.error_type) : undefined
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
      } catch (error) {
        // ИСПРАВЛЕНИЕ: Логируем ошибки парсинга для диагностики
        logger.warn('⚠️ Ошибка парсинга STAGE_END:', error, event.data)
      }
    })

    // Обработчик стриминга кода (чанки по мере генерации)
    eventSource.addEventListener(SSE_EVENTS.CODE_CHUNK, (event: MessageEvent) => {
      try {
        if (!event.data || event.data.trim() === '') return
        const data = JSON.parse(event.data)
        lastEventTimeRef.current = Date.now() // Обновляем время последнего события
        
        if (data.chunk) {
          setResults(prev => {
            const chunks = prev.codeChunks || []
            const newChunks = [...chunks, data.chunk]
            const assembledCode = newChunks.join('') // Собираем полный код из чанков
            
            // ИСПРАВЛЕНИЕ: Логируем для диагностики если код собирается
            if (assembledCode && assembledCode.length > 0) {
              console.debug(`[CODE_CHUNK] Получен чанк: ${data.chunk.length} символов, всего: ${assembledCode.length} символов`)
            }
            
            return {
              ...prev,
              codeChunks: newChunks,
              code: assembledCode // Собираем полный код из чанков
            }
          })
        }
      } catch (error) {
        // ИСПРАВЛЕНИЕ: Логируем ошибки парсинга для диагностики
        console.error('[CODE_CHUNK] Ошибка парсинга:', error, event.data)
      }
    })

    // Обработчик стриминга плана (чанки по мере генерации)
    eventSource.addEventListener(SSE_EVENTS.PLAN_CHUNK, (event: MessageEvent) => {
      try {
        if (!event.data || event.data.trim() === '') return
        const data = JSON.parse(event.data)
        lastEventTimeRef.current = Date.now() // Обновляем время последнего события
        
        if (data.chunk) {
          setResults(prev => ({
            ...prev,
            plan: (prev.plan || '') + data.chunk
          }))
        }
      } catch (error) {
        // ИСПРАВЛЕНИЕ: Логируем ошибки парсинга для диагностики
        logger.warn('⚠️ Ошибка парсинга PLAN_CHUNK:', error, event.data)
      }
    })

    // Обработчик стриминга тестов (чанки по мере генерации)
    eventSource.addEventListener(SSE_EVENTS.TEST_CHUNK, (event: MessageEvent) => {
      try {
        if (!event.data || event.data.trim() === '') return
        const data = JSON.parse(event.data)
        lastEventTimeRef.current = Date.now() // Обновляем время последнего события
        
        if (data.chunk) {
          setResults(prev => ({
            ...prev,
            tests: (prev.tests || '') + data.chunk
          }))
        }
      } catch (error) {
        // ИСПРАВЛЕНИЕ: Логируем ошибки парсинга для диагностики
        logger.warn('⚠️ Ошибка парсинга TEST_CHUNK:', error, event.data)
      }
    })

    // === Обработчики thinking событий (reasoning модели) ===
    
    // Начало рассуждения
    eventSource.addEventListener(
      SSE_EVENTS.THINKING_STARTED,
      createSSEEventHandler<{ stage: string; total_chars?: number }>(
        (data) => {
          setStages(prev => ({
            ...prev,
            [data.stage]: {
              ...prev[data.stage] || { stage: data.stage, status: 'idle', message: '' },
              thinking: {
                status: 'started',
                content: '',
                elapsedMs: 0,
                totalChars: data.total_chars || 0
              }
            }
          }))
        },
        'THINKING_STARTED',
        ['stage']
      )
    )

    // Чанк рассуждения (стриминг)
    eventSource.addEventListener(
      SSE_EVENTS.THINKING_IN_PROGRESS,
      createSSEEventHandlerWithTime<{ stage: string; content?: string; elapsed_ms?: number; total_chars?: number }>(
        (data) => {
          setStages(prev => {
            const currentStage = prev[data.stage] || { stage: data.stage, status: 'idle', message: '' }
            const currentThinking = currentStage?.thinking
            
            return {
              ...prev,
              [data.stage]: {
                ...currentStage,
                thinking: {
                  status: 'in_progress',
                  content: (currentThinking?.content || '') + (data.content || ''),
                  elapsedMs: data.elapsed_ms || 0,
                  totalChars: data.total_chars || 0
                }
              }
            }
          })
        },
        'THINKING_IN_PROGRESS',
        lastEventTimeRef,
        ['stage']
      )
    )

    // Рассуждение завершено
    eventSource.addEventListener(
      SSE_EVENTS.THINKING_COMPLETED,
      createSSEEventHandler<{ stage: string; content?: string; summary?: string; elapsed_ms?: number; total_chars?: number }>(
        (data) => {
          setStages(prev => {
            const currentStage = prev[data.stage] || { stage: data.stage, status: 'idle', message: '' }
            const currentThinking = currentStage?.thinking
            
            return {
              ...prev,
              [data.stage]: {
                ...currentStage,
                thinking: {
                  status: 'completed',
                  content: data.content || currentThinking?.content || '',
                  summary: data.summary,
                  elapsedMs: data.elapsed_ms || 0,
                  totalChars: data.total_chars || 0
                }
              }
            }
          })
        },
        'THINKING_COMPLETED',
        ['stage']
      )
    )

    // Рассуждение прервано пользователем
    eventSource.addEventListener(
      SSE_EVENTS.THINKING_INTERRUPTED,
      createSSEEventHandler<{ stage: string; elapsed_ms?: number; total_chars?: number }>(
        (data) => {
          setStages(prev => {
            const currentStage = prev[data.stage] || { stage: data.stage, status: 'idle', message: '' }
            const currentThinking = currentStage?.thinking
            
            return {
              ...prev,
              [data.stage]: {
                ...currentStage,
                thinking: {
                  status: 'interrupted',
                  content: currentThinking?.content || '',
                  elapsedMs: data.elapsed_ms || 0,
                  totalChars: data.total_chars || 0
                }
              }
            }
          })
        },
        'THINKING_INTERRUPTED',
        ['stage']
      )
    )

    // === Phase 7: Under The Hood events ===
    
    // Log entry
    eventSource.addEventListener(
      SSE_EVENTS.LOG,
      createSSEEventHandler<LogEntry>(
        (data) => {
          setLogs(prev => {
            const newLogs = [...prev, data]
            // Ограничиваем количество логов в памяти
            if (newLogs.length > 500) {
              return newLogs.slice(-500)
            }
            return newLogs
          })
        },
        'LOG',
        ['stage', 'message']
      )
    )
    
    // Tool call started
    eventSource.addEventListener(
      SSE_EVENTS.TOOL_CALL_START,
      createSSEEventHandler<ToolCall>(
        (data) => {
          setToolCalls(prev => [...prev, data])
        },
        'TOOL_CALL_START',
        ['id', 'type', 'name']
      )
    )
    
    // Tool call ended
    eventSource.addEventListener(
      SSE_EVENTS.TOOL_CALL_END,
      createSSEEventHandler<Partial<ToolCall> & { id: string }>(
        (data) => {
          setToolCalls(prev => prev.map(call => 
            call.id === data.id 
              ? { ...call, ...data } 
              : call
          ))
        },
        'TOOL_CALL_END',
        ['id']
      )
    )

    // Metrics update (real-time метрики)
    eventSource.addEventListener(
      SSE_EVENTS.METRICS_UPDATE,
      createSSEEventHandler<Metrics>(
        (data) => {
          setMetrics(prev => ({
            ...prev,
            ...data
          }))
        },
        'METRICS_UPDATE',
        []
      )
    )

    // Incremental progress (Compiler-in-the-Loop)
    eventSource.addEventListener(
      SSE_EVENTS.INCREMENTAL_PROGRESS,
      createSSEEventHandler<IncrementalProgress>(
        (data) => {
          setIncrementalProgress(prev => {
            const newProgress = [...prev, data]
            // Ограничиваем количество записей в памяти
            if (newProgress.length > 100) {
              return newProgress.slice(-100)
            }
            return newProgress
          })
        },
        'INCREMENTAL_PROGRESS',
        ['function', 'status']
      )
    )

    // Advisor suggestion (FastAdvisor)
    eventSource.addEventListener(
      SSE_EVENTS.ADVISOR_SUGGESTION,
      createSSEEventHandler<AdvisorSuggestion>(
        (data) => {
          setAdvisorSuggestions(prev => {
            const newSuggestions = [...prev, data]
            // Ограничиваем количество советов в памяти
            if (newSuggestions.length > 50) {
              return newSuggestions.slice(-50)
            }
            return newSuggestions
          })
        },
        'ADVISOR_SUGGESTION',
        ['advice', 'confidence']
      )
    )

    // Обработчик кастомного события 'error' от backend (не путать с onerror)
    eventSource.addEventListener(SSE_EVENTS.ERROR, (event: MessageEvent) => {
      try {
        // Проверяем, что это действительно событие с данными от backend
        if (!event.data || event.data.trim() === '') return
        
        const data = JSON.parse(event.data)
        const errorMessage = handleSSEError(data)
        
        updateStage(data.stage || 'unknown', {
          stage: data.stage || 'unknown',
          status: 'error',
          message: errorMessage,
          error: errorMessage
        })
        setError(errorMessage)
        isCompletedRef.current = true
        setIsRunning(false)
        eventSource.close()
        eventSourceRef.current = null
      } catch (e) {
        const errorMessage = handleSSEError(e)
        setError(errorMessage)
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
        
        // ИСПРАВЛЕНИЕ: Если в финальных results есть code, но его нет в codeChunks,
        // используем финальный code из results. Это важно для случаев, когда код
        // был отправлен не через code_chunk, а через финальный complete event.
        setResults(prev => {
          const finalResults = data.results || {}
          const finalCode = finalResults.code || prev.code || ''
          
          // Если есть финальный код, но нет чанков, используем финальный код
          if (finalCode && (!prev.codeChunks || prev.codeChunks.length === 0)) {
            console.debug('[COMPLETE] Используем финальный код из results:', finalCode.length, 'символов')
            return {
              ...prev,
              ...finalResults,
              code: finalCode,
              codeChunks: [finalCode] // Сохраняем как один чанк для консистентности
            }
          }
          
          // Иначе объединяем с существующими results (сохраняет codeChunks из стриминга)
          return {
            ...prev,
            ...finalResults,
            // Сохраняем собранный код из чанков, если он есть
            code: prev.code || finalCode
          }
        })
        
        setMetrics(data.metrics || metrics)
        isCompletedRef.current = true
        setIsRunning(false)
        
        // ИСПРАВЛЕНИЕ: Закрываем соединение с небольшой задержкой, чтобы дать время обработать все события
        // Это предотвращает преждевременное закрытие соединения
        setTimeout(() => {
          if (eventSourceRef.current) {
            eventSourceRef.current.close()
            eventSourceRef.current = null
          }
          // Очищаем heartbeat таймаут
          if (heartbeatTimeoutRef.current) {
            clearTimeout(heartbeatTimeoutRef.current)
            heartbeatTimeoutRef.current = null
          }
        }, 100) // Небольшая задержка для обработки всех событий
      } catch (error) {
        // ИСПРАВЛЕНИЕ: Логируем ошибки парсинга COMPLETE события
        logger.error('❌ Ошибка парсинга COMPLETE события:', error, event.data)
        // Все равно завершаем задачу, чтобы не зависнуть
        isCompletedRef.current = true
        setIsRunning(false)
        if (eventSourceRef.current) {
          eventSourceRef.current.close()
          eventSourceRef.current = null
        }
        if (heartbeatTimeoutRef.current) {
          clearTimeout(heartbeatTimeoutRef.current)
          heartbeatTimeoutRef.current = null
        }
      }
    })

    eventSource.addEventListener(SSE_EVENTS.WARNING, (event: MessageEvent) => {
      try {
        if (!event.data || event.data.trim() === '') return
        const data = JSON.parse(event.data)
        // ИСПРАВЛЕНИЕ: Логируем предупреждения для диагностики
        logger.warn('⚠️ Предупреждение от backend:', data.message || data)
        // Предупреждения от backend обрабатываются тихо
        // При необходимости можно добавить отображение в UI
      } catch (error) {
        // ИСПРАВЛЕНИЕ: Логируем ошибки парсинга предупреждений
        logger.warn('⚠️ Ошибка парсинга WARNING события:', error, event.data)
      }
    })

    const handleReconnect = (task: string, options: TaskOptions) => {
      if (isCompletedRef.current) {
        return
      }
      
      if (reconnectAttemptsRef.current >= MAX_RECONNECT_ATTEMPTS) {
        setError(`Не удалось переподключиться после ${MAX_RECONNECT_ATTEMPTS} попыток`)
        setIsRunning(false)
        isCompletedRef.current = true
        if (eventSourceRef.current) {
          eventSourceRef.current.close()
          eventSourceRef.current = null
        }
        return
      }
      
      reconnectAttemptsRef.current += 1
      logger.info(`🔄 Попытка переподключения ${reconnectAttemptsRef.current}/${MAX_RECONNECT_ATTEMPTS}`)
      
      // Закрываем старое соединение
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
        eventSourceRef.current = null
      }
      
      // Очищаем heartbeat
      if (heartbeatTimeoutRef.current) {
        clearTimeout(heartbeatTimeoutRef.current)
        heartbeatTimeoutRef.current = null
      }
      
      // Пытаемся переподключиться через задержку
      reconnectTimeoutRef.current = setTimeout(() => {
        if (!isCompletedRef.current) {
          _createEventSource(task, options)
        }
      }, RECONNECT_DELAY * reconnectAttemptsRef.current) // Экспоненциальная задержка
    }
    
    eventSource.onerror = (error: Event) => {
      const readyState = eventSource.readyState
      // ИСПРАВЛЕНИЕ: Используем Record для правильной типизации индексации
      const stateNames: Record<number, string> = {
        [EventSource.CONNECTING]: 'CONNECTING',
        [EventSource.OPEN]: 'OPEN',
        [EventSource.CLOSED]: 'CLOSED'
      }
      
      // ИСПРАВЛЕНИЕ: Если задача уже завершена и соединение закрыто - это нормальное завершение
      // Не логируем это как ошибку, только как debug информацию
      if (isCompletedRef.current && readyState === EventSource.CLOSED) {
        logger.debug(
          `✅ SSE соединение закрыто после завершения задачи (readyState=${stateNames[readyState]})`
        )
        if (eventSourceRef.current) {
          eventSourceRef.current.close()
          eventSourceRef.current = null
        }
        if (heartbeatTimeoutRef.current) {
          clearTimeout(heartbeatTimeoutRef.current)
          heartbeatTimeoutRef.current = null
        }
        return
      }
      
      // ИСПРАВЛЕНИЕ: Логируем ошибку только если задача не завершена
      logger.warn(
        `⚠️ SSE ошибка: readyState=${stateNames[readyState] || readyState}, ` +
        `completed=${isCompletedRef.current}, error=`,
        error
      )
      
      // Если задача уже завершена, закрываем соединение
      if (isCompletedRef.current) {
        if (eventSourceRef.current) {
          eventSourceRef.current.close()
          eventSourceRef.current = null
        }
        if (heartbeatTimeoutRef.current) {
          clearTimeout(heartbeatTimeoutRef.current)
          heartbeatTimeoutRef.current = null
        }
        return
      }
      
      // Проверяем состояние подключения
      if (eventSource.readyState === EventSource.CLOSED) {
        // Подключение закрыто во время выполнения задачи - пытаемся переподключиться
        logger.info('🔄 Соединение закрыто, пытаемся переподключиться...')
        handleReconnect(task, options)
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
    // ИСПРАВЛЕНИЕ: Очищаем codeChunks при сбросе, чтобы не было накопления старых чанков
    setStages({})
    setResults({
      codeChunks: [] // ИСПРАВЛЕНИЕ: Явно очищаем чанки при сбросе
    })
    setMetrics({
      planning: 0,
      research: 0,
      testing: 0,
      coding: 0,
      overall: 0
    })
    setError(null)
    isCompletedRef.current = false
    
    // Phase 7: Очищаем логи и tool calls
    setLogs([])
    setToolCalls([])
    
    // Очищаем дополнительные события
    setIncrementalProgress([])
    setAdvisorSuggestions([])
    
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
        eventSourceRef.current = null
      }
      if (heartbeatTimeoutRef.current) {
        clearTimeout(heartbeatTimeoutRef.current)
        heartbeatTimeoutRef.current = null
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
        reconnectTimeoutRef.current = null
      }
    }
  }, [])

  return {
    stages,
    results,
    metrics,
    isRunning,
    error,
    // Phase 7: Under The Hood
    logs,
    toolCalls,
    // Дополнительные события
    incrementalProgress,
    advisorSuggestions,
    clearLogs,
    startTask,
    stopTask,
    reset
  }
}
