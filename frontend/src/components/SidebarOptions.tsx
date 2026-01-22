import { useState, useEffect } from 'react'
import { Zap } from 'lucide-react'
import { TaskOptions } from '../hooks/useAgentStream'
import { formatModelName, isReasoningModelSync } from '../utils/modelUtils'

export type { TaskOptions }

interface SidebarOptionsProps {
  options: TaskOptions
  onChange: (options: TaskOptions) => void
}

export function SidebarOptions({ options, onChange }: SidebarOptionsProps) {
  const [availableModels, setAvailableModels] = useState<string[]>([])
  const [modelsLoading, setModelsLoading] = useState(true)

  useEffect(() => {
    const fetchModels = async () => {
      try {
        const response = await fetch('/api/models')
        if (response.ok) {
          const data = await response.json()
          const models = data.models || []
          setAvailableModels(models)
          
          // Если текущая модель пуста или не в списке доступных, выбираем первую доступную
          if (models.length > 0) {
            if (!options.model || !models.includes(options.model)) {
              onChange({ ...options, model: models[0] })
            }
          }
        }
      } catch (error) {
        console.error('Ошибка загрузки моделей:', error)
        // Если не удалось загрузить модели, оставляем пустой список
        // Пользователь увидит текущую модель в селекте
        setAvailableModels([])
      } finally {
        setModelsLoading(false)
      }
    }

    fetchModels()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleModelChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    onChange({ ...options, model: e.target.value })
  }

  const handleTemperatureChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange({ ...options, temperature: parseFloat(e.target.value) })
  }

  const handleWebSearchToggle = (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange({ ...options, disableWebSearch: e.target.checked })
  }

  const handleMaxIterationsChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange({ ...options, maxIterations: parseInt(e.target.value) })
  }

  return (
    <div className="space-y-6 p-4 animate-fade-in">
      <h2 className="text-lg font-semibold text-gray-100">Настройки</h2>

      <div>
        <label htmlFor="model" className="block text-sm font-medium mb-2 text-gray-300 flex items-center gap-2">
          Модель Ollama:
          {options.model && isReasoningModelSync(options.model) && (
            <Zap className="w-4 h-4 text-gray-400" title="Reasoning модель (поддерживает размышления)" />
          )}
        </label>
        <div className="relative">
          <select
            id="model"
            value={options.model}
            onChange={handleModelChange}
            disabled={modelsLoading}
            className="w-full px-3 py-2 pr-8 bg-gray-700 border border-gray-600 text-gray-100 rounded-lg 
                       focus:ring-2 focus:ring-blue-500 focus:border-blue-500
                       disabled:bg-gray-800 disabled:text-gray-500 disabled:cursor-not-allowed
                       transition-all duration-200 appearance-none"
          >
            {modelsLoading ? (
              <option>Загрузка моделей...</option>
            ) : availableModels.length > 0 ? (
              availableModels.map((model) => (
                <option key={model} value={model}>
                  {formatModelName(model)}
                </option>
              ))
            ) : (
              <option value={options.model}>{formatModelName(options.model)}</option>
            )}
          </select>
          {/* Иконка Zap для reasoning моделей в селекте (из Tool Calls) */}
          {options.model && isReasoningModelSync(options.model) && (
            <div className="absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none">
              <Zap className="w-4 h-4 text-gray-400" />
            </div>
          )}
        </div>
        {options.model && isReasoningModelSync(options.model) && (
          <p className="text-xs text-gray-400 mt-1">
            Reasoning модель: показывает процесс размышления
          </p>
        )}
      </div>

      <div>
        <label htmlFor="temperature" className="block text-sm font-medium mb-2 text-gray-300">
          Температура: <span className="text-blue-400 font-mono">{options.temperature.toFixed(2)}</span>
        </label>
        <input
          id="temperature"
          type="range"
          min="0.1"
          max="0.7"
          step="0.05"
          value={options.temperature}
          onChange={handleTemperatureChange}
          className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer
                     [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 
                     [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:bg-blue-500 
                     [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:cursor-pointer
                     [&::-webkit-slider-thumb]:transition-all [&::-webkit-slider-thumb]:hover:bg-blue-400
                     [&::-webkit-slider-thumb]:hover:scale-110"
        />
        <div className="flex justify-between text-xs text-gray-500 mt-1">
          <span>Точнее</span>
          <span>Креативнее</span>
        </div>
      </div>

      <div className="flex items-center space-x-3">
        <div className="relative">
          <input
            id="disableWebSearch"
            type="checkbox"
            checked={options.disableWebSearch}
            onChange={handleWebSearchToggle}
            className="sr-only peer"
          />
          <div className="w-10 h-5 bg-gray-700 rounded-full peer 
                          peer-checked:bg-blue-600 peer-checked:after:translate-x-5
                          after:content-[''] after:absolute after:top-0.5 after:left-0.5 
                          after:bg-white after:rounded-full after:h-4 after:w-4 
                          after:transition-all cursor-pointer" 
               onClick={() => handleWebSearchToggle({ target: { checked: !options.disableWebSearch } } as any)}
          />
        </div>
        <label htmlFor="disableWebSearch" className="text-sm text-gray-300 cursor-pointer">
          Без веб-поиска
        </label>
      </div>

      <div>
        <label htmlFor="maxIterations" className="block text-sm font-medium mb-2 text-gray-300">
          Макс. итераций: <span className="text-blue-400 font-mono">{options.maxIterations}</span>
        </label>
        <input
          id="maxIterations"
          type="range"
          min="1"
          max="3"
          value={options.maxIterations}
          onChange={handleMaxIterationsChange}
          className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer
                     [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 
                     [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:bg-blue-500 
                     [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:cursor-pointer
                     [&::-webkit-slider-thumb]:transition-all [&::-webkit-slider-thumb]:hover:bg-blue-400
                     [&::-webkit-slider-thumb]:hover:scale-110"
        />
        <div className="flex justify-between text-xs text-gray-500 mt-1">
          <span>1</span>
          <span>2</span>
          <span>3</span>
        </div>
      </div>
    </div>
  )
}
