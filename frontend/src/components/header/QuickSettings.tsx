/**
 * Быстрые настройки (inline панель)
 */
import { Sliders } from 'lucide-react'
import { TaskOptions } from '../../hooks/useAgentStream'

interface QuickSettingsProps {
  options: TaskOptions
  onOptionsChange: (options: TaskOptions) => void
  onAdvancedClick: () => void
}

export function QuickSettings({ options, onOptionsChange, onAdvancedClick }: QuickSettingsProps) {
  return (
    <div className="border-b border-white/5 bg-white/[0.02] px-6 py-3 backdrop-blur-sm">
      <div className="max-w-4xl mx-auto flex items-center flex-wrap gap-4 text-sm">
        <div className="flex items-center gap-2 group">
          <label className="text-gray-400 whitespace-nowrap group-hover:text-gray-300 transition-colors">
            Температура
          </label>
          <input
            type="range"
            min="0.1"
            max="0.7"
            step="0.05"
            value={options.temperature}
            onChange={(e) => onOptionsChange({ ...options, temperature: parseFloat(e.target.value) })}
            className="w-20 accent-blue-500 hover:accent-blue-400 transition-colors cursor-pointer"
            title={`Температура: ${options.temperature.toFixed(2)}`}
          />
          <span className="text-gray-300 font-mono w-10 text-xs bg-white/5 px-1.5 py-0.5 rounded">
            {options.temperature.toFixed(2)}
          </span>
        </div>
        <div className="flex items-center gap-2 group">
          <label className="text-gray-400 whitespace-nowrap group-hover:text-gray-300 transition-colors">
            Итерации
          </label>
          <input
            type="range"
            min="1"
            max="3"
            value={options.maxIterations}
            onChange={(e) => onOptionsChange({ ...options, maxIterations: parseInt(e.target.value) })}
            className="w-14 accent-blue-500 hover:accent-blue-400 transition-colors cursor-pointer"
            title={`Максимум итераций: ${options.maxIterations}`}
          />
          <span className="text-gray-300 font-mono w-4 text-xs bg-white/5 px-1.5 py-0.5 rounded text-center">
            {options.maxIterations}
          </span>
        </div>
        <label className="flex items-center gap-1.5 text-gray-400 cursor-pointer whitespace-nowrap hover:text-gray-300 transition-colors group">
          <input
            type="checkbox"
            checked={options.disableWebSearch}
            onChange={(e) => onOptionsChange({ ...options, disableWebSearch: e.target.checked })}
            className="accent-blue-500 cursor-pointer"
          />
          <span className="text-xs">Без веб-поиска</span>
        </label>
        <button
          onClick={onAdvancedClick}
          className="flex items-center gap-1.5 text-gray-400 hover:text-white transition-all duration-200 whitespace-nowrap ml-auto 
                     hover:bg-white/5 px-2 py-1 rounded-lg"
          title="Расширенные настройки"
        >
          <Sliders className="w-3.5 h-3.5" />
          <span className="text-xs">Расширенные</span>
        </button>
      </div>
    </div>
  )
}
