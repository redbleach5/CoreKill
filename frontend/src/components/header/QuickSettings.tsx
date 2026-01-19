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
    <div className="border-b border-white/5 bg-white/[0.02] px-6 py-4">
      <div className="max-w-2xl mx-auto flex flex-wrap gap-6 text-sm">
        <div className="flex items-center gap-3">
          <label className="text-gray-400">Температура</label>
          <input
            type="range"
            min="0.1"
            max="0.7"
            step="0.05"
            value={options.temperature}
            onChange={(e) => onOptionsChange({ ...options, temperature: parseFloat(e.target.value) })}
            className="w-24 accent-blue-500"
          />
          <span className="text-gray-300 font-mono w-10">{options.temperature.toFixed(2)}</span>
        </div>
        <div className="flex items-center gap-3">
          <label className="text-gray-400">Итерации</label>
          <input
            type="range"
            min="1"
            max="3"
            value={options.maxIterations}
            onChange={(e) => onOptionsChange({ ...options, maxIterations: parseInt(e.target.value) })}
            className="w-16 accent-blue-500"
          />
          <span className="text-gray-300 font-mono w-4">{options.maxIterations}</span>
        </div>
        <label className="flex items-center gap-2 text-gray-400 cursor-pointer">
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
          className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors"
        >
          <Sliders className="w-4 h-4" />
          Расширенные
        </button>
      </div>
    </div>
  )
}
