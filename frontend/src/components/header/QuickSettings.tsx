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
    <div className="border-b border-white/5 bg-white/[0.02] px-6 py-3">
      <div className="max-w-4xl mx-auto flex items-center flex-wrap gap-4 text-sm">
        <div className="flex items-center gap-2">
          <label className="text-gray-400 whitespace-nowrap">Температура</label>
          <input
            type="range"
            min="0.1"
            max="0.7"
            step="0.05"
            value={options.temperature}
            onChange={(e) => onOptionsChange({ ...options, temperature: parseFloat(e.target.value) })}
            className="w-20 accent-blue-500"
          />
          <span className="text-gray-300 font-mono w-10 text-xs">{options.temperature.toFixed(2)}</span>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-gray-400 whitespace-nowrap">Итерации</label>
          <input
            type="range"
            min="1"
            max="3"
            value={options.maxIterations}
            onChange={(e) => onOptionsChange({ ...options, maxIterations: parseInt(e.target.value) })}
            className="w-14 accent-blue-500"
          />
          <span className="text-gray-300 font-mono w-4 text-xs">{options.maxIterations}</span>
        </div>
        <label className="flex items-center gap-1.5 text-gray-400 cursor-pointer whitespace-nowrap">
          <input
            type="checkbox"
            checked={options.disableWebSearch}
            onChange={(e) => onOptionsChange({ ...options, disableWebSearch: e.target.checked })}
            className="accent-blue-500"
          />
          Без веб-поиска
        </label>
        <button
          onClick={onAdvancedClick}
          className="flex items-center gap-1.5 text-gray-400 hover:text-white transition-colors whitespace-nowrap ml-auto"
        >
          <Sliders className="w-3.5 h-3.5" />
          <span className="text-xs">Расширенные</span>
        </button>
      </div>
    </div>
  )
}
