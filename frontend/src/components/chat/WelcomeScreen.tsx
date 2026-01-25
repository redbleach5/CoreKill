/**
 * Экран приветствия для нового чата
 */
import { MessageCircle, Sparkles, MessagesSquare, Code2, Hand, MessageSquare, FileCode, Wrench } from 'lucide-react'
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
  { icon: Hand, text: 'Привет! Что ты умеешь?' },
  { icon: MessageSquare, text: 'Как лучше организовать проект?' },
  { icon: FileCode, text: 'Напиши функцию сортировки' },
  { icon: Wrench, text: 'Создай REST API эндпоинт' }
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
    <div className="text-center py-16 px-4">
      <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-gradient-to-br from-blue-500/20 to-violet-500/20 border border-white/10 mb-6 shadow-lg shadow-blue-500/10">
        <MessageCircle className="w-10 h-10 text-blue-400" />
      </div>
      <h1 className="text-3xl font-semibold text-white mb-3 bg-gradient-to-r from-blue-400 to-violet-400 bg-clip-text text-transparent">
        Чем могу помочь?
      </h1>
      <p className="text-gray-400 max-w-md mx-auto mb-6 leading-relaxed">
        {getModeDescription()}
      </p>
      
      {/* Mode indicator */}
      <div className="flex items-center justify-center gap-2 mb-10">
        <span className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-full text-xs font-medium bg-blue-500/10 text-blue-400 border border-blue-500/20 shadow-sm">
          <Icon className="w-3.5 h-3.5" />
          {config.label}: {config.description}
        </span>
      </div>
      
      {/* Quick suggestions */}
      <div className="flex flex-wrap justify-center gap-3 max-w-2xl mx-auto">
        {QUICK_SUGGESTIONS.map((suggestion) => {
          const SuggestionIcon = suggestion.icon
          return (
            <button
              key={suggestion.text}
              onClick={() => onSuggestionClick(suggestion.text)}
              className="flex items-center gap-2 px-5 py-2.5 text-sm text-gray-300 bg-white/5 hover:bg-white/10 
                         border border-white/10 rounded-full transition-all duration-200
                         hover:border-blue-500/30 hover:shadow-md hover:shadow-blue-500/10
                         active:scale-95"
            >
              <SuggestionIcon className="w-4 h-4 text-blue-400" />
              {suggestion.text}
            </button>
          )
        })}
      </div>
    </div>
  )
}
