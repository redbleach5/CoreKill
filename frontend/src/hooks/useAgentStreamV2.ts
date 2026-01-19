"""Хук для стриминга событий от агента."""
import { useCallback } from 'react'

interface SSEEvent {
  id: string
  event: string
  data: Record<string, any>
  timestamp: string
}

interface StageStartEvent extends SSEEvent {
  event: 'stage_start'
  data: {
    stage: string
    status: string
    message: string
    metadata?: Record<string, any>
  }
}

interface StageEndEvent extends SSEEvent {
  event: 'stage_end'
  data: {
    stage: string
    status: string
    message: string
    result?: Record<string, any>
  }
}

interface FinalResultEvent extends SSEEvent {
  event: 'final_result'
  data: {
    task_id: string
    results: Record<string, any>
    metrics: Record<string, number>
  }
}

interface ErrorEvent extends SSEEvent {
  event: 'error'
  data: {
    stage: string
    error_message: string
    error_details?: Record<string, any>
  }
}

type AgentEvent = StageStartEvent | StageEndEvent | FinalResultEvent | ErrorEvent

export const useAgentStream = () => {
  const stream = useCallback(
    async function* (task: string) {
      try {
        const response = await fetch('/api/agent/stream', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ task }),
        })

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`)
        }

        const reader = response.body?.getReader()
        if (!reader) {
          throw new Error('Response body is not readable')
        }

        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')

          // Обрабатываем полные события
          for (let i = 0; i < lines.length - 1; i++) {
            const line = lines[i].trim()

            if (line.startsWith('data: ')) {
              try {
                const jsonStr = line.slice(6)
                const data = JSON.parse(jsonStr)

                // Определяем тип события
                if (data.stage) {
                  if (data.status === 'start') {
                    yield {
                      type: 'stage_start',
                      stage: data.stage,
                      message: data.message,
                      metadata: data.metadata,
                    }
                  } else if (data.status === 'end') {
                    yield {
                      type: 'stage_end',
                      stage: data.stage,
                      message: data.message,
                      result: data.result,
                    }
                  }
                } else if (data.task_id) {
                  yield {
                    type: 'final_result',
                    results: data.results,
                    metrics: data.metrics,
                  }
                } else if (data.error_message) {
                  yield {
                    type: 'error',
                    stage: data.stage,
                    error: data.error_message,
                    details: data.error_details,
                  }
                }
              } catch (e) {
                console.error('Ошибка при парсинге JSON:', e)
              }
            }
          }

          // Сохраняем неполную строку в буфер
          buffer = lines[lines.length - 1]
        }

        // Обрабатываем остаток буфера
        if (buffer.trim().startsWith('data: ')) {
          try {
            const jsonStr = buffer.trim().slice(6)
            const data = JSON.parse(jsonStr)
            if (data.task_id) {
              yield {
                type: 'final_result',
                results: data.results,
                metrics: data.metrics,
              }
            }
          } catch (e) {
            console.error('Ошибка при парсинге финального JSON:', e)
          }
        }
      } catch (error) {
        console.error('Ошибка при стриминге:', error)
        yield {
          type: 'error',
          stage: 'stream',
          error: error instanceof Error ? error.message : 'Неизвестная ошибка',
        }
      }
    },
    []
  )

  return { stream }
}
