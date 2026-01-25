// Панель настроек приложения
import React, { useState, useEffect } from 'react'
import { X, Save, RotateCcw, Zap, Thermometer, Search, Database, Target, Code, RotateCcw as RotateIcon } from 'lucide-react'
import { formatModelName, isReasoningModelSync } from '../utils/modelUtils'
import { useLocalStorage } from '../hooks/useLocalStorage'

interface Settings {
  model: string
  temperature: number
  topP: number
  maxIterations: number
  maxTokens: number
  enableWebSearch: boolean
  webSearchMaxResults: number
  enableRAG: boolean
  ragSimilarityThreshold: number
  qualityThreshold: number
}

interface SettingsPanelProps {
  isOpen: boolean
  onClose: () => void
  onSave: (settings: Settings) => void
  availableModels: string[]
}

const DEFAULT_SETTINGS: Settings = {
  model: '',
  temperature: 0.25,
  topP: 0.9,
  maxIterations: 3,
  maxTokens: 4096,
  enableWebSearch: true,
  webSearchMaxResults: 3,
  enableRAG: true,
  ragSimilarityThreshold: 0.5,
  qualityThreshold: 0.7
}

export const SettingsPanel: React.FC<SettingsPanelProps> = ({
  isOpen,
  onClose,
  onSave,
  availableModels
}) => {
  const [settings, setSettings] = useLocalStorage<Settings>('appSettings', DEFAULT_SETTINGS)
  const [hasChanges, setHasChanges] = useState(false)

  // Очищаем старые поля при загрузке (если они есть в localStorage)
  useEffect(() => {
    if (isOpen) {
      const cleanSettings = { ...settings }
      // Удаляем несуществующие поля из типа Settings
      if ('projectPath' in cleanSettings) {
        delete (cleanSettings as any).projectPath
      }
      if ('fileExtensions' in cleanSettings) {
        delete (cleanSettings as any).fileExtensions
      }
      // Проверяем, были ли изменения
      const hasOldFields = 'projectPath' in settings || 'fileExtensions' in settings
      if (hasOldFields) {
        setSettings(cleanSettings as Settings)
      }
    }
  }, [isOpen, settings, setSettings])

  const handleChange = (key: keyof Settings, value: any) => {
    setSettings(prev => ({ ...prev, [key]: value }))
    setHasChanges(true)
  }

  const handleSave = () => {
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
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50" onClick={onClose}>
      <div 
        className="bg-slate-900 border border-white/10 rounded-2xl shadow-2xl max-w-lg w-full mx-4 max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-white/10 sticky top-0 bg-slate-900 z-10">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <Code className="w-5 h-5 text-blue-500" />
            Расширенные настройки
          </h2>
          <button
            onClick={onClose}
            className="p-1.5 hover:bg-white/10 rounded-lg transition-colors text-gray-400 hover:text-white"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Model Selection */}
          <div className="space-y-2">
            <label className="block text-sm font-medium text-gray-200 flex items-center gap-2">
              <Code className="w-4 h-4 text-gray-400" />
              Модель LLM
              {settings.model && isReasoningModelSync(settings.model) && (
                <span title="Reasoning модель">
                  <Zap className="w-3.5 h-3.5 text-yellow-500" />
                </span>
              )}
            </label>
            <div className="relative">
              <select
                value={settings.model}
                onChange={e => handleChange('model', e.target.value)}
                className="w-full bg-white/10 border border-white/20 rounded-lg px-3 py-2.5 pr-10 text-white text-sm focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all appearance-none cursor-pointer"
              >
                <option value="" className="bg-slate-900">Авто (умный выбор)</option>
                {availableModels.map(model => (
                  <option key={model} value={model} className="bg-slate-900">
                    {formatModelName(model)}
                  </option>
                ))}
              </select>
              {/* Иконка Zap для reasoning моделей в селекте (из Tool Calls) */}
              {settings.model && isReasoningModelSync(settings.model) && (
                <div className="absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none">
                  <Zap className="w-4 h-4 text-gray-400" />
                </div>
              )}
            </div>
            <p className="text-xs text-gray-500">
              {settings.model && isReasoningModelSync(settings.model) 
                ? 'Reasoning модель: показывает процесс размышления в <think> блоках'
                : settings.model 
                  ? 'Выбранная модель для генерации кода'
                  : 'Автоматический выбор оптимальной модели'}
            </p>
          </div>

          {/* Temperature */}
          <div className="space-y-2">
            <label className="block text-sm font-medium text-gray-200 flex items-center gap-2">
              <Thermometer className="w-4 h-4 text-gray-400" />
              Температура: <span className="text-blue-400 font-mono ml-1">{settings.temperature.toFixed(2)}</span>
            </label>
            <input
              type="range"
              min="0.1"
              max="0.7"
              step="0.05"
              value={settings.temperature}
              onChange={e => handleChange('temperature', parseFloat(e.target.value))}
              className="w-full h-2 bg-white/10 rounded-lg appearance-none cursor-pointer accent-blue-500 hover:accent-blue-400 transition-colors"
            />
            <div className="flex justify-between text-xs text-gray-500">
              <span>Детерминированно</span>
              <span>Креативно</span>
            </div>
          </div>

          {/* Max Iterations */}
          <div className="space-y-2">
            <label className="block text-sm font-medium text-gray-200 flex items-center gap-2">
              <RotateIcon className="w-4 h-4 text-gray-400" />
              Максимум итераций: <span className="text-blue-400 font-mono ml-1">{settings.maxIterations}</span>
            </label>
            <input
              type="range"
              min="1"
              max="5"
              step="1"
              value={settings.maxIterations}
              onChange={e => handleChange('maxIterations', parseInt(e.target.value))}
              className="w-full h-2 bg-white/10 rounded-lg appearance-none cursor-pointer accent-blue-500 hover:accent-blue-400 transition-colors"
            />
            <p className="text-xs text-gray-500">
              Количество попыток исправления кода при ошибках
            </p>
          </div>

          {/* Top P */}
          <div className="space-y-2">
            <label className="block text-sm font-medium text-gray-200">
              Top P: <span className="text-blue-400 font-mono ml-1">{settings.topP.toFixed(2)}</span>
            </label>
            <input
              type="range"
              min="0.1"
              max="1.0"
              step="0.05"
              value={settings.topP}
              onChange={e => handleChange('topP', parseFloat(e.target.value))}
              className="w-full h-2 bg-white/10 rounded-lg appearance-none cursor-pointer accent-blue-500 hover:accent-blue-400 transition-colors"
            />
            <p className="text-xs text-gray-500">
              Контролирует разнообразие генерации (nucleus sampling)
            </p>
          </div>

          {/* Max Tokens */}
          <div className="space-y-2">
            <label className="block text-sm font-medium text-gray-200">
              Максимум токенов: <span className="text-blue-400 font-mono ml-1">{settings.maxTokens}</span>
            </label>
            <input
              type="range"
              min="512"
              max="8192"
              step="256"
              value={settings.maxTokens}
              onChange={e => handleChange('maxTokens', parseInt(e.target.value))}
              className="w-full h-2 bg-white/10 rounded-lg appearance-none cursor-pointer accent-blue-500 hover:accent-blue-400 transition-colors"
            />
            <p className="text-xs text-gray-500">
              Максимальная длина генерируемого текста
            </p>
          </div>

          {/* Web Search Settings */}
          <div className="border-t border-white/10 pt-6 space-y-4">
            <h3 className="text-sm font-medium text-gray-200 flex items-center gap-2 mb-4">
              <Search className="w-4 h-4 text-gray-400" />
              Веб-поиск
            </h3>
            
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={settings.enableWebSearch}
                onChange={e => handleChange('enableWebSearch', e.target.checked)}
                className="w-4 h-4 rounded bg-white/10 border border-white/20 checked:bg-blue-600 checked:border-blue-600 focus:ring-2 focus:ring-blue-500/50 cursor-pointer transition-colors"
              />
              <span className="text-sm text-gray-200">Включить веб-поиск</span>
            </label>

            {settings.enableWebSearch && (
              <div className="space-y-2">
                <label className="block text-sm font-medium text-gray-200">
                  Максимум результатов: <span className="text-blue-400 font-mono ml-1">{settings.webSearchMaxResults}</span>
                </label>
                <input
                  type="range"
                  min="1"
                  max="10"
                  step="1"
                  value={settings.webSearchMaxResults}
                  onChange={e => handleChange('webSearchMaxResults', parseInt(e.target.value))}
                  className="w-full h-2 bg-white/10 rounded-lg appearance-none cursor-pointer accent-blue-500 hover:accent-blue-400 transition-colors"
                />
                <p className="text-xs text-gray-500">
                  Количество результатов веб-поиска для использования в контексте
                </p>
              </div>
            )}
          </div>

          {/* RAG Settings */}
          <div className="border-t border-white/10 pt-6 space-y-4">
            <h3 className="text-sm font-medium text-gray-200 flex items-center gap-2 mb-4">
              <Database className="w-4 h-4 text-gray-400" />
              RAG (Retrieval-Augmented Generation)
            </h3>
            
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={settings.enableRAG}
                onChange={e => handleChange('enableRAG', e.target.checked)}
                className="w-4 h-4 rounded bg-white/10 border border-white/20 checked:bg-blue-600 checked:border-blue-600 focus:ring-2 focus:ring-blue-500/50 cursor-pointer transition-colors"
              />
              <span className="text-sm text-gray-200">Включить RAG (контекст из памяти)</span>
            </label>

            {settings.enableRAG && (
              <div className="space-y-2">
                <label className="block text-sm font-medium text-gray-200">
                  Порог схожести: <span className="text-blue-400 font-mono ml-1">{settings.ragSimilarityThreshold.toFixed(2)}</span>
                </label>
                <input
                  type="range"
                  min="0.1"
                  max="1.0"
                  step="0.05"
                  value={settings.ragSimilarityThreshold}
                  onChange={e => handleChange('ragSimilarityThreshold', parseFloat(e.target.value))}
                  className="w-full h-2 bg-white/10 rounded-lg appearance-none cursor-pointer accent-blue-500 hover:accent-blue-400 transition-colors"
                />
                <p className="text-xs text-gray-500">
                  Минимальная схожесть для включения результатов в контекст (0.0-1.0)
                </p>
              </div>
            )}
          </div>

          {/* Quality Settings */}
          <div className="border-t border-white/10 pt-6">
            <h3 className="text-sm font-medium text-gray-200 flex items-center gap-2 mb-4">
              <Target className="w-4 h-4 text-gray-400" />
              Качество кода
            </h3>
            
            <div className="space-y-2">
              <label className="block text-sm font-medium text-gray-200">
                Порог качества: <span className="text-blue-400 font-mono ml-1">{settings.qualityThreshold.toFixed(2)}</span>
              </label>
              <input
                type="range"
                min="0.0"
                max="1.0"
                step="0.05"
                value={settings.qualityThreshold}
                onChange={e => handleChange('qualityThreshold', parseFloat(e.target.value))}
                className="w-full h-2 bg-white/10 rounded-lg appearance-none cursor-pointer accent-blue-500 hover:accent-blue-400 transition-colors"
              />
              <p className="text-xs text-gray-500">
                Минимальный порог качества для успешного результата (0.0-1.0)
              </p>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex gap-3 p-6 border-t border-white/10 bg-gradient-to-b from-black/20 to-transparent">
          <button
            onClick={handleReset}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-white/10 hover:bg-white/20 text-white rounded-lg transition-colors text-sm font-medium"
          >
            <RotateCcw className="w-4 h-4" />
            Сброс
          </button>
          <button
            onClick={handleSave}
            disabled={!hasChanges}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:text-gray-500 disabled:cursor-not-allowed text-white rounded-lg transition-colors text-sm font-medium"
          >
            <Save className="w-4 h-4" />
            Сохранить
          </button>
        </div>
      </div>
    </div>
  )
}
