/**
 * Экран приветствия для нового чата
 */
import { MessageCircle, Sparkles, MessagesSquare, Code2 } from 'lucide-react'
import { InteractionMode } from '../../types/chat'

// Конфигурация режимов с иконками
const modeConfig: Record<InteractionMode, { label: string; icon: typeof Sparkles; description: string }> = {
  auto: { label: 'Авто', icon: Sparkles, description: 'Автовыбор режима' },
  chat: { label: 'Диалог', icon: MessagesSquare, description: 'Простое общение' },
  code: { label: 'Код', icon: Code2, description: 'Генерация с тестами' }
}

interface WelcomeScreenProps {
  mode: InteractionMode
  onSuggestionClick: (text: string) => void
}

const QUICK_SUGGESTIONS = [
  '👋 Привет! Что ты умеешь?',
  '💬 Как лучше организовать проект?',
  '📝 Напиши функцию сортировки',
  '🔧 Создай REST API эндпоинт'
]

export function WelcomeScreen({ mode, onSuggestionClick }: WelcomeScreenProps) {
  const config = modeConfig[mode]
  const Icon = config.icon

  const getModeDescription = () => {
    switch (mode) {
      case 'chat':
        return 'Режим диалога — обсудим архитектуру, ответим на вопросы'
      case 'code':
        return 'Режим генерации — создам код с тестами и валидацией'
      default:
        return 'Авто-режим — сам определю нужен ли код или достаточно обсуждения'
    }
  }

  return (
    <div className="text-center py-16">
      <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500/20 to-violet-500/20 border border-white/10 mb-6">
        <MessageCircle className="w-8 h-8 text-blue-400" />
      </div>
      <h1 className="text-2xl font-semibold text-white mb-2">Чем могу помочь?</h1>
      <p className="text-gray-400 max-w-md mx-auto mb-4">
        {getModeDescription()}
      </p>
      
      {/* Mode indicator */}
      <div className="flex items-center justify-center gap-2 mb-8">
        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-blue-500/10 text-blue-400 border border-blue-500/20">
          <Icon className="w-3.5 h-3.5" />
          {config.label}: {config.description}
        </span>
      </div>
      
      {/* Quick suggestions */}
      <div className="flex flex-wrap justify-center gap-2">
        {QUICK_SUGGESTIONS.map((example) => (
          <button
            key={example}
            onClick={() => onSuggestionClick(example.replace(/^[^\s]+\s/, ''))}
            className="px-4 py-2 text-sm text-gray-400 bg-white/5 hover:bg-white/10 
                       border border-white/10 rounded-full transition-colors"
          >
            {example}
          </button>
        ))}
      </div>
    </div>
  )
}
