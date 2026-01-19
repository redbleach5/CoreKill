/**
 * Улучшенный компонент для отображения результатов генерации кода
 */
import { useState } from 'react'
import { Copy, Download, FileCode, TestTube, Zap, AlertCircle, CheckCircle2 } from 'lucide-react'

interface ResultMetrics {
  quality: number
  coverage: number
  complexity: number
  executionTime: number
}

interface EnhancedResultDisplayProps {
  code: string
  tests?: string
  metrics?: ResultMetrics
  stages?: Record<string, any>
  onCopy?: (text: string) => void
  onDownload?: (text: string, filename: string) => void
}

export function EnhancedResultDisplay({
  code,
  tests,
  metrics,
  stages,
  onCopy,
  onDownload
}: EnhancedResultDisplayProps) {
  const [activeTab, setActiveTab] = useState<'code' | 'tests' | 'metrics'>('code')
  const [showLineNumbers, setShowLineNumbers] = useState(true)

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text)
    onCopy?.(text)
  }

  const handleDownload = (text: string, filename: string) => {
    const element = document.createElement('a')
    const file = new Blob([text], { type: 'text/plain' })
    element.href = URL.createObjectURL(file)
    element.download = filename
    document.body.appendChild(element)
    element.click()
    document.body.removeChild(element)
    onDownload?.(text, filename)
  }

  const renderCodeBlock = (codeText: string, language: string = 'python') => (
    <div className="bg-[#0d1117] border border-white/10 rounded-lg overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 bg-white/5 border-b border-white/10">
        <div className="flex items-center gap-2">
          <FileCode className="w-4 h-4 text-gray-400" />
          <span className="text-sm text-gray-400">{language}</span>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setShowLineNumbers(!showLineNumbers)}
            className="p-1.5 text-gray-400 hover:text-white hover:bg-white/10 rounded transition-colors"
            title="Показать/скрыть номера строк"
          >
            {showLineNumbers ? '№' : '|'}
          </button>
          <button
            onClick={() => handleCopy(codeText)}
            className="p-1.5 text-gray-400 hover:text-white hover:bg-white/10 rounded transition-colors"
            title="Копировать"
          >
            <Copy className="w-4 h-4" />
          </button>
          <button
            onClick={() => handleDownload(codeText, `code.${language === 'python' ? 'py' : 'js'}`)}
            className="p-1.5 text-gray-400 hover:text-white hover:bg-white/10 rounded transition-colors"
            title="Скачать"
          >
            <Download className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Code */}
      <div className="overflow-x-auto">
        <pre className="p-4 text-sm font-mono text-gray-300">
          {showLineNumbers && (
            <div className="inline-block mr-4 text-gray-600 select-none">
              {codeText.split('\n').map((_, i) => (
                <div key={i}>{i + 1}</div>
              ))}
            </div>
          )}
          <code>{codeText}</code>
        </pre>
      </div>
    </div>
  )

  const renderMetrics = () => {
    if (!metrics) return null

    const getMetricColor = (value: number) => {
      if (value >= 0.8) return 'text-emerald-400'
      if (value >= 0.6) return 'text-amber-400'
      return 'text-red-400'
    }

    const MetricCard = ({ label, value, unit = '%' }: { label: string; value: number; unit?: string }) => (
      <div className="bg-white/5 border border-white/10 rounded-lg p-4">
        <p className="text-xs text-gray-500 mb-2">{label}</p>
        <div className="flex items-baseline gap-2">
          <span className={`text-2xl font-bold ${getMetricColor(value / 100)}`}>
            {Math.round(value)}
          </span>
          <span className="text-xs text-gray-500">{unit}</span>
        </div>
        <div className="mt-2 h-1.5 bg-white/10 rounded-full overflow-hidden">
          <div
            className={`h-full ${
              value >= 0.8 ? 'bg-emerald-500' :
              value >= 0.6 ? 'bg-amber-500' :
              'bg-red-500'
            }`}
            style={{ width: `${value}%` }}
          />
        </div>
      </div>
    )

    return (
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <MetricCard label="Качество" value={metrics.quality * 100} />
          <MetricCard label="Покрытие тестами" value={metrics.coverage * 100} />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <MetricCard label="Сложность" value={(1 - metrics.complexity) * 100} />
          <MetricCard label="Время выполнения" value={Math.min(metrics.executionTime * 100, 100)} unit="ms" />
        </div>

        {/* Stages */}
        {stages && Object.keys(stages).length > 0 && (
          <div className="bg-white/5 border border-white/10 rounded-lg p-4">
            <p className="text-xs font-medium text-gray-300 mb-3">Этапы выполнения</p>
            <div className="space-y-2">
              {Object.entries(stages).map(([stage, data]: [string, any]) => (
                <div key={stage} className="flex items-center justify-between text-xs">
                  <span className="text-gray-400">{stage}</span>
                  <div className="flex items-center gap-2">
                    {data.success ? (
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    ) : (
                      <AlertCircle className="w-3.5 h-3.5 text-red-400" />
                    )}
                    <span className="text-gray-500">{data.duration || 0}ms</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full bg-[#0a0a0f] rounded-xl border border-white/10 overflow-hidden">
      {/* Tabs */}
      <div className="flex-shrink-0 flex items-center border-b border-white/10 bg-white/5">
        <button
          onClick={() => setActiveTab('code')}
          className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 text-sm font-medium transition-colors border-b-2 ${
            activeTab === 'code'
              ? 'text-blue-400 border-blue-500'
              : 'text-gray-400 border-transparent hover:text-gray-300'
          }`}
        >
          <FileCode className="w-4 h-4" />
          Код
        </button>
        {tests && (
          <button
            onClick={() => setActiveTab('tests')}
            className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 text-sm font-medium transition-colors border-b-2 ${
              activeTab === 'tests'
                ? 'text-blue-400 border-blue-500'
                : 'text-gray-400 border-transparent hover:text-gray-300'
            }`}
          >
            <TestTube className="w-4 h-4" />
            Тесты
          </button>
        )}
        {metrics && (
          <button
            onClick={() => setActiveTab('metrics')}
            className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 text-sm font-medium transition-colors border-b-2 ${
              activeTab === 'metrics'
                ? 'text-blue-400 border-blue-500'
                : 'text-gray-400 border-transparent hover:text-gray-300'
            }`}
          >
            <Zap className="w-4 h-4" />
            Метрики
          </button>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {activeTab === 'code' && renderCodeBlock(code)}
        {activeTab === 'tests' && tests && renderCodeBlock(tests, 'python')}
        {activeTab === 'metrics' && renderMetrics()}
      </div>
    </div>
  )
}
