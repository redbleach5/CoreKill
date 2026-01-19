/**
 * Совместимая версия EnhancedSettingsPanel
 * Работает с существующей системой настроек
 */
import { useState } from 'react'
import { Settings, X, ChevronDown } from 'lucide-react'

interface SettingsPanelCompatProps {
  onClose: () => void
  availableModels?: string[]
  currentSettings?: {
    model: string
    temperature: number
    disableWebSearch: boolean
    maxIterations: number
    mode: string
  }
  onSettingsChange?: (settings: any) => void
}

export function EnhancedSettingsPanelCompat({
  onClose,
  availableModels = [],
  currentSettings = {
    model: '',
    temperature: 0.25,
    disableWebSearch: false,
    maxIterations: 3,
    mode: 'auto'
  },
  onSettingsChange
}: SettingsPanelCompatProps) {
  const [settings, setSettings] = useState(currentSettings)
  const [expandedSections, setExpandedSections] = useState({
    model: true,
    advanced: false,
    safety: false
  })

  const handleSettingChange = (key: string, value: any) => {
    const newSettings = { ...settings, [key]: value }
    setSettings(newSettings)
    onSettingsChange?.(newSettings)
  }

  const toggleSection = (section: string) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section]
    }))
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-[#1a1a24] rounded-lg shadow-xl w-96 max-h-[90vh] overflow-y-auto border border-white/10">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-white/10">
          <div className="flex items-center gap-2">
            <Settings className="w-5 h-5 text-blue-400" />
            <h2 className="text-lg font-semibold text-white">Настройки</h2>
          </div>
          <button
            onClick={onClose}
            className="p-1 text-gray-400 hover:text-white hover:bg-white/10 rounded transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-4">
          {/* Model Selection */}
          <div className="space-y-2">
            <button
              onClick={() => toggleSection('model')}
              className="w-full flex items-center justify-between p-3 rounded-lg hover:bg-white/5 transition-colors"
            >
              <span className="font-medium text-white">Модель LLM</span>
              <ChevronDown
                className={`w-4 h-4 text-gray-400 transition-transform ${
                  expandedSections.model ? 'rotate-180' : ''
                }`}
              />
            </button>
            {expandedSections.model && (
              <div className="pl-3 space-y-2">
                <select
                  value={settings.model}
                  onChange={(e) => handleSettingChange('model', e.target.value)}
                  className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded text-white text-sm focus:outline-none focus:border-blue-500/50"
                >
                  <option value="">Выберите модель</option>
                  {availableModels.map(model => (
                    <option key={model} value={model}>
                      {model}
                    </option>
                  ))}
                </select>
                <p className="text-xs text-gray-500">Выберите модель для генерации кода</p>
              </div>
            )}
          </div>

          {/* Temperature */}
          <div className="space-y-2">
            <label className="block text-sm font-medium text-white">
              Температура (творчество): {settings.temperature.toFixed(2)}
            </label>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={settings.temperature}
              onChange={(e) => handleSettingChange('temperature', parseFloat(e.target.value))}
              className="w-full h-2 bg-white/10 rounded-lg appearance-none cursor-pointer accent-blue-500"
            />
            <p className="text-xs text-gray-500">
              Низкое значение = предсказуемый код, высокое = творческий код
            </p>
          </div>

          {/* Max Iterations */}
          <div className="space-y-2">
            <label className="block text-sm font-medium text-white">
              Максимум итераций: {settings.maxIterations}
            </label>
            <input
              type="range"
              min="1"
              max="10"
              step="1"
              value={settings.maxIterations}
              onChange={(e) => handleSettingChange('maxIterations', parseInt(e.target.value))}
              className="w-full h-2 bg-white/10 rounded-lg appearance-none cursor-pointer accent-blue-500"
            />
            <p className="text-xs text-gray-500">
              Количество попыток улучшения кода
            </p>
          </div>

          {/* Advanced Settings */}
          <div className="space-y-2">
            <button
              onClick={() => toggleSection('advanced')}
              className="w-full flex items-center justify-between p-3 rounded-lg hover:bg-white/5 transition-colors"
            >
              <span className="font-medium text-white">Продвинутые</span>
              <ChevronDown
                className={`w-4 h-4 text-gray-400 transition-transform ${
                  expandedSections.advanced ? 'rotate-180' : ''
                }`}
              />
            </button>
            {expandedSections.advanced && (
              <div className="pl-3 space-y-3">
                <div className="flex items-center justify-between">
                  <label className="text-sm text-gray-300">Режим</label>
                  <select
                    value={settings.mode}
                    onChange={(e) => handleSettingChange('mode', e.target.value)}
                    className="px-2 py-1 bg-white/5 border border-white/10 rounded text-white text-xs focus:outline-none focus:border-blue-500/50"
                  >
                    <option value="auto">Автоматический</option>
                    <option value="fast">Быстрый</option>
                    <option value="quality">Качество</option>
                  </select>
                </div>
              </div>
            )}
          </div>

          {/* Safety Settings */}
          <div className="space-y-2">
            <button
              onClick={() => toggleSection('safety')}
              className="w-full flex items-center justify-between p-3 rounded-lg hover:bg-white/5 transition-colors"
            >
              <span className="font-medium text-white">Безопасность</span>
              <ChevronDown
                className={`w-4 h-4 text-gray-400 transition-transform ${
                  expandedSections.safety ? 'rotate-180' : ''
                }`}
              />
            </button>
            {expandedSections.safety && (
              <div className="pl-3 space-y-3">
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={settings.disableWebSearch}
                    onChange={(e) => handleSettingChange('disableWebSearch', e.target.checked)}
                    className="w-4 h-4 rounded border-white/20 text-blue-500 focus:ring-0"
                  />
                  <span className="text-sm text-gray-300">Отключить веб-поиск</span>
                </label>
                <p className="text-xs text-gray-500">
                  Отключение веб-поиска повышает безопасность, но может снизить качество результатов
                </p>
              </div>
            )}
          </div>

          {/* Info */}
          <div className="mt-6 p-3 rounded-lg bg-blue-500/10 border border-blue-500/20">
            <p className="text-xs text-blue-300">
              💡 Совет: Используйте низкую температуру для надёжного кода и высокую для экспериментов.
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="flex gap-2 p-6 border-t border-white/10">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2 bg-white/10 text-white rounded-lg hover:bg-white/20 transition-colors text-sm font-medium"
          >
            Закрыть
          </button>
        </div>
      </div>
    </div>
  )
}
