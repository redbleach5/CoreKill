/**
 * Главный компонент приложения Cursor Killer
 * 
 * Модульная архитектура:
 * - components/chat/ — компоненты чата (MessageList, ChatInput, WelcomeScreen)
 * - components/header/ — компоненты шапки (AppHeader, QuickSettings)
 * - components/ChatHistory — история диалогов (сайдбар)
 * - components/IDEPanel — встроенный редактор кода
 * - hooks/useAgentStream — SSE соединение с backend
 * - hooks/useCodeExecution — выполнение кода
 */
import { useState, useEffect, useRef, useCallback } from 'react'
import { useAgentStream, TaskOptions } from './hooks/useAgentStream'
import { useCodeExecution } from './hooks/useCodeExecution'
import { SettingsPanel } from './components/SettingsPanel'
import { MessageList, ChatInput, WelcomeScreen } from './components/chat'
import { AppHeader, QuickSettings, LayoutMode } from './components/header'
import { ChatHistory } from './components/ChatHistory'
import { IDEPanel } from './components/IDEPanel'
import { ChatMessage, InteractionMode } from './types/chat'

function App() {
  const { stages, results, metrics, isRunning, error, startTask, stopTask, reset } = useAgentStream()
  const { isExecuting, executeCode } = useCodeExecution()
  
  const [options, setOptions] = useState<TaskOptions>({
    model: '',
    temperature: 0.25,
    disableWebSearch: false,
    maxIterations: 3,
    mode: 'auto' as InteractionMode,
    projectPath: '',
    fileExtensions: '.py'
  })
  const [conversationId, setConversationId] = useState<string | null>(null)

  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [taskInput, setTaskInput] = useState<string>('')
  const [showSettings, setShowSettings] = useState(false)
  const [showAdvancedSettings, setShowAdvancedSettings] = useState(false)
  const [availableModels, setAvailableModels] = useState<string[]>([])
  const [currentAssistantId, setCurrentAssistantId] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  // IDE состояние
  const [layoutMode, setLayoutMode] = useState<LayoutMode>('chat')
  const [currentCode, setCurrentCode] = useState('')
  const taskStartTimeRef = useRef<number>(0)
  const previousLayoutRef = useRef<LayoutMode>('chat')
  
  // История чатов
  const [showChatHistory] = useState(true)
  const [chatHistoryCollapsed, setChatHistoryCollapsed] = useState(false)

  // Загрузка доступных моделей
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
      } catch {
        // Игнорируем ошибки загрузки моделей
      }
    }
    fetchModels()
  }, [])

  // Автоскролл к последнему сообщению
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, stages, isRunning])

  // Автопереключение в split режим когда начинается генерация кода
  useEffect(() => {
    if (!isRunning) return
    
    const codingStage = stages['coding']
    const isCodingStarted = codingStage && (codingStage.status === 'start' || codingStage.status === 'progress')
    
    if (isCodingStarted && layoutMode === 'chat') {
      previousLayoutRef.current = layoutMode
      setLayoutMode('split')
    }
  }, [stages, isRunning, layoutMode])

  // Обновляем сообщение ассистента при изменении stages/results
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
          metadata: { intentType }
        }
      }

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

    if (results.code && results.code !== currentCode) {
      setCurrentCode(results.code)
    }
  }, [stages, results, metrics, currentAssistantId, currentCode])

  // Завершение генерации
  const wasRunningRef = useRef(false)
  useEffect(() => {
    if (wasRunningRef.current && !isRunning && currentAssistantId) {
      setTimeout(() => setCurrentAssistantId(null), 300)
    }
    wasRunningRef.current = isRunning
  }, [isRunning, currentAssistantId])

  // Загрузка диалога с сервера
  const loadConversation = useCallback(async (convId: string) => {
    try {
      const response = await fetch(`/api/conversations/${convId}`)
      if (!response.ok) return
      
      const data = await response.json()
      
      // Преобразуем сообщения в формат ChatMessage
      const loadedMessages: ChatMessage[] = data.messages.map((msg: {
        id: string
        role: string
        content: string
        timestamp: string
        metadata?: Record<string, unknown>
      }) => ({
        id: msg.id,
        role: msg.role as 'user' | 'assistant',
        content: msg.content,
        type: msg.role === 'assistant' ? 'text' : 'text',
        timestamp: new Date(msg.timestamp),
        metadata: msg.metadata
      }))
      
      setMessages(loadedMessages)
      setConversationId(convId)
      
      // Если есть код в последнем сообщении, показываем его
      const lastAssistant = loadedMessages.filter((m: ChatMessage) => m.role === 'assistant').pop()
      if (lastAssistant?.metadata?.code) {
        setCurrentCode(lastAssistant.metadata.code as string)
      }
      
    } catch (e) {
      console.error('Ошибка загрузки диалога:', e)
    }
  }, [])

  // Выбор диалога из истории
  const handleSelectConversation = useCallback((convId: string) => {
    if (convId === conversationId) return
    
    // Сбрасываем текущее состояние
    reset()
    setCurrentAssistantId(null)
    
    // Загружаем выбранный диалог
    loadConversation(convId)
  }, [conversationId, reset, loadConversation])

  // Новый диалог
  const handleNewChat = useCallback(() => {
    setMessages([])
    setConversationId(null)
    setCurrentCode('')
    setCurrentAssistantId(null)
    reset()
  }, [reset])

  // Удаление диалога из истории
  const handleDeleteConversation = useCallback((convId: string) => {
    if (convId === conversationId) {
      handleNewChat()
    }
  }, [conversationId, handleNewChat])

  // Отправка сообщения
  const handleSubmit = () => {
    if (!taskInput.trim() || isRunning) return

    taskStartTimeRef.current = Date.now()

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

    // Создаём новый conversation_id если его нет
    const convId = conversationId || `conv-${Date.now()}`
    if (!conversationId) {
      setConversationId(convId)
    }

    reset()
    startTask(taskInput.trim(), { ...options, conversationId: convId })
  }

  // Копирование кода
  const handleCopy = async (code: string) => {
    await navigator.clipboard.writeText(code)
  }

  // Скачивание кода
  const handleDownload = (code: string) => {
    const blob = new Blob([code], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'generated_code.py'
    a.click()
    URL.revokeObjectURL(url)
  }

  // Сохранение расширенных настроек
  const handleAdvancedSettingsSave = (settings: {
    model: string
    temperature: number
    maxIterations: number
    enableWebSearch: boolean
    enableRAG: boolean
    maxTokens: number
    projectPath: string
    fileExtensions: string
  }) => {
    setOptions(prev => ({
      ...prev,
      model: settings.model || prev.model,
      temperature: settings.temperature,
      maxIterations: settings.maxIterations,
      disableWebSearch: !settings.enableWebSearch,
      projectPath: settings.projectPath,
      fileExtensions: settings.fileExtensions
    }))
  }

  // IDE: выполнение кода
  const handleCodeExecute = async (code: string) => {
    const result = await executeCode(code)
    return result
  }

  // IDE: изменение кода
  const handleCodeChange = (code: string) => {
    setCurrentCode(code)
  }

  // Рендер Chat View (только сообщения, без поля ввода)
  const renderChatMessages = () => (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">
        {messages.length === 0 && (
          <WelcomeScreen 
            mode={options.mode as InteractionMode} 
            onSuggestionClick={setTaskInput} 
          />
        )}
        <MessageList
          ref={messagesEndRef}
          messages={messages}
          stages={stages}
          error={error}
          onCopy={handleCopy}
          onDownload={handleDownload}
        />
      </div>
    </div>
  )

  // Рендер поля ввода
  const renderChatInput = () => (
    <div className="flex-shrink-0">
      <ChatInput
        ref={inputRef}
        value={taskInput}
        onChange={setTaskInput}
        onSubmit={handleSubmit}
        onStop={stopTask}
        isRunning={isRunning}
      />
    </div>
  )

  // Рендер IDE View
  const renderIDEView = () => (
    <IDEPanel
      initialCode={currentCode}
      onCodeChange={handleCodeChange}
      onExecute={handleCodeExecute}
      isExecuting={isExecuting}
    />
  )

  // Рендер Split View
  const renderSplitView = () => (
    <div className="flex gap-4 h-full">
      <div className="flex-1 flex flex-col min-w-0">
        {renderChatMessages()}
        {renderChatInput()}
      </div>
      <div className="w-1/2 flex flex-col min-w-0">
        {renderIDEView()}
      </div>
    </div>
  )

  return (
    <div className="h-screen bg-[#0a0a0f] text-gray-100 flex flex-col overflow-hidden">
      {/* Header */}
      <AppHeader
        options={options}
        onOptionsChange={setOptions}
        availableModels={availableModels}
        isRunning={isRunning}
        hasMessages={messages.length > 0}
        showSettings={showSettings}
        onToggleSettings={() => setShowSettings(!showSettings)}
        onNewChat={handleNewChat}
        layoutMode={layoutMode}
        onLayoutChange={setLayoutMode}
      />

      {/* Quick Settings */}
      {showSettings && (
        <QuickSettings
          options={options}
          onOptionsChange={setOptions}
          onAdvancedClick={() => setShowAdvancedSettings(true)}
        />
      )}

      {/* Advanced Settings Modal */}
      <SettingsPanel
        isOpen={showAdvancedSettings}
        onClose={() => setShowAdvancedSettings(false)}
        onSave={handleAdvancedSettingsSave}
        availableModels={availableModels}
      />

      {/* Main Content */}
      <main className="flex-1 overflow-hidden flex min-h-0">
        {/* Chat History Sidebar */}
        {showChatHistory && layoutMode !== 'split' && (
          <ChatHistory
            currentConversationId={conversationId}
            onSelectConversation={handleSelectConversation}
            onNewConversation={handleNewChat}
            onDeleteConversation={handleDeleteConversation}
            isCollapsed={chatHistoryCollapsed}
            onToggleCollapse={() => setChatHistoryCollapsed(!chatHistoryCollapsed)}
          />
        )}

        {/* Main area */}
        <div className="flex-1 min-w-0 flex flex-col">
          {layoutMode === 'chat' && (
            <>
              {renderChatMessages()}
              {renderChatInput()}
            </>
          )}
          {layoutMode === 'ide' && (
            <div className="flex-1 p-4">
              {renderIDEView()}
            </div>
          )}
          {layoutMode === 'split' && (
            <div className="flex-1 p-4">
              {renderSplitView()}
            </div>
          )}
        </div>
      </main>
    </div>
  )
}

export default App
