/**
 * Общий компонент для отображения пустого состояния
 * 
 * Улучшенная версия с иконкой и лучшей визуальной обратной связью.
 */
import { Inbox, FileX } from 'lucide-react'

interface EmptyStateProps {
  message?: string
  className?: string
  /** Иконка (по умолчанию Inbox) */
  icon?: 'inbox' | 'file'
  /** Компактный режим */
  compact?: boolean
}

export function EmptyState({ 
  message = 'Нет данных', 
  className = '',
  icon = 'inbox',
  compact = false
}: EmptyStateProps) {
  const Icon = icon === 'file' ? FileX : Inbox
  
  return (
    <div className={`${compact ? 'p-4' : 'p-8'} text-center ${className}`}>
      <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-white/5 border border-white/10 mb-4">
        <Icon className="w-8 h-8 text-gray-500" />
      </div>
      <p className="text-gray-400 text-sm leading-relaxed">
        {message}
      </p>
    </div>
  )
}
