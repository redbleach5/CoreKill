import { useState, useEffect, useRef } from 'react'
import { ChevronDown, ChevronRight, Brain, Loader2, Square, Sparkles, Clock, Hash } from 'lucide-react'
import { ThinkingState } from '../hooks/useAgentStream'

interface ThinkingBlockProps {
  thinking: ThinkingState
  /** Название этапа (для будущего использования в логах/аналитике) */
  stageName?: string
  /** Компактный режим (для списка сообщений) */
  compact?: boolean
}

/**
 * Компонент для отображения рассуждений reasoning модели.
 * 
 * Показывает <think> блоки от моделей DeepSeek-R1, QwQ в сворачиваемом виде,
 * как extended thinking в ChatGPT.
 * 
 * Состояния:
 * - started/in_progress: показывает спиннер и контент по мере поступления
 * - completed: показывает summary со возможностью развернуть полный текст
 * - interrupted: показывает что рассуждение было прервано
 */
export function ThinkingBlock({ thinking, stageName: _stageName, compact = false }: ThinkingBlockProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const contentRef = useRef<HTMLDivElement>(null)
  
  // Автопрокрутка при новом контенте
  useEffect(() => {
    if (contentRef.current && (thinking.status === 'started' || thinking.status === 'in_progress')) {
      contentRef.current.scrollTop = contentRef.current.scrollHeight
    }
  }, [thinking.content, thinking.status])

  // Не показываем если нет рассуждений
  if (!thinking || thinking.status === 'idle') {
    return null
  }

  const isActive = thinking.status === 'started' || thinking.status === 'in_progress'
  const isInterrupted = thinking.status === 'interrupted'

  // Форматируем время
  const formatTime = (ms: number): string => {
    if (ms < 1000) return `${ms}мс`
    return `${(ms / 1000).toFixed(1)}с`
  }

  // Компактный режим для списка сообщений
  if (compact) {
    return (
      <div className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-xs ${
        isActive 
          ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30' 
          : isInterrupted
          ? 'bg-orange-500/20 text-orange-300 border border-orange-500/30'
          : 'bg-gray-700/50 text-gray-400 border border-gray-600/30'
      }`}>
        {isActive ? (
          <Sparkles className="w-3 h-3 animate-pulse" />
        ) : (
          <Brain className="w-3 h-3" />
        )}
        <span>{formatTime(thinking.elapsedMs)}</span>
        {thinking.totalChars > 0 && (
          <span className="text-gray-500">· {thinking.totalChars}</span>
        )}
      </div>
    )
  }

  return (
    <div className={`mt-2 rounded-xl border transition-all duration-300 overflow-hidden ${
      isActive 
        ? 'border-purple-500/40 bg-gradient-to-br from-purple-500/10 to-purple-600/5 shadow-lg shadow-purple-500/10' 
        : isInterrupted
        ? 'border-orange-500/40 bg-gradient-to-br from-orange-500/10 to-orange-600/5'
        : 'border-gray-700/60 bg-gray-800/40 hover:bg-gray-800/60'
    }`}>
      {/* Заголовок (всегда видим) */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center gap-3 px-4 py-3 text-left transition-colors group"
        disabled={isActive && !thinking.content}
      >
        {/* Иконка сворачивания */}
        <div className="flex-shrink-0">
          {isExpanded ? (
            <ChevronDown className="w-4 h-4 text-gray-400 group-hover:text-gray-300 transition-colors" />
          ) : (
            <ChevronRight className="w-4 h-4 text-gray-400 group-hover:text-gray-300 transition-colors" />
          )}
        </div>

        {/* Иконка мозга / спиннер с анимацией */}
        <div className={`flex-shrink-0 p-1.5 rounded-lg ${
          isActive ? 'bg-purple-500/20' : isInterrupted ? 'bg-orange-500/20' : 'bg-gray-700/50'
        }`}>
          {isActive ? (
            <div className="relative">
              <Sparkles className="w-4 h-4 text-purple-400 animate-pulse" />
              <Loader2 className="w-4 h-4 text-purple-400 animate-spin absolute inset-0 opacity-50" />
            </div>
          ) : isInterrupted ? (
            <Square className="w-4 h-4 text-orange-400" />
          ) : (
            <Brain className="w-4 h-4 text-purple-400" />
          )}
        </div>

        {/* Текст заголовка */}
        <div className="flex-1 min-w-0">
          <span className={`text-sm font-medium ${
            isActive ? 'text-purple-300' : isInterrupted ? 'text-orange-300' : 'text-gray-300'
          }`}>
            {isActive ? (
              <span className="flex items-center gap-2">
                Рассуждаю
                <span className="flex gap-1">
                  <span className="w-1.5 h-1.5 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                  <span className="w-1.5 h-1.5 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                  <span className="w-1.5 h-1.5 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                </span>
              </span>
            ) : isInterrupted ? (
              'Рассуждение прервано'
            ) : (
              'Рассуждение завершено'
            )}
          </span>
          {thinking.summary && !isExpanded && !isActive && (
            <p className="text-xs text-gray-500 truncate mt-0.5">
              {thinking.summary}
            </p>
          )}
        </div>

        {/* Метрики */}
        <div className="flex items-center gap-3 text-xs text-gray-500 flex-shrink-0">
          <span className="flex items-center gap-1">
            <Clock className="w-3 h-3" />
            {formatTime(thinking.elapsedMs)}
          </span>
          {thinking.totalChars > 0 && (
            <span className="flex items-center gap-1">
              <Hash className="w-3 h-3" />
              {thinking.totalChars.toLocaleString()}
            </span>
          )}
        </div>
      </button>

      {/* Контент (раскрывается) */}
      {(isExpanded || isActive) && thinking.content && (
        <div className="px-4 pb-4">
          <div 
            ref={contentRef}
            className={`
              text-sm text-gray-400 whitespace-pre-wrap font-mono leading-relaxed
              max-h-80 overflow-y-auto scroll-smooth
              p-4 rounded-lg bg-gray-900/70 border border-gray-700/50
              ${isActive ? 'ring-1 ring-purple-500/30' : ''}
            `}
          >
            {thinking.content}
            {isActive && (
              <span className="inline-block w-2 h-5 bg-purple-400 animate-pulse ml-0.5 rounded-sm" />
            )}
          </div>
        </div>
      )}
    </div>
  )
}
