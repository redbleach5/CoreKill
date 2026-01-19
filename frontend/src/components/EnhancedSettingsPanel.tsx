/**
 * Улучшенная панель настроек с лучшим UX
 */
import { useState } from 'react'
import { X, Save, RotateCcw, ChevronDown } from 'lucide-react'

interface EnhancedSettingsPanelProps {
  onClose: () => void
  availableModels: string[]
  currentSettings: {
    model: string
    temperature: number
    maxIterations: number
    disableWebSearch: boolean
  }
  onSettingsChange: (settings: any) => void
}

export function EnhancedSettingsPanel({
  onClose,
  availableModels,
  currentSettings,
  onSettingsChange
}: EnhancedSettingsPanelProps) {
  const [settings, setSettings] = useState(currentSettings)
  const [expandedSections, setExpandedSections] = useState<Set<string>>(
    new Set(['model', 'generation', 'search'])
  )

  const toggleSection = (section: string) => {
    const newExpanded = new Set(expandedSections)
    if (newExpanded.has(section)) {
      newExpanded.delete(section)
    } else {
      newExpanded.add(section)
    }
    setExpandedSections(newExpanded)
  }

  const handleSave = () => {
    onSettingsChange(settings)
    onClose()
  }

  const handleReset = () => {
    setSettings(currentSettings)
  }

  const SettingSection = ({
    title,
    id,
    children
  }: {
    title: string
    id: string
    children: React.ReactNode
  }) => (
    <div className="border-b border-white/10 last:border-b-0">
      <button
        onClick={() => toggleSection(id)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-white/5 transition-colors"
      >
        <span className="font-medium text-white">{title}</span>
        <ChevronDown
          className={`w-4 h-4 text-gray-400 transition-transform ${
            expandedSections.has(id) ? 'rotate-180' : ''
          }`}
        />
      </button>
      {expandedSections.has(id) && (
        <div className="px-4 py-3 bg-white/5 space-y-4">{children}</div>
      )}
    </div>
  )

  const SettingItem = ({
    label,
    description,
    children
  }: {
    label: string
    description?: string
    children: React.ReactNode
  }) => (
    <div>
      <label className="block text-sm font-medium text-gray-300 mb-1">
        {label}
      </label>
      {description && (
        <p className="text-xs text-gray-500 mb-2">{description}</p>
      )}
      {children}
    </div>
  )

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-[#1a1a1f] border border-white/10 rounded-xl w-96 max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10">
          <h2 className="text-lg font-semibold text-white">Настройки</h2>
          <button
            onClick={onClose}
            className="p-1 text-gray-400 hover:text-white hover:bg-white/10 rounded transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto">
          {/* Model Selection */}
          <SettingSection title="Модель" id="model">
            <SettingItem
              label="LLM модель"
              description="Выберите модель для генерации кода"
            >
              <select
                value={settings.model}
                onChange={(e) => setSettings({ ...settings, model: e.target.value })}
                className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded text-white text-sm focus:outline-none focus:border-blue-500/50"
              >
                <option value="">Автоматический выбор</option>
                {availableModels.map(model => (
                  <option key={model} value={model}>
                    {model}
                  </option>
                ))}
              </select>
            </SettingItem>
          </SettingSection>

          {/* Generation Settings */}
          <SettingSection title="Генерация" id="generation">
            <SettingItem
              label="Температура"
              description="Контролирует творчество (0.1 = консервативно, 0.7 = творчески)"
            >
              <div className="flex items-center gap-3">
                <input
                  type="range"
                  min="0.1"
                  max="0.7"
                  step="0.05"
                  value={settings.temperature}
                  onChange={(e) =>
                    setSettings({ ...settings, temperature: parseFloat(e.target.value) })
                  }
                  className="flex-1"
                />
                <span className="text-sm font-mono text-gray-400 w-12 text-right">
                  {settings.temperature.toFixed(2)}
                </span>
              </div>
            </SettingItem>

            <SettingItem
              label="Максимум итераций"
              description="Количество попыток исправления ошибок"
            >
              <div className="flex items-center gap-3">
                <input
                  type="range"
                  min="1"
                  max="5"
                  value={settings.maxIterations}
                  onChange={(e) =>
                    setSettings({ ...settings, maxIterations: parseInt(e.target.value) })
                  }
                  className="flex-1"
                />
                <span className="text-sm font-mono text-gray-400 w-8 text-right">
                  {settings.maxIterations}
                </span>
              </div>
            </SettingItem>
          </SettingSection>

          {/* Search Settings */}
          <SettingSection title="Поиск" id="search">
            <SettingItem
              label="Веб-поиск"
              description="Использовать веб-поиск для сбора контекста"
            >
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={!settings.disableWebSearch}
                  onChange={(e) =>
                    setSettings({ ...settings, disableWebSearch: !e.target.checked })
                  }
                  className="w-4 h-4 rounded border-white/20 text-blue-600 focus:ring-blue-500"
                />
                <span className="text-sm text-gray-300">
                  {settings.disableWebSearch ? 'Отключен' : 'Включен'}
                </span>
              </label>
            </SettingItem>
          </SettingSection>

          {/* Advanced Settings */}
          <SettingSection title="Дополнительно" id="advanced">
            <div className="space-y-3 text-sm text-gray-400">
              <div className="flex justify-between">
                <span>Версия API:</span>
                <span className="text-gray-300">1.0.0</span>
              </div>
              <div className="flex justify-between">
                <span>Статус Ollama:</span>
                <span className="text-emerald-400">● Подключено</span>
              </div>
              <div className="flex justify-between">
                <span>RAG память:</span>
                <span className="text-gray-300">Активна</span>
              </div>
            </div>
          </SettingSection>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-white/10 bg-white/5">
          <button
            onClick={handleReset}
            className="flex items-center gap-2 px-3 py-2 text-sm text-gray-400 hover:text-gray-300 hover:bg-white/10 rounded transition-colors"
          >
            <RotateCcw className="w-4 h-4" />
            Сбросить
          </button>
          <button
            onClick={handleSave}
            className="flex items-center gap-2 px-4 py-2 text-sm bg-blue-600 text-white hover:bg-blue-700 rounded transition-colors"
          >
            <Save className="w-4 h-4" />
            Сохранить
          </button>
        </div>
      </div>
    </div>
  )
}
