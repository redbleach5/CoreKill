/**
 * Компонент списка сообщений чата
 * 
 * Поддерживает рендеринг markdown с красивыми стилями.
 */
import { forwardRef, useMemo, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { 
  CheckCircle2, Loader2, AlertCircle, Copy, Download, 
  ThumbsUp, ThumbsDown, FileCode, Bot, User, TestTube, ChevronRight,
  Sparkles, Search, FlaskConical, Code2, ShieldCheck, Brain, MessageSquare,
  ExternalLink
} from 'lucide-react'
import { ChatMessage } from '../../types/chat'
import { StageStatus } from '../../hooks/useAgentStream'

interface MessageListProps {
  messages: ChatMessage[]
  stages: Record<string, StageStatus>
  error: string | null
  onCopy: (code: string) => void
  onDownload: (code: string) => void
}

// Рендер сообщения пользователя
function UserMessage({ msg }: { msg: ChatMessage }) {
  return (
    <div key={msg.id} className="flex gap-3 justify-end">
      <div className="max-w-[80%] bg-gradient-to-br from-blue-600 to-violet-600 rounded-2xl rounded-tr-sm px-4 py-3">
        <p className="text-white whitespace-pre-wrap">{msg.content}</p>
      </div>
      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-500/20 flex items-center justify-center">
        <User className="w-4 h-4 text-blue-400" />
      </div>
    </div>
  )
}

// Компоненты для рендеринга markdown
const markdownComponents = {
  // Параграфы
  p: ({ children }: { children?: React.ReactNode }) => (
    <p className="mb-3 last:mb-0 leading-relaxed">{children}</p>
  ),
  // Заголовки
  h1: ({ children }: { children?: React.ReactNode }) => (
    <h1 className="text-xl font-bold text-white mb-3 mt-4 first:mt-0">{children}</h1>
  ),
  h2: ({ children }: { children?: React.ReactNode }) => (
    <h2 className="text-lg font-semibold text-white mb-2 mt-3 first:mt-0">{children}</h2>
  ),
  h3: ({ children }: { children?: React.ReactNode }) => (
    <h3 className="text-base font-semibold text-gray-100 mb-2 mt-3 first:mt-0">{children}</h3>
  ),
  // Списки
  ul: ({ children }: { children?: React.ReactNode }) => (
    <ul className="list-none space-y-1.5 mb-3 pl-1">{children}</ul>
  ),
  ol: ({ children }: { children?: React.ReactNode }) => (
    <ol className="list-decimal list-inside space-y-1.5 mb-3 pl-1">{children}</ol>
  ),
  li: ({ children }: { children?: React.ReactNode }) => (
    <li className="flex gap-2 items-start">
      <span className="text-emerald-400 mt-1.5 flex-shrink-0">•</span>
      <span className="flex-1">{children}</span>
    </li>
  ),
  // Ссылки
  a: ({ href, children }: { href?: string; children?: React.ReactNode }) => (
    <a 
      href={href} 
      target="_blank" 
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1 text-blue-400 hover:text-blue-300 underline decoration-blue-400/30 hover:decoration-blue-300/50 transition-colors"
    >
      {children}
      <ExternalLink className="w-3 h-3 flex-shrink-0" />
    </a>
  ),
  // Код inline
  code: ({ children, className }: { children?: React.ReactNode; className?: string }) => {
    const isBlock = className?.includes('language-')
    if (isBlock) {
      return (
        <code className="block bg-[#0d1117] rounded-lg p-3 my-2 overflow-x-auto text-sm font-mono text-gray-300">
          {children}
        </code>
      )
    }
    return (
      <code className="px-1.5 py-0.5 bg-white/10 rounded text-sm font-mono text-emerald-300">
        {children}
      </code>
    )
  },
  // Блок кода
  pre: ({ children }: { children?: React.ReactNode }) => (
    <pre className="my-2">{children}</pre>
  ),
  // Жирный текст
  strong: ({ children }: { children?: React.ReactNode }) => (
    <strong className="font-semibold text-white">{children}</strong>
  ),
  // Курсив
  em: ({ children }: { children?: React.ReactNode }) => (
    <em className="italic text-gray-300">{children}</em>
  ),
  // Горизонтальная линия
  hr: () => (
    <hr className="my-4 border-white/10" />
  ),
  // Цитата
  blockquote: ({ children }: { children?: React.ReactNode }) => (
    <blockquote className="border-l-2 border-blue-400/50 pl-3 my-3 text-gray-400 italic">
      {children}
    </blockquote>
  ),
}

// Рендер текстового ответа (greeting/help/chat) с markdown
function TextMessage({ msg }: { msg: ChatMessage }) {
  return (
    <div key={msg.id} className="flex gap-3">
      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-br from-emerald-500/20 to-cyan-500/20 flex items-center justify-center">
        <Bot className="w-4 h-4 text-emerald-400" />
      </div>
      <div className="max-w-[85%] bg-white/5 border border-white/10 rounded-2xl rounded-tl-sm px-5 py-4">
        <div className="text-gray-200 prose prose-invert prose-sm max-w-none">
          <ReactMarkdown 
            remarkPlugins={[remarkGfm]}
            components={markdownComponents}
          >
            {msg.content}
          </ReactMarkdown>
        </div>
      </div>
    </div>
  )
}

// Конфигурация этапов для отображения
const STAGE_CONFIG: Record<string, { label: string; icon: typeof Sparkles; color: string }> = {
  intent: { label: 'Анализирую задачу', icon: Sparkles, color: 'text-violet-400' },
  planning: { label: 'Планирую решение', icon: Brain, color: 'text-blue-400' },
  research: { label: 'Ищу информацию', icon: Search, color: 'text-cyan-400' },
  testing: { label: 'Пишу тесты', icon: FlaskConical, color: 'text-amber-400' },
  coding: { label: 'Генерирую код', icon: Code2, color: 'text-emerald-400' },
  validation: { label: 'Проверяю код', icon: ShieldCheck, color: 'text-orange-400' },
  debug: { label: 'Анализирую ошибки', icon: AlertCircle, color: 'text-red-400' },
  fixing: { label: 'Исправляю код', icon: Code2, color: 'text-yellow-400' },
  reflection: { label: 'Оцениваю результат', icon: Brain, color: 'text-purple-400' },
  critic: { label: 'Финальная проверка', icon: CheckCircle2, color: 'text-emerald-400' },
  chat: { label: 'Отвечаю', icon: MessageSquare, color: 'text-blue-400' },
  greeting: { label: 'Приветствую', icon: Sparkles, color: 'text-violet-400' },
  help: { label: 'Помогаю', icon: Sparkles, color: 'text-violet-400' }
}

// Среднее время выполнения этапов (секунды) — эмпирические данные
const STAGE_DURATIONS: Record<string, number> = {
  intent: 3,
  planning: 8,
  research: 12,
  testing: 15,
  coding: 25,
  validation: 5,
  debug: 10,
  fixing: 15,
  reflection: 5,
  critic: 5,
  chat: 5,
  greeting: 1,
  help: 2
}

// Рендер прогресса генерации — компактный анимированный статус
function ProgressMessage({ msg, stages }: { msg: ChatMessage; stages: Record<string, StageStatus> }) {
  const stageData = msg.metadata?.stages || stages
  const [showDetails, setShowDetails] = useState(false)
  
  // Порядок этапов для workflow
  const stageOrder = useMemo(() => 
    ['intent', 'planning', 'research', 'testing', 'coding', 'validation', 'debug', 'fixing', 'reflection', 'critic', 'chat', 'greeting', 'help'],
    []
  )
  
  // Основные этапы для отображения в деталях
  const mainStages = useMemo(() => 
    ['intent', 'planning', 'research', 'testing', 'coding', 'validation', 'reflection', 'critic'],
    []
  )
  
  // Находим текущий активный этап (последний со статусом start или progress)
  const currentStage = useMemo(() => {
    // Ищем последний активный этап
    for (let i = stageOrder.length - 1; i >= 0; i--) {
      const stage = stageOrder[i]
      const status = stageData[stage]
      if (status && (status.status === 'start' || status.status === 'progress')) {
        return stage
      }
    }
    
    // Если нет активных, ищем последний завершённый
    for (let i = stageOrder.length - 1; i >= 0; i--) {
      const stage = stageOrder[i]
      const status = stageData[stage]
      if (status && status.status === 'end') {
        return stage
      }
    }
    
    // Fallback на первый этап
    return 'intent'
  }, [stageData, stageOrder])
  
  const config = STAGE_CONFIG[currentStage] || STAGE_CONFIG.intent
  const Icon = config.icon
  
  // Считаем прогресс
  const completedStages = Object.values(stageData).filter(s => s.status === 'end').length
  const totalStages = 8 // Примерное количество основных этапов
  const progressPercent = Math.min(100, Math.round((completedStages / totalStages) * 100))
  
  // Расчёт оставшегося времени
  const estimatedTimeLeft = useMemo(() => {
    let remainingSeconds = 0
    const mainStages = ['intent', 'planning', 'research', 'testing', 'coding', 'validation', 'reflection', 'critic']
    
    for (const stage of mainStages) {
      const status = stageData[stage]
      if (!status || status.status === 'idle') {
        remainingSeconds += STAGE_DURATIONS[stage] || 5
      } else if (status.status === 'start' || status.status === 'progress') {
        // Текущий этап — добавляем половину времени
        remainingSeconds += (STAGE_DURATIONS[stage] || 5) / 2
      }
      // Завершённые этапы не учитываем
    }
    
    if (remainingSeconds < 5) return null
    if (remainingSeconds < 60) return `~${Math.round(remainingSeconds)} сек`
    return `~${Math.round(remainingSeconds / 60)} мин`
  }, [stageData])

  return (
    <div key={msg.id} className="flex gap-3">
      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-br from-blue-500/20 to-violet-500/20 flex items-center justify-center">
        <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />
      </div>
      <div className="flex-1 max-w-[80%]">
        {/* Компактный статус с анимацией */}
        <div className="bg-white/5 border border-white/10 rounded-2xl rounded-tl-sm px-4 py-3">
          <div className="flex items-center gap-3">
            {/* Иконка текущего этапа с пульсацией */}
            <div className={`relative flex items-center justify-center w-8 h-8 rounded-lg bg-white/5 ${config.color}`}>
              <Icon className="w-4 h-4 animate-pulse" />
              {/* Пульсирующий круг */}
              <span className="absolute inset-0 rounded-lg bg-current opacity-20 animate-ping" />
            </div>
            
            {/* Текст статуса */}
            <div className="flex-1 min-w-0">
              <div className={`text-sm font-medium ${config.color} flex items-center gap-2`}>
                <span>{config.label}</span>
                <span className="inline-flex">
                  <span className="animate-bounce" style={{ animationDelay: '0ms' }}>.</span>
                  <span className="animate-bounce" style={{ animationDelay: '150ms' }}>.</span>
                  <span className="animate-bounce" style={{ animationDelay: '300ms' }}>.</span>
                </span>
              </div>
              
              {/* Мини прогресс-бар */}
              <div className="mt-2 h-1 bg-white/10 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-gradient-to-r from-blue-500 to-violet-500 rounded-full transition-all duration-500 ease-out"
                  style={{ width: `${progressPercent}%` }}
                />
              </div>
            </div>
            
            {/* Процент и время */}
            <div className="flex flex-col items-end gap-0.5">
              <span className="text-xs text-gray-500 tabular-nums">
                {progressPercent}%
              </span>
              {estimatedTimeLeft && (
                <span className="text-[10px] text-gray-600 tabular-nums">
                  {estimatedTimeLeft}
                </span>
              )}
            </div>
          </div>
          
          {/* Кнопка раскрытия деталей */}
          <button
            onClick={() => setShowDetails(!showDetails)}
            className="mt-2 text-xs text-gray-500 hover:text-gray-300 transition-colors flex items-center gap-1"
          >
            <ChevronRight className={`w-3 h-3 transition-transform ${showDetails ? 'rotate-90' : ''}`} />
            {showDetails ? 'Скрыть этапы' : 'Показать все этапы'}
          </button>
          
          {/* Детальный список этапов */}
          {showDetails && (
            <div className="mt-3 space-y-1.5 border-t border-white/5 pt-3">
              {mainStages.map((stage) => {
                const stageStatus = stageData[stage]
                const stageConfig = STAGE_CONFIG[stage]
                if (!stageConfig) return null
                
                const StageIcon = stageConfig.icon
                const status = stageStatus?.status || 'idle'
                const isCompleted = status === 'end'
                const isActive = status === 'start' || status === 'progress'
                const isError = status === 'error'
                
                return (
                  <div 
                    key={stage}
                    className={`flex items-center gap-2 py-1 px-2 rounded-lg transition-colors ${
                      isActive ? 'bg-white/5' : ''
                    }`}
                  >
                    {/* Иконка статуса */}
                    <div className={`w-5 h-5 rounded-full flex items-center justify-center ${
                      isCompleted ? 'bg-emerald-500/20' :
                      isActive ? 'bg-blue-500/20' :
                      isError ? 'bg-red-500/20' :
                      'bg-white/5'
                    }`}>
                      {isCompleted ? (
                        <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                      ) : isActive ? (
                        <Loader2 className="w-3 h-3 text-blue-400 animate-spin" />
                      ) : isError ? (
                        <AlertCircle className="w-3 h-3 text-red-400" />
                      ) : (
                        <StageIcon className="w-3 h-3 text-gray-600" />
                      )}
                    </div>
                    
                    {/* Название этапа */}
                    <span className={`text-xs ${
                      isCompleted ? 'text-emerald-400' :
                      isActive ? 'text-blue-400' :
                      isError ? 'text-red-400' :
                      'text-gray-600'
                    }`}>
                      {stageConfig.label}
                    </span>
                    
                    {/* Время этапа */}
                    <span className="text-[10px] text-gray-600 ml-auto">
                      ~{STAGE_DURATIONS[stage]}с
                    </span>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// Рендер сообщения с кодом
function CodeMessage({ 
  msg, 
  onCopy, 
  onDownload 
}: { 
  msg: ChatMessage
  onCopy: (code: string) => void
  onDownload: (code: string) => void
}) {
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
                onClick={() => onCopy(code)}
                className="p-1.5 text-gray-400 hover:text-white hover:bg-white/10 rounded transition-colors"
                title="Копировать"
              >
                <Copy className="w-4 h-4" />
              </button>
              <button
                onClick={() => onDownload(code)}
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

// Рендер ошибки
function ErrorMessage({ msg }: { msg: ChatMessage }) {
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
}

export const MessageList = forwardRef<HTMLDivElement, MessageListProps>(
  function MessageList({ messages, stages, error, onCopy, onDownload }, ref) {
    const renderMessage = (msg: ChatMessage) => {
      if (msg.role === 'user') return <UserMessage key={msg.id} msg={msg} />
      
      switch (msg.type) {
        case 'text':
          return <TextMessage key={msg.id} msg={msg} />
        case 'progress':
          return <ProgressMessage key={msg.id} msg={msg} stages={stages} />
        case 'code':
          return <CodeMessage key={msg.id} msg={msg} onCopy={onCopy} onDownload={onDownload} />
        case 'error':
          return <ErrorMessage key={msg.id} msg={msg} />
        default:
          return <TextMessage key={msg.id} msg={msg} />
      }
    }

    return (
      <>
        {messages.map(renderMessage)}
        
        {/* Global Error */}
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
        
        <div ref={ref} />
      </>
    )
  }
)
