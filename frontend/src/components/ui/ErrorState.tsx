/**
 * Общий компонент для отображения состояния ошибки
 */
import { AlertTriangle } from 'lucide-react'

interface ErrorStateProps {
  title?: string
  message?: string
  onRetry?: () => void
  retryLabel?: string
  className?: string
}

export function ErrorState({
  title = 'Произошла ошибка',
  message,
  onRetry,
  retryLabel = 'Повторить',
  className = ''
}: ErrorStateProps) {
  return (
    <div className={`p-6 text-center ${className}`}>
      <AlertTriangle className="w-8 h-8 text-yellow-400 mx-auto mb-2" />
      <p className="text-gray-400">{title}</p>
      {message && <p className="text-sm text-gray-500 mt-1">{message}</p>}
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-4 px-4 py-2 bg-purple-500/20 text-purple-300 rounded-lg hover:bg-purple-500/30 transition-colors"
        >
          {retryLabel}
        </button>
      )}
    </div>
  )
}
