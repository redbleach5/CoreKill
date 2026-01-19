"""Панель настроек приложения."""
import React, { useState, useEffect } from 'react'
import { X, Save, RotateCcw } from 'lucide-react'

interface Settings {
  model: string
  temperature: number
  maxIterations: number
  enableWebSearch: boolean
  enableRAG: boolean
  maxTokens: number
}

interface SettingsPanelProps {
  isOpen: boolean
  onClose: () => void
  onSave: (settings: Settings) => void
  availableModels: string[]
}

const DEFAULT_SETTINGS: Settings = {
  model: 'codellama:7b',
  temperature: 0.25,
  maxIterations: 3,
  enableWebSearch: true,
  enableRAG: true,
  maxTokens: 4096
}

export const SettingsPanel: React.FC<SettingsPanelProps> = ({
  isOpen,
  onClose,
  onSave,
  availableModels
}) => {
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS)
  const [hasChanges, setHasChanges] = useState(false)

  // Загружаем сохранённые настройки из localStorage
  useEffect(() => {
    const saved = localStorage.getItem('appSettings')
    if (saved) {
      try {
        setSettings(JSON.parse(saved))
      } catch (e) {
        console.error('Ошибка при загрузке настроек:', e)
      }
    }
  }, [isOpen])

  const handleChange = (key: keyof Settings, value: any) => {
    setSettings(prev => ({ ...prev, [key]: value }))
    setHasChanges(true)
  }

  const handleSave = () => {
    localStorage.setItem('appSettings', JSON.stringify(settings))
    onSave(settings)
    setHasChanges(false)
    onClose()
  }

  const handleReset = () => {
    setSettings(DEFAULT_SETTINGS)
    setHasChanges(true)
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="bg-slate-900 border border-white/10 rounded-2xl shadow-2xl max-w-md w-full mx-4 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-white/10 sticky top-0 bg-slate-900">
          <h2 className="text-lg font-semibold text-white">Настройки</h2>
          <button
            onClick={onClose}
            className="p-1 hover:bg-white/10 rounded transition-colors"
          >
            <X className="w-5 h-5 text-gray-400" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Model Selection */}
          <div>
            <label className="block text-sm font-medium text-gray-200 mb-2">
              Модель
            </label>
            <select
              value={settings.model}
              onChange={e => handleChange('model', e.target.value)}
              className="w-full bg-white/10 border border-white/20 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500 transition-colors"
            >
              {availableModels.map(model => (
                <option key={model} value={model} className="bg-slate-900">
                  {model}
                </option>
              ))}
            </select>
            <p className="text-xs text-gray-500 mt-1">
              Выберите LLM модель для генерации кода
            </p>
          </div>

          {/* Temperature */}
          <div>
            <label className="block text-sm font-medium text-gray-200 mb-2">
              Температура: {settings.temperature.toFixed(2)}
            </label>
            <input
              type="range"
              min="0.1"
              max="0.7"
              step="0.05"
              value={settings.temperature}
              onChange={e => handleChange('temperature', parseFloat(e.target.value))}
              className="w-full"
            />
            <p className="text-xs text-gray-500 mt-1">
              Ниже = детерминированнее, выше = креативнее
            </p>
          </div>

          {/* Max Iterations */}
          <div>
            <label className="block text-sm font-medium text-gray-200 mb-2">
              Максимум итераций: {settings.maxIterations}
            </label>
            <input
              type="range"
              min="1"
              max="5"
              step="1"
              value={settings.maxIterations}
              onChange={e => handleChange('maxIterations', parseInt(e.target.value))}
              className="w-full"
            />
            <p className="text-xs text-gray-500 mt-1">
              Количество попыток исправления кода
            </p>
          </div>

          {/* Max Tokens */}
          <div>
            <label className="block text-sm font-medium text-gray-200 mb-2">
              Максимум токенов: {settings.maxTokens}
            </label>
            <input
              type="range"
              min="512"
              max="8192"
              step="256"
              value={settings.maxTokens}
              onChange={e => handleChange('maxTokens', parseInt(e.target.value))}
              className="w-full"
            />
            <p className="text-xs text-gray-500 mt-1">
              Максимальная длина генерируемого текста
            </p>
          </div>

          {/* Toggles */}
          <div className="space-y-3">
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={settings.enableWebSearch}
                onChange={e => handleChange('enableWebSearch', e.target.checked)}
                className="w-4 h-4 rounded bg-white/10 border border-white/20 checked:bg-blue-600 checked:border-blue-600"
              />
              <span className="text-sm text-gray-200">Включить веб-поиск</span>
            </label>

            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={settings.enableRAG}
                onChange={e => handleChange('enableRAG', e.target.checked)}
                className="w-4 h-4 rounded bg-white/10 border border-white/20 checked:bg-blue-600 checked:border-blue-600"
              />
              <span className="text-sm text-gray-200">Включить RAG (контекст)</span>
            </label>
          </div>
        </div>

        {/* Footer */}
        <div className="flex gap-3 p-6 border-t border-white/10 bg-black/20">
          <button
            onClick={handleReset}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-white/10 hover:bg-white/20 text-white rounded-lg transition-colors"
          >
            <RotateCcw className="w-4 h-4" />
            Сброс
          </button>
          <button
            onClick={handleSave}
            disabled={!hasChanges}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white rounded-lg transition-colors"
          >
            <Save className="w-4 h-4" />
            Сохранить
          </button>
        </div>
      </div>
    </div>
  )
}
