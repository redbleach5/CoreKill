import { useState, useCallback, useRef, useEffect } from 'react'

export interface StageStatus {
  stage: string
  status: 'idle' | 'start' | 'progress' | 'end' | 'error'
  message: string
  progress?: number
  result?: any
  error?: string
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
  validation?: any
  reflection?: {
    planning_score: number
    research_score: number
    testing_score: number
    coding_score: number
    overall_score: number
    analysis: string
    improvements: string
    should_retry: boolean
  }
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
}

interface TaskOptions {
  model: string
  temperature: number
  disableWebSearch: boolean
  maxIterations: number
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
    // Защита от повторных вызовов - если задача уже выполняется, не создаем новое соединение
    if (isRunning || eventSourceRef.current) {
      console.warn('Задача уже выполняется, новый запрос проигнорирован')
      return
    }

    // Останавливаем предыдущее подключение если есть (на всякий случай)
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
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

    // Формируем URL для SSE
    const params = new URLSearchParams({
      task,
      model: options.model,
      temperature: options.temperature.toString(),
      disable_web_search: options.disableWebSearch.toString(),
      max_iterations: options.maxIterations.toString()
    })

    const eventSource = new EventSource(`/api/stream?${params.toString()}`)
    eventSourceRef.current = eventSource

    eventSource.onopen = () => {
      console.log('✅ SSE подключение установлено')
    }

    eventSource.onmessage = (event: MessageEvent) => {
      console.log('📨 Получено сообщение через onmessage:', event.type, event.data?.substring(0, 100))
      try {
        // Проверяем наличие данных перед парсингом
        if (!event.data || event.data.trim() === '') {
          console.warn('Получено пустое сообщение SSE')
          return
        }
        const data = JSON.parse(event.data)
        handleSSEEvent(data)
      } catch (err) {
        console.error('Ошибка парсинга SSE события:', err, event.data)
      }
    }

    eventSource.addEventListener('stage_start', (event: MessageEvent) => {
      try {
        if (!event.data || event.data.trim() === '') {
          console.warn('Получено пустое событие stage_start')
          return
        }
        const data = JSON.parse(event.data)
        updateStage(data.stage, {
          stage: data.stage,
          status: 'start',
          message: data.message || ''
        })
      } catch (err) {
        console.error('Ошибка парсинга stage_start:', err, event.data)
      }
    })

    eventSource.addEventListener('stage_progress', (event: MessageEvent) => {
      try {
        if (!event.data || event.data.trim() === '') {
          console.warn('Получено пустое событие stage_progress')
          return
        }
        const data = JSON.parse(event.data)
        updateStage(data.stage, {
          stage: data.stage,
          status: 'progress',
          message: data.message || '',
          progress: data.progress || 0
        })
      } catch (err) {
        console.error('Ошибка парсинга stage_progress:', err, event.data)
      }
    })

    eventSource.addEventListener('stage_end', (event: MessageEvent) => {
      try {
        if (!event.data || event.data.trim() === '') {
          console.warn('Получено пустое событие stage_end')
          return
        }
        const data = JSON.parse(event.data)
        updateStage(data.stage, {
          stage: data.stage,
          status: 'end',
          message: data.message || '',
          result: data.result
        })

        // Обновляем метрики если это этап рефлексии
        if (data.stage === 'reflection' && data.result) {
          setMetrics({
            planning: data.result.planning_score || 0,
            research: data.result.research_score || 0,
            testing: data.result.testing_score || 0,
            coding: data.result.coding_score || 0,
            overall: data.result.overall_score || 0
          })
        }
      } catch (err) {
        console.error('Ошибка парсинга stage_end:', err, event.data)
      }
    })

    // Обработчик кастомного события 'error' от backend (не путать с onerror)
    eventSource.addEventListener('error', (event: MessageEvent) => {
      try {
        // Проверяем, что это действительно событие с данными от backend
        if (!event.data || event.data.trim() === '') {
          // Пустое событие error может быть от EventSource.onerror, игнорируем
          return
        }
        const data = JSON.parse(event.data)
        updateStage(data.stage || 'unknown', {
          stage: data.stage || 'unknown',
          status: 'error',
          message: data.error || 'Ошибка',
          error: data.error
        })
        setError(data.error || 'Произошла ошибка')
        isCompletedRef.current = true  // Помечаем как завершенную (с ошибкой)
        setIsRunning(false)
        // Закрываем соединение и предотвращаем переподключение
        eventSource.close()
        eventSourceRef.current = null
      } catch (err) {
        console.error('Ошибка парсинга error события:', err, event.data)
        setError('Ошибка обработки события')
        isCompletedRef.current = true
        setIsRunning(false)
        // Закрываем соединение и предотвращаем переподключение
        eventSource.close()
        eventSourceRef.current = null
      }
    })

    eventSource.addEventListener('complete', (event: MessageEvent) => {
      try {
        console.log('✅ Получено событие complete:', event.data)
        if (!event.data || event.data.trim() === '') {
          console.warn('Получено пустое событие complete')
          isCompletedRef.current = true
          setIsRunning(false)
          // Закрываем соединение и предотвращаем переподключение
          if (eventSourceRef.current) {
            eventSourceRef.current.close()
            eventSourceRef.current = null
          }
          return
        }
        const data = JSON.parse(event.data)
        console.log('✅ Парсинг complete успешен:', data)
        setResults(data.results || {})
        setMetrics(data.metrics || metrics)
        isCompletedRef.current = true
        setIsRunning(false)
        // Закрываем соединение и предотвращаем переподключение
        if (eventSourceRef.current) {
          eventSourceRef.current.close()
          eventSourceRef.current = null
        }
      } catch (err) {
        console.error('❌ Ошибка парсинга complete:', err, event.data)
        isCompletedRef.current = true
        setIsRunning(false)
        // Закрываем соединение и предотвращаем переподключение
        if (eventSourceRef.current) {
          eventSourceRef.current.close()
          eventSourceRef.current = null
        }
      }
    })

    eventSource.addEventListener('warning', (event: MessageEvent) => {
      try {
        if (!event.data || event.data.trim() === '') {
          console.warn('Получено пустое событие warning')
          return
        }
        const data = JSON.parse(event.data)
        console.warn('Предупреждение:', data.message || 'Неизвестное предупреждение')
        // Можно добавить отображение предупреждений в UI
      } catch (err) {
        console.error('Ошибка парсинга warning:', err, event.data)
      }
    })

    eventSource.onerror = (err: Event) => {
      // onerror вызывается с Event, а не MessageEvent, поэтому нет event.data
      // Это ошибка подключения, а не ошибка от backend
      
      // Если задача уже завершена, сразу закрываем и предотвращаем переподключение
      if (isCompletedRef.current) {
        console.log('ℹ️ SSE onerror вызван, но задача уже завершена - игнорируем')
        if (eventSourceRef.current) {
          eventSourceRef.current.close()
          eventSourceRef.current = null
        }
        return
      }
      
      // Проверяем состояние подключения
      if (eventSource.readyState === EventSource.CLOSED) {
        // Подключение закрыто - если задача не завершена, это ошибка
        // НО: если поток завершился нормально (после complete), onerror может сработать
        // Поэтому ждем немного перед установкой ошибки
        setTimeout(() => {
          if (!isCompletedRef.current && eventSourceRef.current) {
            console.warn('⚠️ SSE подключение закрыто во время выполнения задачи')
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
          console.log('ℹ️ Предотвращаем переподключение - задача завершена')
          eventSourceRef.current.close()
          eventSourceRef.current = null
        }
      } else if (eventSource.readyState === EventSource.OPEN) {
        // Соединение открыто - ничего не делаем, это нормально
        // onerror может срабатывать даже при открытом соединении (например, при сетевых проблемах)
      } else {
        // Неизвестное состояние - закрываем на всякий случай если задача завершена
        if (isCompletedRef.current && eventSourceRef.current) {
          eventSourceRef.current.close()
          eventSourceRef.current = null
        }
      }
    }
  }, [updateStage, isRunning])

  const handleSSEEvent = (data: any) => {
    // Обработка стандартных SSE событий через data поля
    // Это fallback для событий, которые приходят через onmessage
    if (!data || typeof data !== 'object') {
      console.warn('Получены некорректные данные в handleSSEEvent:', data)
      return
    }
    
    if (data.type === 'stage_start' && data.data) {
      updateStage(data.data.stage, {
        stage: data.data.stage,
        status: 'start',
        message: data.data.message || ''
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
    stopTask
  }
}
