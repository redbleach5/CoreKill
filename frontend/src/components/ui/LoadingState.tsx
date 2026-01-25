/**
 * Общий компонент для отображения состояния загрузки
 * 
 * Улучшенная версия с лучшей визуальной обратной связью.
 */
import { Loader2 } from 'lucide-react'

interface LoadingStateProps {
  message?: string
  className?: string
  /** Компактный режим (меньше отступов) */
  compact?: boolean
  /** Показывать анимированные точки */
  showDots?: boolean
}

export function LoadingState({ 
  message = 'Загрузка...', 
  className = '',
  compact = false,
  showDots = true
}: LoadingStateProps) {
  return (
    <div className={`${compact ? 'p-4' : 'p-6'} flex flex-col items-center justify-center gap-3 ${className}`}>
      <div className="relative">
        <Loader2 className="w-6 h-6 text-purple-400 animate-spin" />
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="w-2 h-2 bg-purple-500 rounded-full animate-pulse" />
        </div>
      </div>
      <div className="flex flex-col items-center gap-1">
        <span className="text-gray-300 font-medium">{message}</span>
        {showDots && (
          <div className="flex gap-1 mt-1">
            <span className="w-1.5 h-1.5 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
            <span className="w-1.5 h-1.5 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
            <span className="w-1.5 h-1.5 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
          </div>
        )}
      </div>
    </div>
  )
}
