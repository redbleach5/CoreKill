/**
 * Общий компонент для отображения состояния загрузки
 */
import { RefreshCw } from 'lucide-react'

interface LoadingStateProps {
  message?: string
  className?: string
}

export function LoadingState({ message = 'Загрузка...', className = '' }: LoadingStateProps) {
  return (
    <div className={`p-6 flex items-center justify-center ${className}`}>
      <RefreshCw className="w-6 h-6 text-purple-400 animate-spin" />
      <span className="ml-2 text-gray-400">{message}</span>
    </div>
  )
}
