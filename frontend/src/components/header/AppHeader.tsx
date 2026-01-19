/**
 * Шапка приложения с настройками режима и модели
 */
import { Zap, Settings, Plus, Sparkles, MessagesSquare, Code2, PanelRight, Columns2 } from 'lucide-react'
import { InteractionMode } from '../../types/chat'
import { TaskOptions } from '../../hooks/useAgentStream'

// Конфигурация режимов работы агента
const modeConfig: Record<InteractionMode, { label: string; icon: typeof Sparkles; description: string }> = {
  auto: { label: 'Авто', icon: Sparkles, description: 'Автовыбор режима' },
  chat: { label: 'Диалог', icon: MessagesSquare, description: 'Простое общение' },
  code: { label: 'Код', icon: Code2, description: 'Генерация с тестами' }
}

// Типы layout
export type LayoutMode = 'chat' | 'ide' | 'split'

interface AppHeaderProps {
  options: TaskOptions
  onOptionsChange: (options: TaskOptions) => void
  availableModels: string[]
  isRunning: boolean
  hasMessages: boolean
  showSettings: boolean
  onToggleSettings: () => void
  onNewChat: () => void
  layoutMode: LayoutMode
  onLayoutChange: (mode: LayoutMode) => void
}

export function AppHeader({
  options,
  onOptionsChange,
  availableModels,
  isRunning,
  hasMessages,
  showSettings,
  onToggleSettings,
  onNewChat,
  layoutMode,
  onLayoutChange
}: AppHeaderProps) {
  return (
    <header className="flex-shrink-0 border-b border-white/5 px-6 py-3 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center">
            <Zap className="w-4 h-4 text-white" />
          </div>
          <span className="font-semibold text-white">Cursor Killer</span>
          <span className="text-xs text-gray-500 hidden sm:block">AI Code Agent</span>
        </div>
        
        {/* New Chat Button */}
        {hasMessages && (
          <button
            onClick={onNewChat}
            disabled={isRunning}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-400 
                       hover:text-white hover:bg-white/5 rounded-lg transition-colors
                       disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Plus className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Новый диалог</span>
          </button>
        )}
      </div>
      
      <div className="flex items-center gap-3">
        {/* Agent Mode Switcher (auto/chat/code) */}
        <div className="flex items-center bg-white/5 rounded-lg p-0.5 border border-white/10">
          {(Object.keys(modeConfig) as InteractionMode[]).map((mode) => {
            const config = modeConfig[mode]
            const Icon = config.icon
            const isActive = options.mode === mode
            return (
              <button
                key={mode}
                type="button"
                onClick={(e) => {
                  e.preventDefault()
                  e.stopPropagation()
                  if (!isRunning) {
                    onOptionsChange({ ...options, mode })
                  }
                }}
                disabled={isRunning}
                title={config.description}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all cursor-pointer
                  ${isActive 
                    ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30' 
                    : 'text-gray-400 hover:text-white hover:bg-white/5 border border-transparent'
                  }
                  disabled:opacity-50 disabled:cursor-not-allowed`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">{config.label}</span>
              </button>
            )
          })}
        </div>

        {/* Separator */}
        <div className="w-px h-6 bg-white/10" />

        {/* Layout Switcher (chat/ide/split) */}
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => onLayoutChange('ide')}
            title="Редактор кода"
            className={`p-2 rounded-lg transition-colors ${
              layoutMode === 'ide'
                ? 'bg-emerald-500/20 text-emerald-400'
                : 'text-gray-400 hover:text-white hover:bg-white/5'
            }`}
          >
            <PanelRight className="w-4 h-4" />
          </button>
          <button
            type="button"
            onClick={() => onLayoutChange(layoutMode === 'split' ? 'chat' : 'split')}
            title={layoutMode === 'split' ? 'Только чат' : 'Чат + Редактор'}
            className={`p-2 rounded-lg transition-colors ${
              layoutMode === 'split'
                ? 'bg-emerald-500/20 text-emerald-400'
                : 'text-gray-400 hover:text-white hover:bg-white/5'
            }`}
          >
            <Columns2 className="w-4 h-4" />
          </button>
        </div>

        {/* Model selector */}
        {availableModels.length > 0 && (
          <select
            value={options.model || ''}
            onChange={(e) => onOptionsChange({ ...options, model: e.target.value })}
            disabled={isRunning}
            className="text-xs bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-gray-300 
                       focus:outline-none focus:border-blue-500/50 disabled:opacity-50"
          >
            <option value="" className="bg-gray-900">Авто (умный выбор)</option>
            {availableModels.map(m => (
              <option key={m} value={m} className="bg-gray-900">{m}</option>
            ))}
          </select>
        )}
        
        {/* Settings button */}
        <button
          onClick={onToggleSettings}
          className={`p-2 rounded-lg transition-colors ${
            showSettings ? 'bg-white/10 text-white' : 'text-gray-400 hover:text-white hover:bg-white/5'
          }`}
        >
          <Settings className="w-4 h-4" />
        </button>
      </div>
    </header>
  )
}
