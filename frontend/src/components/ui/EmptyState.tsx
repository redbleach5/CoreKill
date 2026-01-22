/**
 * Общий компонент для отображения пустого состояния
 */
interface EmptyStateProps {
  message?: string
  className?: string
}

export function EmptyState({ message = 'Нет данных', className = '' }: EmptyStateProps) {
  return (
    <div className={`p-6 text-center text-gray-400 ${className}`}>
      {message}
    </div>
  )
}
