/**
 * Общий компонент для отображения состояния ошибки
 * 
 * Улучшенная версия с лучшей визуальной обратной связью и деталями.
 */
import { AlertTriangle, RefreshCw, XCircle } from 'lucide-react'

interface ErrorStateProps {
  title?: string
  message?: string
  onRetry?: () => void
  retryLabel?: string
  className?: string
  /** Тип ошибки (для разных стилей) */
  variant?: 'error' | 'warning' | 'info'
  /** Компактный режим */
  compact?: boolean
}

export function ErrorState({
  title = 'Произошла ошибка',
  message,
  onRetry,
  retryLabel = 'Повторить',
  className = '',
  variant = 'error',
  compact = false
}: ErrorStateProps) {
  const variantStyles = {
    error: {
      icon: XCircle,
      iconColor: 'text-red-400',
      bgColor: 'bg-red-500/10',
      borderColor: 'border-red-500/30',
      textColor: 'text-red-300',
      buttonBg: 'bg-red-500/20 hover:bg-red-500/30 text-red-300'
    },
    warning: {
      icon: AlertTriangle,
      iconColor: 'text-yellow-400',
      bgColor: 'bg-yellow-500/10',
      borderColor: 'border-yellow-500/30',
      textColor: 'text-yellow-300',
      buttonBg: 'bg-yellow-500/20 hover:bg-yellow-500/30 text-yellow-300'
    },
    info: {
      icon: AlertTriangle,
      iconColor: 'text-blue-400',
      bgColor: 'bg-blue-500/10',
      borderColor: 'border-blue-500/30',
      textColor: 'text-blue-300',
      buttonBg: 'bg-blue-500/20 hover:bg-blue-500/30 text-blue-300'
    }
  }

  const style = variantStyles[variant]
  const Icon = style.icon

  return (
    <div className={`${compact ? 'p-4' : 'p-6'} text-center ${className}`}>
      <div className={`inline-flex items-center justify-center w-16 h-16 rounded-full ${style.bgColor} ${style.borderColor} border-2 mb-4`}>
        <Icon className={`w-8 h-8 ${style.iconColor}`} />
      </div>
      <h3 className={`text-lg font-semibold ${style.textColor} mb-2`}>{title}</h3>
      {message && (
        <p className="text-sm text-gray-400 max-w-md mx-auto leading-relaxed">
          {message}
        </p>
      )}
      {onRetry && (
        <button
          onClick={onRetry}
          className={`mt-4 px-4 py-2 rounded-lg transition-all duration-200 flex items-center gap-2 mx-auto ${style.buttonBg}`}
        >
          <RefreshCw className="w-4 h-4" />
          {retryLabel}
        </button>
      )}
    </div>
  )
}
