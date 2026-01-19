/**
 * Тесты для проверки корректного обновления сообщений чата
 * 
 * Проблема: При быстрых chat ответах (greeting) сообщение не обновлялось,
 * потому что currentAssistantId сбрасывался в null до получения данных.
 * 
 * Решение: Используем useRef для отслеживания перехода isRunning из true в false,
 * чтобы не сбрасывать currentAssistantId преждевременно.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useState, useEffect, useRef } from 'react'

// Типы для тестов
interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  type: 'text' | 'progress' | 'code' | 'error'
}

interface AgentResults {
  intent?: { type: string }
  greeting_message?: string
  code?: string
}

interface StageStatus {
  result?: { message?: string }
}

/**
 * Хук, воспроизводящий логику обновления сообщений из App.tsx
 */
function useMessageUpdate(
  isRunning: boolean,
  results: AgentResults,
  stages: Record<string, StageStatus>
) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [currentAssistantId, setCurrentAssistantId] = useState<string | null>(null)
  const wasRunningRef = useRef(false)

  // Логика обновления сообщения (из App.tsx)
  useEffect(() => {
    if (!currentAssistantId) return

    const intentType = results.intent?.type || ''
    const isSimpleResponse = intentType === 'greeting' || intentType === 'help' || intentType === 'chat'
    const greetingMessage = stages['greeting']?.result?.message 
      || stages['help']?.result?.message 
      || stages['chat']?.result?.message
      || results.greeting_message

    setMessages(prev => prev.map(msg => {
      if (msg.id !== currentAssistantId) return msg

      if (isSimpleResponse && greetingMessage) {
        return {
          ...msg,
          content: greetingMessage,
          type: 'text' as const,
        }
      }

      return msg
    }))
  }, [stages, results, currentAssistantId])

  // Логика сброса currentAssistantId (ИСПРАВЛЕННАЯ)
  useEffect(() => {
    // Сбрасываем только когда isRunning переходит из true в false
    if (wasRunningRef.current && !isRunning && currentAssistantId) {
      setTimeout(() => setCurrentAssistantId(null), 300)
    }
    wasRunningRef.current = isRunning
  }, [isRunning, currentAssistantId])

  const addAssistantMessage = (id: string) => {
    setMessages(prev => [...prev, {
      id,
      role: 'assistant',
      content: '',
      type: 'progress'
    }])
    setCurrentAssistantId(id)
  }

  return { messages, currentAssistantId, addAssistantMessage, setCurrentAssistantId }
}

describe('Chat Message Update', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  /**
   * Тест 1: currentAssistantId не сбрасывается до начала генерации
   * 
   * Проблема: Раньше useEffect срабатывал при isRunning=false и сразу сбрасывал ID
   * Решение: Проверяем что isRunning было true перед сбросом
   */
  it('should NOT reset currentAssistantId when isRunning starts as false', async () => {
    const { result } = renderHook(
      ({ isRunning, results, stages }) => useMessageUpdate(isRunning, results, stages),
      { initialProps: { isRunning: false, results: {}, stages: {} } }
    )

    // Добавляем сообщение (как при handleSubmit)
    act(() => {
      result.current.addAssistantMessage('test-id-1')
    })

    // currentAssistantId должен быть установлен
    expect(result.current.currentAssistantId).toBe('test-id-1')

    // Ждём потенциальный setTimeout (300ms)
    act(() => {
      vi.advanceTimersByTime(400)
    })

    // currentAssistantId НЕ должен сброситься, потому что isRunning никогда не был true
    expect(result.current.currentAssistantId).toBe('test-id-1')
  })

  /**
   * Тест 2: Сообщение обновляется при получении chat ответа
   * 
   * Проверяем что когда приходит results с intent.type='chat' и greeting_message,
   * сообщение обновляется с type='text' и правильным content
   */
  it('should update message content when chat response arrives', () => {
    const { result, rerender } = renderHook(
      ({ isRunning, results, stages }) => useMessageUpdate(isRunning, results, stages),
      { initialProps: { isRunning: false, results: {} as AgentResults, stages: {} } }
    )

    // Добавляем сообщение
    act(() => {
      result.current.addAssistantMessage('test-id-2')
    })

    // Симулируем начало генерации
    rerender({ isRunning: true, results: {} as AgentResults, stages: {} })

    // Симулируем получение ответа (как при SSE complete event)
    const chatResults: AgentResults = {
      intent: { type: 'chat' },
      greeting_message: 'Привет! Рад помочь.'
    }

    // rerender триггерит useEffect синхронно
    rerender({ isRunning: true, results: chatResults, stages: {} })

    // Сообщение должно обновиться синхронно после rerender
    const assistantMsg = result.current.messages.find(m => m.id === 'test-id-2')
    expect(assistantMsg?.content).toBe('Привет! Рад помочь.')
    expect(assistantMsg?.type).toBe('text')
  })

  /**
   * Тест 3: currentAssistantId сбрасывается после завершения генерации
   * 
   * Проверяем что когда isRunning переходит из true в false,
   * currentAssistantId сбрасывается через 300ms
   */
  it('should reset currentAssistantId after generation completes (isRunning: true -> false)', async () => {
    const { result, rerender } = renderHook(
      ({ isRunning, results, stages }) => useMessageUpdate(isRunning, results, stages),
      { initialProps: { isRunning: false, results: {}, stages: {} } }
    )

    // Добавляем сообщение
    act(() => {
      result.current.addAssistantMessage('test-id-3')
    })

    expect(result.current.currentAssistantId).toBe('test-id-3')

    // Симулируем начало генерации
    rerender({ isRunning: true, results: {}, stages: {} })
    expect(result.current.currentAssistantId).toBe('test-id-3')

    // Симулируем завершение генерации
    rerender({ isRunning: false, results: {}, stages: {} })

    // Сразу после — ID ещё не сброшен (ждёт 300ms)
    expect(result.current.currentAssistantId).toBe('test-id-3')

    // Через 300ms — ID должен сброситься
    act(() => {
      vi.advanceTimersByTime(350)
    })

    expect(result.current.currentAssistantId).toBeNull()
  })

  /**
   * Тест 4: Сообщение обновляется из stages['chat']
   * 
   * Проверяем что сообщение берётся из stages['chat'].result.message
   * когда results.greeting_message ещё не пришёл
   */
  it('should update message from stages[chat].result.message', () => {
    const { result, rerender } = renderHook(
      ({ isRunning, results, stages }) => useMessageUpdate(isRunning, results, stages),
      { initialProps: { isRunning: false, results: {} as AgentResults, stages: {} } }
    )

    // Добавляем сообщение
    act(() => {
      result.current.addAssistantMessage('test-id-4')
    })

    // Симулируем начало генерации
    rerender({ isRunning: true, results: {} as AgentResults, stages: {} })

    // Симулируем получение stage_end для chat (раньше чем complete)
    const chatStages = {
      chat: { result: { message: 'Сообщение из stage' } }
    }
    const partialResults: AgentResults = {
      intent: { type: 'chat' }
    }

    // rerender триггерит useEffect синхронно
    rerender({ isRunning: true, results: partialResults, stages: chatStages })

    // Сообщение должно обновиться из stages синхронно
    const assistantMsg = result.current.messages.find(m => m.id === 'test-id-4')
    expect(assistantMsg?.content).toBe('Сообщение из stage')
    expect(assistantMsg?.type).toBe('text')
  })
})
