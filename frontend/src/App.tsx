import { useState, useEffect, useRef } from 'react'
import { useAgentStream } from './hooks/useAgentStream'
import { TaskOptions } from './components/SidebarOptions'
import { 
  Zap, Send, Square, Settings, ChevronRight, 
  Brain, ListTodo, Search, TestTube, Code2, Shield, RefreshCw,
  CheckCircle2, Loader2, AlertCircle, Copy, Download, ThumbsUp, ThumbsDown,
  Sparkles, FileCode, MessageCircle, Bot, User
} from 'lucide-react'

// Типы сообщений в чате
interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  type: 'text' | 'code' | 'progress' | 'error'
  timestamp: Date
  metadata?: {
    intentType?: string
    code?: string
    tests?: string
    stages?: Record<string, any>
    metrics?: any
    quality?: number
  }
}

// Конфигурация этапов
const stageConfig: Record<string, { label: string; icon: typeof Brain; description: string }> = {
  intent: { label: 'Анализ', icon: Brain, description: 'Понимание задачи' },
  planning: { label: 'План', icon: ListTodo, description: 'Разработка плана' },
  research: { label: 'Поиск', icon: Search, description: 'Сбор контекста' },
  testing: { label: 'Тесты', icon: TestTube, description: 'Генерация тестов' },
  coding: { label: 'Код', icon: Code2, description: 'Написание кода' },
  validation: { label: 'Проверка', icon: Shield, description: 'Валидация' },
  debug: { label: 'Отладка', icon: AlertCircle, description: 'Анализ ошибок' },
  fixing: { label: 'Фикс', icon: Code2, description: 'Исправление кода' },
  reflection: { label: 'Оценка', icon: RefreshCw, description: 'Оценка качества' },
  critic: { label: 'Критик', icon: AlertCircle, description: 'Критический анализ' },
  greeting: { label: 'Приветствие', icon: Sparkles, description: 'Приветствие' }
}

const stageOrder = ['intent', 'planning', 'research', 'testing', 'coding', 'validation', 'reflection', 'critic']

function App() {
  const { stages, results, metrics, isRunning, error, startTask, stopTask, reset } = useAgentStream()
  const [options, setOptions] = useState<TaskOptions>({
    model: '',
    temperature: 0.25,
    disableWebSearch: false,
    maxIterations: 3
  })

  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [taskInput, setTaskInput] = useState<string>('')
  const [showSettings, setShowSettings] = useState(false)
  const [availableModels, setAvailableModels] = useState<string[]>([])
  const [currentAssistantId, setCurrentAssistantId] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  // Загрузка моделей
  useEffect(() => {
    const fetchModels = async () => {
      try {
        const response = await fetch('/api/models')
        if (response.ok) {
          const data = await response.json()
          const models = data.models || []
          setAvailableModels(models)
          if (models.length > 0 && !options.model) {
            setOptions(prev => ({ ...prev, model: models[0] }))
          }
        }
      } catch (err) {
        console.error('Ошибка загрузки моделей:', err)
      }
    }
    fetchModels()
  }, [])

  // Автоскролл
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, stages, isRunning])

  // Обновляем сообщение ассистента при изменении stages/results
  useEffect(() => {
    if (!currentAssistantId) return

    const intentType = results.intent?.type || ''
    const isSimpleResponse = intentType === 'greeting' || intentType === 'help'
    const greetingMessage = stages['greeting']?.result?.message || results.greeting_message

    setMessages(prev => prev.map(msg => {
      if (msg.id !== currentAssistantId) return msg

      // Для простых ответов (greeting/help) — просто текст
      if (isSimpleResponse && greetingMessage) {
        return {
          ...msg,
          content: greetingMessage,
          type: 'text' as const,
          metadata: { intentType }
        }
      }

      // Для генерации кода — прогресс и код
      const hasCode = !!results.code

      return {
        ...msg,
        type: hasCode ? 'code' as const : 'progress' as const,
        content: hasCode ? '' : 'Генерация...',
        metadata: {
          intentType,
          code: results.code,
          tests: results.tests,
          stages: stages,
          metrics: metrics,
          quality: metrics?.overall
        }
      }
    }))
  }, [stages, results, metrics, currentAssistantId])

  // Завершение генерации
  useEffect(() => {
    if (!isRunning && currentAssistantId) {
      // Задержка чтобы финальное состояние успело обновиться
      setTimeout(() => setCurrentAssistantId(null), 100)
    }
  }, [isRunning])

  const handleSubmit = () => {
    if (!taskInput.trim() || isRunning) return

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: taskInput.trim(),
      type: 'text',
      timestamp: new Date()
    }

    const assistantId = `assistant-${Date.now()}`
    const assistantMessage: ChatMessage = {
      id: assistantId,
      role: 'assistant',
      content: '',
      type: 'progress',
      timestamp: new Date()
    }

    setMessages(prev => [...prev, userMessage, assistantMessage])
    setCurrentAssistantId(assistantId)
    setTaskInput('')

    // Reset stream state and start
    reset()
    startTask(taskInput.trim(), options)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  const handleCopy = async (code: string) => {
    await navigator.clipboard.writeText(code)
    // Visual feedback handled by button state
  }

  const handleDownload = (code: string) => {
    const blob = new Blob([code], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'generated_code.py'
    a.click()
    URL.revokeObjectURL(url)
  }

  const getStageStatus = (stage: string, stageData: Record<string, any>) => {
    const data = stageData[stage]
    if (!data || data.status === 'idle') return 'pending'
    if (data.status === 'error') return 'error'
    if (data.status === 'end') return 'completed'
    return 'active'
  }

  // Рендер сообщения пользователя
  const renderUserMessage = (msg: ChatMessage) => (
    <div key={msg.id} className="flex gap-3 justify-end">
      <div className="max-w-[80%] bg-gradient-to-br from-blue-600 to-violet-600 rounded-2xl rounded-tr-sm px-4 py-3">
        <p className="text-white whitespace-pre-wrap">{msg.content}</p>
      </div>
      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-500/20 flex items-center justify-center">
        <User className="w-4 h-4 text-blue-400" />
      </div>
    </div>
  )

  // Рендер текстового ответа (greeting/help)
  const renderTextMessage = (msg: ChatMessage) => (
    <div key={msg.id} className="flex gap-3">
      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-br from-emerald-500/20 to-cyan-500/20 flex items-center justify-center">
        <Bot className="w-4 h-4 text-emerald-400" />
      </div>
      <div className="max-w-[80%] bg-white/5 border border-white/10 rounded-2xl rounded-tl-sm px-4 py-3">
        <p className="text-gray-200 whitespace-pre-wrap leading-relaxed">{msg.content}</p>
      </div>
    </div>
  )

  // Рендер прогресса генерации
  const renderProgressMessage = (msg: ChatMessage) => {
    const stageData = msg.metadata?.stages || stages
    const completedCount = Object.values(stageData).filter((s: any) => s.status === 'end').length
    const totalStages = stageOrder.length

    return (
      <div key={msg.id} className="flex gap-3">
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-br from-blue-500/20 to-violet-500/20 flex items-center justify-center">
          <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />
        </div>
        <div className="flex-1 max-w-[85%]">
          <div className="bg-white/5 border border-white/10 rounded-2xl rounded-tl-sm p-4">
            <div className="flex items-center gap-2 mb-3">
              <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />
              <span className="text-sm text-gray-300">Выполнение...</span>
              <span className="text-xs text-gray-500 ml-auto">{completedCount}/{totalStages} этапов</span>
            </div>
            
            {/* Mini progress bar */}
            <div className="flex gap-1">
              {stageOrder.map((stage) => {
                const status = getStageStatus(stage, stageData)
                const config = stageConfig[stage]
                return (
                  <div
                    key={stage}
                    className={`flex-1 h-1.5 rounded-full transition-all duration-300 ${
                      status === 'completed' ? 'bg-emerald-500' :
                      status === 'active' ? 'bg-blue-500 animate-pulse' :
                      status === 'error' ? 'bg-red-500' :
                      'bg-white/10'
                    }`}
                    title={config?.label}
                  />
                )
              })}
            </div>
            
            {/* Current stage */}
            {Object.entries(stageData).map(([name, data]: [string, any]) => {
              if (data.status !== 'start') return null
              const config = stageConfig[name]
              if (!config) return null
              return (
                <div key={name} className="mt-3 flex items-center gap-2 text-sm text-gray-400">
                  <config.icon className="w-4 h-4 text-blue-400" />
                  <span>{config.description}...</span>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    )
  }

  // Рендер сообщения с кодом
  const renderCodeMessage = (msg: ChatMessage) => {
    const code = msg.metadata?.code || ''
    const tests = msg.metadata?.tests || ''
    const quality = msg.metadata?.quality
    const stageData = msg.metadata?.stages || {}
    const hasValidationIssues = stageData['validation']?.result?.success === false

    return (
      <div key={msg.id} className="flex gap-3">
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-br from-emerald-500/20 to-cyan-500/20 flex items-center justify-center">
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
        </div>
        <div className="flex-1 max-w-[90%] space-y-3">
          {/* Status badge */}
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <CheckCircle2 className="w-3 h-3" />
              Готово
            </span>
            {hasValidationIssues && (
              <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
                <AlertCircle className="w-3 h-3" />
                Код был исправлен после валидации
              </span>
            )}
          </div>

          {/* Code block */}
          <div className="bg-[#0d1117] border border-white/10 rounded-xl overflow-hidden">
            <div className="flex items-center justify-between px-4 py-2 bg-white/5 border-b border-white/10">
              <div className="flex items-center gap-2">
                <FileCode className="w-4 h-4 text-gray-400" />
                <span className="text-sm text-gray-400">generated_code.py</span>
              </div>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => handleCopy(code)}
                  className="p-1.5 text-gray-400 hover:text-white hover:bg-white/10 rounded transition-colors"
                  title="Копировать"
                >
                  <Copy className="w-4 h-4" />
                </button>
                <button
                  onClick={() => handleDownload(code)}
                  className="p-1.5 text-gray-400 hover:text-white hover:bg-white/10 rounded transition-colors"
                  title="Скачать"
                >
                  <Download className="w-4 h-4" />
                </button>
              </div>
            </div>
            <pre className="p-4 overflow-x-auto max-h-96">
              <code className="text-sm text-gray-300 font-mono">{code}</code>
            </pre>
          </div>

          {/* Tests (collapsible) */}
          {tests && (
            <details className="group">
              <summary className="flex items-center gap-2 cursor-pointer text-sm text-gray-400 hover:text-white transition-colors">
                <TestTube className="w-4 h-4" />
                <span>Тесты</span>
                <ChevronRight className="w-4 h-4 transition-transform group-open:rotate-90" />
              </summary>
              <div className="mt-2 bg-[#0d1117] border border-white/10 rounded-xl overflow-hidden">
                <pre className="p-4 overflow-x-auto max-h-64">
                  <code className="text-sm text-gray-300 font-mono">{tests}</code>
                </pre>
              </div>
            </details>
          )}

          {/* Quality & Feedback */}
          {quality !== undefined && (
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-sm text-gray-400">Качество:</span>
                <span className={`text-sm font-medium ${
                  quality >= 0.8 ? 'text-emerald-400' :
                  quality >= 0.6 ? 'text-amber-400' :
                  'text-red-400'
                }`}>
                  {Math.round(quality * 100)}%
                </span>
              </div>
              <div className="flex items-center gap-2">
                <button className="p-1.5 text-gray-500 hover:text-emerald-400 hover:bg-emerald-500/10 rounded transition-colors">
                  <ThumbsUp className="w-4 h-4" />
                </button>
                <button className="p-1.5 text-gray-500 hover:text-red-400 hover:bg-red-500/10 rounded transition-colors">
                  <ThumbsDown className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    )
  }

  // Рендер сообщения
  const renderMessage = (msg: ChatMessage) => {
    if (msg.role === 'user') return renderUserMessage(msg)
    
    switch (msg.type) {
      case 'text':
        return renderTextMessage(msg)
      case 'progress':
        return renderProgressMessage(msg)
      case 'code':
        return renderCodeMessage(msg)
      case 'error':
        return (
          <div key={msg.id} className="flex gap-3">
            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-red-500/20 flex items-center justify-center">
              <AlertCircle className="w-4 h-4 text-red-400" />
            </div>
            <div className="bg-red-500/10 border border-red-500/20 rounded-2xl rounded-tl-sm px-4 py-3">
              <p className="text-red-400">{msg.content}</p>
            </div>
          </div>
        )
      default:
        return renderTextMessage(msg)
    }
  }

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-gray-100 flex flex-col">
      {/* Header */}
      <header className="flex-shrink-0 border-b border-white/5 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center">
            <Zap className="w-4 h-4 text-white" />
          </div>
          <span className="font-semibold text-white">Cursor Killer</span>
          <span className="text-xs text-gray-500 hidden sm:block">AI Code Agent</span>
        </div>
        
        <div className="flex items-center gap-3">
          {availableModels.length > 0 && (
            <select
              value={options.model}
              onChange={(e) => setOptions(prev => ({ ...prev, model: e.target.value }))}
              disabled={isRunning}
              className="text-xs bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-gray-300 
                         focus:outline-none focus:border-blue-500/50 disabled:opacity-50"
            >
              {availableModels.map(m => (
                <option key={m} value={m} className="bg-gray-900">{m}</option>
              ))}
            </select>
          )}
          
          <button
            onClick={() => setShowSettings(!showSettings)}
            className={`p-2 rounded-lg transition-colors ${
              showSettings ? 'bg-white/10 text-white' : 'text-gray-400 hover:text-white hover:bg-white/5'
            }`}
          >
            <Settings className="w-4 h-4" />
          </button>
        </div>
      </header>

      {/* Settings */}
      {showSettings && (
        <div className="border-b border-white/5 bg-white/[0.02] px-6 py-4">
          <div className="max-w-2xl mx-auto flex flex-wrap gap-6 text-sm">
            <div className="flex items-center gap-3">
              <label className="text-gray-400">Температура</label>
              <input
                type="range"
                min="0.1"
                max="0.7"
                step="0.05"
                value={options.temperature}
                onChange={(e) => setOptions(prev => ({ ...prev, temperature: parseFloat(e.target.value) }))}
                className="w-24 accent-blue-500"
              />
              <span className="text-gray-300 font-mono w-10">{options.temperature.toFixed(2)}</span>
            </div>
            <div className="flex items-center gap-3">
              <label className="text-gray-400">Итерации</label>
              <input
                type="range"
                min="1"
                max="3"
                value={options.maxIterations}
                onChange={(e) => setOptions(prev => ({ ...prev, maxIterations: parseInt(e.target.value) }))}
                className="w-16 accent-blue-500"
              />
              <span className="text-gray-300 font-mono w-4">{options.maxIterations}</span>
            </div>
            <label className="flex items-center gap-2 text-gray-400 cursor-pointer">
              <input
                type="checkbox"
                checked={options.disableWebSearch}
                onChange={(e) => setOptions(prev => ({ ...prev, disableWebSearch: e.target.checked }))}
                className="accent-blue-500"
              />
              Без веб-поиска
            </label>
          </div>
        </div>
      )}

      {/* Chat Area */}
      <main className="flex-1 overflow-hidden flex flex-col">
        <div className="flex-1 overflow-y-auto">
          <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">
            
            {/* Welcome State */}
            {messages.length === 0 && (
              <div className="text-center py-16">
                <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500/20 to-violet-500/20 border border-white/10 mb-6">
                  <MessageCircle className="w-8 h-8 text-blue-400" />
                </div>
                <h1 className="text-2xl font-semibold text-white mb-2">Чем могу помочь?</h1>
                <p className="text-gray-400 max-w-md mx-auto mb-8">
                  Опишите задачу — я сгенерирую код, помогу с отладкой или отвечу на вопросы
                </p>
                
                {/* Quick suggestions */}
                <div className="flex flex-wrap justify-center gap-2">
                  {[
                    '👋 Привет! Что ты умеешь?',
                    '📝 Напиши функцию сортировки',
                    '🔧 Создай REST API эндпоинт',
                    '🧪 Напиши тесты для калькулятора'
                  ].map((example) => (
                    <button
                      key={example}
                      onClick={() => setTaskInput(example.replace(/^[^\s]+\s/, ''))}
                      className="px-4 py-2 text-sm text-gray-400 bg-white/5 hover:bg-white/10 
                                 border border-white/10 rounded-full transition-colors"
                    >
                      {example}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Messages */}
            {messages.map(renderMessage)}
            
            {/* Error */}
            {error && (
              <div className="flex gap-3">
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-red-500/20 flex items-center justify-center">
                  <AlertCircle className="w-4 h-4 text-red-400" />
                </div>
                <div className="bg-red-500/10 border border-red-500/20 rounded-2xl rounded-tl-sm px-4 py-3">
                  <p className="text-red-400">{error}</p>
                </div>
              </div>
            )}
            
            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Input Area */}
        <div className="flex-shrink-0 border-t border-white/5 bg-[#0a0a0f]/80 backdrop-blur-xl p-4">
          <div className="max-w-3xl mx-auto">
            <div className="relative">
              <textarea
                ref={inputRef}
                value={taskInput}
                onChange={(e) => setTaskInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Опишите задачу..."
                rows={1}
                disabled={isRunning}
                className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 pr-24
                           text-white placeholder-gray-500 resize-none
                           focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/25
                           disabled:opacity-50 disabled:cursor-not-allowed
                           min-h-[48px] max-h-32"
                style={{ height: 'auto' }}
                onInput={(e) => {
                  const target = e.target as HTMLTextAreaElement
                  target.style.height = 'auto'
                  target.style.height = Math.min(target.scrollHeight, 128) + 'px'
                }}
              />
              
              <div className="absolute right-2 bottom-2 flex items-center gap-1">
                {isRunning ? (
                  <button
                    onClick={stopTask}
                    className="p-2 rounded-lg bg-red-500/20 text-red-400 hover:bg-red-500/30 transition-colors"
                  >
                    <Square className="w-4 h-4" />
                  </button>
                ) : (
                  <button
                    onClick={handleSubmit}
                    disabled={!taskInput.trim()}
                    className="p-2 rounded-lg bg-blue-500 text-white hover:bg-blue-600 
                               disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    <Send className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>
            
            <p className="text-center text-xs text-gray-500 mt-2">
              AI может ошибаться. Проверяйте результаты.
            </p>
          </div>
        </div>
      </main>
    </div>
  )
}

export default App
