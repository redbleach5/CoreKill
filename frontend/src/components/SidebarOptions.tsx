import { useState, useEffect } from 'react'

export interface TaskOptions {
  model: string
  temperature: number
  disableWebSearch: boolean
  maxIterations: number
}

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
    <div className="space-y-6 p-4">
      <h2 className="text-lg font-semibold">Настройки</h2>

      <div>
        <label htmlFor="model" className="block text-sm font-medium mb-2">
          Модель Ollama:
        </label>
        <select
          id="model"
          value={options.model}
          onChange={handleModelChange}
          disabled={modelsLoading}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
        >
          {modelsLoading ? (
            <option>Загрузка моделей...</option>
          ) : availableModels.length > 0 ? (
            availableModels.map((model) => (
              <option key={model} value={model}>
                {model}
              </option>
            ))
          ) : (
            <option value={options.model}>{options.model}</option>
          )}
        </select>
      </div>

      <div>
        <label htmlFor="temperature" className="block text-sm font-medium mb-2">
          Температура: {options.temperature.toFixed(2)}
        </label>
        <input
          id="temperature"
          type="range"
          min="0.1"
          max="0.7"
          step="0.05"
          value={options.temperature}
          onChange={handleTemperatureChange}
          className="w-full"
        />
        <div className="flex justify-between text-xs text-gray-500 mt-1">
          <span>0.1</span>
          <span>0.7</span>
        </div>
      </div>

      <div className="flex items-center space-x-2">
        <input
          id="disableWebSearch"
          type="checkbox"
          checked={options.disableWebSearch}
          onChange={handleWebSearchToggle}
          className="w-4 h-4"
        />
        <label htmlFor="disableWebSearch" className="text-sm">
          Без веб-поиска
        </label>
      </div>

      <div>
        <label htmlFor="maxIterations" className="block text-sm font-medium mb-2">
          Макс. итераций: {options.maxIterations}
        </label>
        <input
          id="maxIterations"
          type="range"
          min="1"
          max="3"
          value={options.maxIterations}
          onChange={handleMaxIterationsChange}
          className="w-full"
        />
      </div>
    </div>
  )
}
