import { useState, useEffect, useRef } from 'react'
import { useAgentStream } from './hooks/useAgentStream'
import { TaskOptions } from './components/SidebarOptions'
import { 
  Zap, Send, Square, Settings, ChevronRight, 
  Brain, ListTodo, Search, TestTube, Code2, Shield, RefreshCw,
  CheckCircle2, Loader2, AlertCircle, Copy, Download, ThumbsUp, ThumbsDown,
  Sparkles, Terminal, FileCode
} from 'lucide-react'

// Конфигурация этапов (включая debug/fixing которые приходят от backend)
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
  greeting: { label: 'Приветствие', icon: Sparkles, description: 'Приветствие' }
}

// Базовые этапы для прогресс-бара (без debug/fixing которые опциональны)
const stageOrder = ['intent', 'planning', 'research', 'testing', 'coding', 'validation', 'reflection']

function App() {
  const { stages, results, metrics, isRunning, error, startTask, stopTask } = useAgentStream()
  const [options, setOptions] = useState<TaskOptions>({
    model: '',
    temperature: 0.25,
    disableWebSearch: false,
    maxIterations: 1
  })

  const [currentTask, setCurrentTask] = useState<string>('')
  const [taskInput, setTaskInput] = useState<string>('')
  const [showSettings, setShowSettings] = useState(false)
  const [copied, setCopied] = useState(false)
  const [availableModels, setAvailableModels] = useState<string[]>([])
  const messagesEndRef = useRef<HTMLDivElement>(null)

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
  }, [stages, results, isRunning])

  const handleStartTask = () => {
    if (taskInput.trim() && !isRunning) {
      const task = taskInput.trim()
      setCurrentTask(task)
      setTaskInput('')
      setCopied(false) // Сбрасываем состояние копирования
      startTask(task, options)
    }
  }

  // Сброс при запуске новой задачи (для возможности отправить новую после завершения)
  const handleNewTask = () => {
    setCurrentTask('')
  }

  const handleCopy = async () => {
    if (results.code) {
      await navigator.clipboard.writeText(results.code)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  const handleDownload = () => {
    if (results.code) {
      const blob = new Blob([results.code], { type: 'text/plain' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'generated_code.py'
      a.click()
      URL.revokeObjectURL(url)
    }
  }

  const handleFeedback = async (feedback: 'positive' | 'negative') => {
    try {
      await fetch('/api/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task: currentTask, feedback })
      })
    } catch (err) {
      console.error('Ошибка отправки feedback:', err)
    }
  }

  const getStageStatus = (stage: string) => {
    const data = stages[stage]
    if (!data || data.status === 'idle') return 'pending'
    if (data.status === 'error') return 'error'
    if (data.status === 'end') return 'completed'
    return 'active'
  }

  const hasStarted = currentTask || Object.keys(stages).length > 0
  const hasCode = !!results.code
  const completedCount = Object.values(stages).filter(s => s.status === 'end').length
  
  // Проверяем есть ли debug/fixing этапы (они опциональны)
  const hasDebugStages = stages['debug'] || stages['fixing']
  
  // Проверяем приветствие
  const isGreeting = results.intent?.type === 'greeting' || stages['greeting']
  
  // Debug логирование (отключено в production)
  // useEffect(() => {
  //   if (process.env.NODE_ENV === 'development') {
  //     console.log('🔍 DEBUG:', { isGreeting, stages: Object.keys(stages) })
  //   }
  // }, [isGreeting, stages])

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-gray-100 flex flex-col">
      {/* Минимальный Header */}
      <header className="flex-shrink-0 border-b border-white/5 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center">
            <Zap className="w-4 h-4 text-white" />
          </div>
          <span className="font-semibold text-white">Cursor Killer</span>
          <span className="text-xs text-gray-500 hidden sm:block">AI Code Agent</span>
        </div>
        
        <div className="flex items-center gap-3">
          {/* Модель */}
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

      {/* Settings Dropdown */}
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

      {/* Main Chat Area */}
      <main className="flex-1 overflow-hidden flex flex-col">
        <div className="flex-1 overflow-y-auto">
          <div className="max-w-3xl mx-auto px-4 py-8">
            
            {/* Welcome State */}
            {!hasStarted && (
              <div className="text-center py-20">
                <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500/20 to-violet-500/20 border border-white/10 mb-6">
                  <Sparkles className="w-8 h-8 text-blue-400" />
                </div>
                <h1 className="text-2xl font-semibold text-white mb-2">Что вы хотите создать?</h1>
                <p className="text-gray-400 max-w-md mx-auto">
                  Опишите задачу, и AI-агент сгенерирует код с тестами и валидацией
                </p>
                
                {/* Quick Actions */}
                <div className="flex flex-wrap justify-center gap-2 mt-8">
                  {[
                    'FastAPI эндпоинт для пользователей',
                    'CLI утилита для работы с файлами',
                    'Парсер JSON с валидацией'
                  ].map((example) => (
                    <button
                      key={example}
                      onClick={() => setTaskInput(example)}
                      className="px-4 py-2 text-sm text-gray-400 bg-white/5 hover:bg-white/10 
                                 border border-white/10 rounded-full transition-colors"
                    >
                      {example}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Task & Progress */}
            {hasStarted && (
              <div className="space-y-6">
                {/* User Message */}
                <div className="flex gap-3">
                  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-emerald-400 to-cyan-500 flex items-center justify-center flex-shrink-0">
                    <span className="text-xs font-medium text-white">Вы</span>
                  </div>
                  <div className="flex-1 pt-1">
                    <p className="text-gray-100">{currentTask}</p>
                  </div>
                </div>

                {/* Agent Response */}
                <div className="flex gap-3">
                  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center flex-shrink-0">
                    <Zap className="w-4 h-4 text-white" />
                  </div>
                  <div className="flex-1 space-y-4">
                    {/* Progress Timeline */}
                    <div className="bg-white/[0.03] rounded-xl border border-white/5 overflow-hidden">
                      {/* Compact Progress Bar */}
                      <div className="px-4 py-3 border-b border-white/5 flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          {isRunning ? (
                            <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />
                          ) : hasCode ? (
                            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                          ) : (
                            <Terminal className="w-4 h-4 text-gray-400" />
                          )}
                          <span className="text-sm text-gray-300">
                            {isRunning ? 'Выполнение...' : hasCode ? 'Готово' : 'Ожидание'}
                          </span>
                        </div>
                        <span className="text-xs text-gray-500">
                          {completedCount}/7 этапов
                        </span>
                      </div>
                      
                      {/* Stages Grid */}
                      <div className="p-4">
                        <div className="flex gap-1">
                          {stageOrder.map((stage) => {
                            const status = getStageStatus(stage)
                            const config = stageConfig[stage]
                            const Icon = config.icon
                            
                            return (
                              <div
                                key={stage}
                                className="flex-1 group relative"
                              >
                                {/* Progress Segment */}
                                <div className={`h-1.5 rounded-full transition-all duration-500 ${
                                  status === 'completed' ? 'bg-emerald-500' :
                                  status === 'active' ? 'bg-blue-500 animate-pulse' :
                                  status === 'error' ? 'bg-red-500' :
                                  'bg-white/10'
                                }`} />
                                
                                {/* Tooltip */}
                                <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 
                                                opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10">
                                  <div className="bg-gray-900 border border-white/10 rounded-lg px-3 py-2 
                                                  text-xs whitespace-nowrap shadow-xl">
                                    <div className="flex items-center gap-2">
                                      <Icon className={`w-3 h-3 ${
                                        status === 'completed' ? 'text-emerald-400' :
                                        status === 'active' ? 'text-blue-400' :
                                        status === 'error' ? 'text-red-400' :
                                        'text-gray-500'
                                      }`} />
                                      <span className="text-gray-200">{config.label}</span>
                                    </div>
                                    <div className="text-gray-500 mt-0.5">{config.description}</div>
                                  </div>
                                </div>
                              </div>
                            )
                          })}
                        </div>
                        
                        {/* Active Stage Info */}
                        {isRunning && (
                          <div className="mt-4 flex items-center gap-2 text-sm">
                            {(() => {
                              const activeStage = stageOrder.find(s => getStageStatus(s) === 'active')
                              if (!activeStage) return null
                              const config = stageConfig[activeStage]
                              const Icon = config.icon
                              return (
                                <>
                                  <Icon className="w-4 h-4 text-blue-400" />
                                  <span className="text-gray-400">{config.description}</span>
                                  <Loader2 className="w-3 h-3 text-blue-400 animate-spin ml-auto" />
                                </>
                              )
                            })()}
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Greeting Response */}
                    {isGreeting && (stages['greeting']?.result?.message || results.greeting_message) && (
                      <div className="p-4 bg-gradient-to-br from-blue-500/10 to-violet-500/10 border border-white/10 rounded-xl">
                        <pre className="text-sm text-gray-300 whitespace-pre-wrap font-sans">
                          {stages['greeting']?.result?.message || results.greeting_message}
                        </pre>
                      </div>
                    )}

                    {/* Debug/Fixing Stages (если были ошибки и исправления) */}
                    {hasDebugStages && !isRunning && (
                      <div className="flex items-center gap-2 px-4 py-2 bg-amber-500/10 border border-amber-500/20 rounded-lg">
                        <AlertCircle className="w-4 h-4 text-amber-400" />
                        <span className="text-sm text-amber-300">
                          Код был исправлен после валидации
                        </span>
                      </div>
                    )}

                    {/* Error */}
                    {error && (
                      <div className="flex items-start gap-3 p-4 bg-red-500/10 border border-red-500/20 rounded-xl">
                        <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
                        <div>
                          <div className="text-sm font-medium text-red-300">Ошибка</div>
                          <div className="text-sm text-red-400/80 mt-1">{error}</div>
                        </div>
                      </div>
                    )}

                    {/* Code Result */}
                    {hasCode && (
                      <div className="bg-white/[0.03] rounded-xl border border-white/5 overflow-hidden">
                        {/* Code Header */}
                        <div className="px-4 py-3 border-b border-white/5 flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <FileCode className="w-4 h-4 text-emerald-400" />
                            <span className="text-sm text-gray-300">generated_code.py</span>
                          </div>
                          <div className="flex items-center gap-1">
                            <button
                              onClick={handleCopy}
                              className="p-1.5 text-gray-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
                              title="Копировать"
                            >
                              {copied ? <CheckCircle2 className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                            </button>
                            <button
                              onClick={handleDownload}
                              className="p-1.5 text-gray-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
                              title="Скачать"
                            >
                              <Download className="w-4 h-4" />
                            </button>
                          </div>
                        </div>
                        
                        {/* Code Content */}
                        <pre className="p-4 text-sm overflow-x-auto max-h-96 overflow-y-auto">
                          <code className="text-gray-300">{results.code}</code>
                        </pre>
                      </div>
                    )}

                    {/* Tests */}
                    {results.tests && (
                      <details className="bg-white/[0.03] rounded-xl border border-white/5 overflow-hidden group">
                        <summary className="px-4 py-3 flex items-center justify-between cursor-pointer hover:bg-white/[0.02]">
                          <div className="flex items-center gap-2">
                            <TestTube className="w-4 h-4 text-violet-400" />
                            <span className="text-sm text-gray-300">Тесты</span>
                          </div>
                          <ChevronRight className="w-4 h-4 text-gray-500 group-open:rotate-90 transition-transform" />
                        </summary>
                        <pre className="p-4 text-sm overflow-x-auto border-t border-white/5 max-h-64 overflow-y-auto">
                          <code className="text-gray-400">{results.tests}</code>
                        </pre>
                      </details>
                    )}

                    {/* Metrics & Actions */}
                    {hasCode && metrics.overall > 0 && (
                      <div className="flex items-center justify-between gap-4 px-4 py-3 bg-white/[0.03] rounded-xl border border-white/5">
                        <div className="flex items-center gap-4">
                          <div className="flex items-center gap-2">
                            <span className="text-xs text-gray-500">Качество:</span>
                            <span className={`text-sm font-medium ${
                              metrics.overall >= 0.8 ? 'text-emerald-400' :
                              metrics.overall >= 0.5 ? 'text-amber-400' :
                              'text-red-400'
                            }`}>
                              {(metrics.overall * 100).toFixed(0)}%
                            </span>
                          </div>
                          
                          <div className="h-4 w-px bg-white/10" />
                          
                          <div className="flex items-center gap-2">
                            <button
                              onClick={() => handleFeedback('positive')}
                              className="p-1.5 text-gray-400 hover:text-emerald-400 hover:bg-emerald-500/10 rounded-lg transition-colors"
                              title="Хорошо"
                            >
                              <ThumbsUp className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => handleFeedback('negative')}
                              className="p-1.5 text-gray-400 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
                              title="Плохо"
                            >
                              <ThumbsDown className="w-4 h-4" />
                            </button>
                          </div>
                        </div>
                        
                        <button
                          onClick={handleNewTask}
                          className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
                        >
                          Новая задача
                        </button>
                      </div>
                    )}

                    {/* Stop Button */}
                    {isRunning && (
                      <button
                        onClick={stopTask}
                        className="flex items-center gap-2 px-4 py-2 text-sm text-gray-400 
                                   hover:text-white bg-white/5 hover:bg-white/10 rounded-lg transition-colors"
                      >
                        <Square className="w-3 h-3" />
                        Остановить
                      </button>
                    )}
                  </div>
                </div>
              </div>
            )}
            
            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Input Area */}
        <div className="flex-shrink-0 border-t border-white/5 bg-[#0a0a0f]/95 backdrop-blur-sm">
          <div className="max-w-3xl mx-auto px-4 py-4">
            <div className={`flex items-center gap-3 bg-white/[0.05] rounded-2xl px-4 py-3 
                            border transition-all duration-200 ${
                              isRunning 
                                ? 'border-blue-500/30' 
                                : 'border-white/10 focus-within:border-white/20'
                            }`}>
              <input
                type="text"
                value={taskInput}
                onChange={(e) => setTaskInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleStartTask()}
                placeholder={isRunning ? 'Выполняется задача...' : 'Опишите задачу...'}
                disabled={isRunning}
                className="flex-1 bg-transparent text-gray-100 placeholder-gray-500 
                           outline-none text-sm disabled:cursor-not-allowed"
              />
              <button
                onClick={handleStartTask}
                disabled={!taskInput.trim() || isRunning}
                className="p-2 bg-blue-500 hover:bg-blue-600 disabled:bg-white/10 
                           disabled:cursor-not-allowed rounded-xl transition-all duration-200
                           hover:shadow-lg hover:shadow-blue-500/25"
              >
                {isRunning ? (
                  <Loader2 className="w-4 h-4 text-white/50 animate-spin" />
                ) : (
                  <Send className="w-4 h-4 text-white" />
                )}
              </button>
            </div>
            <p className="text-xs text-gray-500 text-center mt-2">
              AI может ошибаться. Проверяйте результаты.
            </p>
          </div>
        </div>
      </main>
    </div>
  )
}

export default App
