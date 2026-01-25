/**
 * Компонент ввода сообщения в чат
 */
import { forwardRef } from 'react'
import { Send, Square } from 'lucide-react'

interface ChatInputProps {
  value: string
  onChange: (value: string) => void
  onSubmit: () => void
  onStop: () => void
  isRunning: boolean
  disabled?: boolean
  placeholder?: string
}

export const ChatInput = forwardRef<HTMLTextAreaElement, ChatInputProps>(
  function ChatInput({ 
    value, 
    onChange, 
    onSubmit, 
    onStop, 
    isRunning, 
    disabled = false,
    placeholder = 'Опишите задачу...'
  }, ref) {
    
    const handleKeyDown = (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        onSubmit()
      }
    }

    const handleInput = (e: React.FormEvent<HTMLTextAreaElement>) => {
      const target = e.target as HTMLTextAreaElement
      target.style.height = 'auto'
      target.style.height = Math.min(target.scrollHeight, 128) + 'px'
    }

    return (
      <div className="border-t border-white/5 bg-[#0a0a0f] p-4">
        <div className="max-w-3xl mx-auto">
          <div className="relative">
            <textarea
              ref={ref}
              value={value}
              onChange={(e) => onChange(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={placeholder}
              rows={1}
              disabled={disabled || isRunning}
              className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 pr-24
                         text-white placeholder-gray-500 resize-none
                         focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/25
                         disabled:opacity-50 disabled:cursor-not-allowed
                         min-h-[48px] max-h-32"
              style={{ height: 'auto' }}
              onInput={handleInput}
            />
            
            <div className="absolute right-2 bottom-2 flex items-center gap-1">
              {isRunning ? (
                <button
                  onClick={onStop}
                  className="p-2 rounded-lg bg-red-500/20 text-red-400 hover:bg-red-500/30 transition-colors"
                  title="Остановить"
                >
                  <Square className="w-4 h-4" />
                </button>
              ) : (
                <button
                  onClick={onSubmit}
                  disabled={!value.trim() || disabled}
                  className="p-2 rounded-lg bg-blue-500 text-white hover:bg-blue-600 
                             disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  title="Отправить (Enter)"
                >
                  <Send className="w-4 h-4" />
                </button>
              )}
            </div>
          </div>
          
          <div className="flex items-center justify-center gap-4 mt-2 text-xs text-gray-500">
            <span className="flex items-center gap-1">
              <span className="w-1.5 h-1.5 bg-green-400 rounded-full animate-pulse" />
              AI может ошибаться. Проверяйте результаты.
            </span>
            {value.trim().length > 0 && (
              <span className="text-gray-600">
                {value.trim().length} символов
              </span>
            )}
          </div>
        </div>
      </div>
    )
  }
)
