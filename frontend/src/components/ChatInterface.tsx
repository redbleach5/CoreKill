"""Улучшенный интерфейс чата."""
import React, { useRef, useEffect, useState } from 'react'
import { Send, Settings, Copy, Download, AlertCircle, CheckCircle2 } from 'lucide-react'
import { useAgentStream } from '../hooks/useAgentStream'

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  metadata?: Record<string, any>
  timestamp: number
}

interface ChatInterfaceProps {
  onSettingsClick?: () => void
}

export const ChatInterface: React.FC<ChatInterfaceProps> = ({ onSettingsClick }) => {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const { stream } = useAgentStream()

  // Автоскролл к последнему сообщению
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!input.trim() || isLoading) return

    // Добавляем сообщение пользователя
    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: input,
      timestamp: Date.now()
    }

    setMessages(prev => [...prev, userMessage])
    setInput('')
    setIsLoading(true)

    try {
      // Стримим ответ от агента
      const assistantMessage: ChatMessage = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: '',
        metadata: {},
        timestamp: Date.now()
      }

      setMessages(prev => [...prev, assistantMessage])

      for await (const event of stream(input)) {
        if (event.type === 'stage_start') {
          // Обновляем метаданные этапа
          setMessages(prev => {
            const updated = [...prev]
            const lastMsg = updated[updated.length - 1]
            if (lastMsg.role === 'assistant') {
              lastMsg.metadata = {
                ...lastMsg.metadata,
                [event.stage]: { status: 'start', message: event.message }
              }
            }
            return updated
          })
        } else if (event.type === 'stage_end') {
          // Обновляем результат этапа
          setMessages(prev => {
            const updated = [...prev]
            const lastMsg = updated[updated.length - 1]
            if (lastMsg.role === 'assistant') {
              lastMsg.metadata = {
                ...lastMsg.metadata,
                [event.stage]: { status: 'end', result: event.result }
              }
            }
            return updated
          })
        } else if (event.type === 'final_result') {
          // Обновляем финальный результат
          setMessages(prev => {
            const updated = [...prev]
            const lastMsg = updated[updated.length - 1]
            if (lastMsg.role === 'assistant') {
              lastMsg.content = event.results.code || ''
              lastMsg.metadata = event.results
            }
            return updated
          })
        }
      }
    } catch (error) {
      console.error('Ошибка при отправке сообщения:', error)
      // Добавляем сообщение об ошибке
      setMessages(prev => [...prev, {
        id: `error-${Date.now()}`,
        role: 'assistant',
        content: 'Произошла ошибка при обработке запроса. Пожалуйста, попробуйте ещё раз.',
        timestamp: Date.now()
      }])
    } finally {
      setIsLoading(false)
    }
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
  }

  const downloadCode = (code: string, filename: string = 'code.py') => {
    const element = document.createElement('a')
    element.setAttribute('href', 'data:text/plain;charset=utf-8,' + encodeURIComponent(code))
    element.setAttribute('download', filename)
    element.style.display = 'none'
    document.body.appendChild(element)
    element.click()
    document.body.removeChild(element)
  }

  return (
    <div className="flex flex-col h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-white/10 bg-black/20 backdrop-blur-sm">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center">
            <span className="text-white font-bold text-lg">CK</span>
          </div>
          <div>
            <h1 className="text-lg font-semibold text-white">Cursor Killer</h1>
            <p className="text-xs text-gray-400">Локальная система генерации кода</p>
          </div>
        </div>
        <button
          onClick={onSettingsClick}
          className="p-2 hover:bg-white/10 rounded-lg transition-colors"
          title="Настройки"
        >
          <Settings className="w-5 h-5 text-gray-300" />
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="text-4xl mb-4">👋</div>
            <h2 className="text-xl font-semibold text-white mb-2">Добро пожаловать!</h2>
            <p className="text-gray-400 max-w-md">
              Я помогу вам создавать, изменять и оптимизировать код. Просто опишите, что вам нужно!
            </p>
          </div>
        )}

        {messages.map(msg => (
          <div key={msg.id} className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            {msg.role === 'assistant' && (
              <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-br from-emerald-500/20 to-cyan-500/20 flex items-center justify-center">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              </div>
            )}

            <div className={`max-w-[70%] ${msg.role === 'user' ? 'bg-blue-600/20 border border-blue-500/30' : 'bg-white/5 border border-white/10'} rounded-2xl px-4 py-3`}>
              {msg.content && (
                <div className="text-gray-200 whitespace-pre-wrap">
                  {msg.content}
                </div>
              )}

              {msg.metadata?.code && (
                <div className="mt-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-400">Сгенерированный код</span>
                    <div className="flex gap-2">
                      <button
                        onClick={() => copyToClipboard(msg.metadata.code)}
                        className="p-1 hover:bg-white/10 rounded transition-colors"
                        title="Копировать"
                      >
                        <Copy className="w-4 h-4 text-gray-400" />
                      </button>
                      <button
                        onClick={() => downloadCode(msg.metadata.code)}
                        className="p-1 hover:bg-white/10 rounded transition-colors"
                        title="Скачать"
                      >
                        <Download className="w-4 h-4 text-gray-400" />
                      </button>
                    </div>
                  </div>
                  <pre className="bg-black/40 rounded p-3 text-xs text-gray-300 overflow-x-auto max-h-96">
                    <code>{msg.metadata.code}</code>
                  </pre>
                </div>
              )}

              {msg.metadata?.error && (
                <div className="mt-3 flex gap-2 p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
                  <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-red-300">{msg.metadata.error}</p>
                </div>
              )}
            </div>

            {msg.role === 'user' && (
              <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-600/20 flex items-center justify-center">
                <span className="text-xs text-blue-300">👤</span>
              </div>
            )}
          </div>
        ))}

        {isLoading && (
          <div className="flex gap-3">
            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-br from-blue-500/20 to-violet-500/20 flex items-center justify-center">
              <div className="w-4 h-4 rounded-full border-2 border-blue-400 border-t-transparent animate-spin" />
            </div>
            <div className="bg-white/5 border border-white/10 rounded-2xl px-4 py-3">
              <p className="text-gray-400 text-sm">Обработка запроса...</p>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t border-white/10 bg-black/20 backdrop-blur-sm p-4">
        <form onSubmit={handleSendMessage} className="flex gap-3">
          <input
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder="Опишите задачу..."
            disabled={isLoading}
            className="flex-1 bg-white/10 border border-white/20 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 focus:bg-white/15 transition-colors disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white rounded-lg px-4 py-3 transition-colors flex items-center gap-2"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
      </div>
    </div>
  )
}
