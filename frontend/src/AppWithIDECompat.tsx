/**
 * Совместимая версия AppWithIDE
 * Интегрируется с существующей архитектурой проекта
 * Использует существующие компоненты где возможно
 */
import { useState, useRef, useEffect } from 'react'
import { useAgentStream, TaskOptions } from './hooks/useAgentStream'
import { useCodeExecution } from './hooks/useCodeExecution'
import { IDEPanel } from './components/IDEPanel'
import { EnhancedSettingsPanel } from './components/EnhancedSettingsPanel'
import { AgentProgress } from './components/AgentProgress'
import { TaskHistory } from './components/TaskHistory'
import { EnhancedResultDisplay } from './components/EnhancedResultDisplay'
import {
  Zap, Send, Square, Settings, Code2, MessageCircle, Plus, Maximize2, Minimize2,
  Copy, Download, FileCode, Bot, User, AlertCircle, CheckCircle2, Loader2
} from 'lucide-react'

type LayoutMode = 'chat' | 'ide' | 'split'

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  type: 'text' | 'code' | 'progress' | 'error'
  timestamp: Date
  metadata?: Record<string, any>
}

interface Task {
  id: string
  title: string
  description: string
  status: 'completed' | 'failed' | 'pending'
  timestamp: Date
  duration: number
  quality?: number
  code?: string
}

/**
 * AppWithIDECompat - Совместимая версия приложения с IDE
 * Полностью интегрируется с существующей архитектурой
 */
function AppWithIDECompat() {
  const { stages, results, metrics, isRunning, error, startTask, stopTask, reset } = useAgentStream()
  const { isExecuting, executeCode } = useCodeExecution()

  const [layoutMode, setLayoutMode] = useState<LayoutMode>('split')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [taskInput, setTaskInput] = useState('')
  const [showSettings, setShowSettings] = useState(false)
  const [availableModels, setAvailableModels] = useState<string[]>([])
  const [currentCode, setCurrentCode] = useState('')
  const [taskHistory, setTaskHistory] = useState<Task[]>([])
  const [options, setOptions] = useState<TaskOptions>({
    model: '',
    temperature: 0.25,
    disableWebSearch: false,
    maxIterations: 3,
    mode: 'auto'
  })

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

  // Сохранение задачи в историю при завершении
  useEffect(() => {
    if (!isRunning && results && results.code) {
      const newTask: Task = {
        id: `task-${Date.now()}`,
        title: messages[messages.length - 2]?.content.substring(0, 50) || 'Задача',
        description: messages[messages.length - 2]?.content || '',
        status: error ? 'failed' : 'completed',
        timestamp: new Date(),
        duration: metrics?.totalTime || 0,
        quality: metrics?.quality || 0.8,
        code: results.code
      }
      setTaskHistory(prev => [newTask, ...prev])
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

    const assistantMessage: ChatMessage = {
      id: `assistant-${Date.now()}`,
      role: 'assistant',
      content: '',
      type: 'progress',
      timestamp: new Date()
    }

    setMessages(prev => [...prev, userMessage, assistantMessage])
    setTaskInput('')
    reset()
    startTask(taskInput.trim(), options)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  const handleCodeExecute = async (code: string) => {
    setCurrentCode(code)
    try {
      const result = await executeCode(code)
      return result
    } catch (err) {
      throw err
    }
  }

  const handleCodeChange = (code: string) => {
    setCurrentCode(code)
  }

  const handleTaskSelect = (task: Task) => {
    if (task.code) {
      setCurrentCode(task.code)
      setLayoutMode('ide')
    }
  }

  const handleTaskDelete = (taskId: string) => {
    setTaskHistory(prev => prev.filter(t => t.id !== taskId))
  }

  // Chat View
  const renderChatView = () => (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex items-center justify-center h-full text-gray-500">
            <div className="text-center">
              <Zap className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p>Начните диалог с системой генерации кода</p>
            </div>
          </div>
        )}
        {messages.map(msg => (
          <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            {msg.role === 'assistant' && (
              <div className="w-8 h-8 rounded-full bg-blue-500/20 flex items-center justify-center flex-shrink-0 mr-3">
                <Bot className="w-4 h-4 text-blue-400" />
              </div>
            )}
            <div className={`max-w-[70%] rounded-lg px-4 py-2 ${
              msg.role === 'user'
                ? 'bg-blue-600 text-white'
                : 'bg-white/10 text-gray-200'
            }`}>
              {msg.type === 'progress' ? (
                <AgentProgress stages={stages} />
              ) : (
                <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
              )}
            </div>
            {msg.role === 'user' && (
              <div className="w-8 h-8 rounded-full bg-blue-500/20 flex items-center justify-center flex-shrink-0 ml-3">
                <User className="w-4 h-4 text-blue-400" />
              </div>
            )}
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="flex-shrink-0 border-t border-white/10 p-4">
        <div className="flex gap-2">
          <textarea
            ref={inputRef}
            value={taskInput}
            onChange={(e) => setTaskInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Опишите задачу..."
            className="flex-1 px-4 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-blue-500/50 resize-none max-h-24"
            rows={3}
          />
          <button
            onClick={handleSubmit}
            disabled={isRunning || !taskInput.trim()}
            className="flex-shrink-0 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isRunning ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          </button>
        </div>
      </div>
    </div>
  )

  // IDE View
  const renderIDEView = () => (
    <IDEPanel
      initialCode={currentCode}
      onCodeChange={handleCodeChange}
      onExecute={handleCodeExecute}
      isExecuting={isExecuting}
    />
  )

  // Split View
  const renderSplitView = () => (
    <div className="flex gap-4 h-full">
      <div className="flex-1 flex flex-col min-w-0">
        {renderChatView()}
      </div>
      <div className="w-1/2 flex flex-col min-w-0">
        {renderIDEView()}
      </div>
    </div>
  )

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-gray-100 flex flex-col">
      {/* Header */}
      <header className="flex-shrink-0 border-b border-white/5 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center">
            <Zap className="w-4 h-4 text-white" />
          </div>
          <span className="font-semibold text-white">Cursor Killer IDE</span>
        </div>

        <div className="flex items-center gap-2">
          {/* Layout toggle */}
          <div className="flex items-center gap-1 bg-white/5 rounded-lg p-1">
            <button
              onClick={() => setLayoutMode('chat')}
              className={`px-3 py-1.5 text-sm rounded transition-colors ${
                layoutMode === 'chat'
                  ? 'bg-blue-500/20 text-blue-400'
                  : 'text-gray-400 hover:text-gray-300'
              }`}
              title="Chat режим"
            >
              <MessageCircle className="w-4 h-4" />
            </button>
            <button
              onClick={() => setLayoutMode('ide')}
              className={`px-3 py-1.5 text-sm rounded transition-colors ${
                layoutMode === 'ide'
                  ? 'bg-blue-500/20 text-blue-400'
                  : 'text-gray-400 hover:text-gray-300'
              }`}
              title="IDE режим"
            >
              <Code2 className="w-4 h-4" />
            </button>
            <button
              onClick={() => setLayoutMode('split')}
              className={`px-3 py-1.5 text-sm rounded transition-colors ${
                layoutMode === 'split'
                  ? 'bg-blue-500/20 text-blue-400'
                  : 'text-gray-400 hover:text-gray-300'
              }`}
              title="Split режим"
            >
              <Maximize2 className="w-4 h-4" />
            </button>
          </div>

          {/* Settings */}
          <button
            onClick={() => setShowSettings(!showSettings)}
            className="p-2 text-gray-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
            title="Настройки"
          >
            <Settings className="w-4 h-4" />
          </button>
        </div>
      </header>

      {/* Main content */}
      <div className="flex-1 overflow-hidden p-4 flex gap-4">
        {/* Main area */}
        <div className="flex-1 min-w-0">
          {layoutMode === 'chat' && renderChatView()}
          {layoutMode === 'ide' && renderIDEView()}
          {layoutMode === 'split' && renderSplitView()}
        </div>

        {/* Sidebar with history */}
        {layoutMode !== 'split' && (
          <div className="w-80 flex-shrink-0">
            <TaskHistory
              tasks={taskHistory}
              onTaskSelect={handleTaskSelect}
              onTaskDelete={handleTaskDelete}
            />
          </div>
        )}
      </div>

      {/* Settings panel */}
      {showSettings && (
        <EnhancedSettingsPanel
          onClose={() => setShowSettings(false)}
          availableModels={availableModels}
          currentSettings={options}
          onSettingsChange={setOptions}
        />
      )}
    </div>
  )
}

export default AppWithIDECompat
