import { useState } from 'react'
import { AgentResults, Metrics } from '../hooks/useAgentStream'
import { Copy, Download, ThumbsUp, ThumbsDown, CheckCircle2, AlertTriangle, FileText, TestTube, Code2, Brain, AlertCircle } from 'lucide-react'

interface ResultDisplayProps {
  results: AgentResults
  metrics: Metrics
  task: string
  onFeedback?: (feedback: 'positive' | 'negative') => void
}

// Простой toast менеджер
let toastContainer: HTMLDivElement | null = null

function showToast(message: string, type: 'success' | 'error' = 'success') {
  if (!toastContainer) {
    toastContainer = document.createElement('div')
    toastContainer.className = 'toast-container'
    document.body.appendChild(toastContainer)
  }
  
  const toast = document.createElement('div')
  toast.className = `toast toast-${type}`
  toast.textContent = message
  toastContainer.appendChild(toast)
  
  setTimeout(() => {
    toast.style.opacity = '0'
    toast.style.transform = 'translateX(20px)'
    toast.style.transition = 'all 0.3s ease-out'
    setTimeout(() => toast.remove(), 300)
  }, 3000)
}

export function ResultDisplay({ results, metrics, task: _task, onFeedback }: ResultDisplayProps) {
  const [activeTab, setActiveTab] = useState<'task' | 'tests' | 'code' | 'reflection' | 'errors'>('task')
  const [copiedCode, setCopiedCode] = useState(false)

  const handleCopyCode = async () => {
    if (results.code) {
      try {
        await navigator.clipboard.writeText(results.code)
        setCopiedCode(true)
        showToast('Код скопирован в буфер обмена', 'success')
        setTimeout(() => setCopiedCode(false), 2000)
      } catch {
        showToast('Не удалось скопировать код', 'error')
      }
    }
  }

  const handleSaveFile = () => {
    if (results.code) {
      const blob = new Blob([results.code], { type: 'text/plain' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'generated_code.py'
      a.click()
      URL.revokeObjectURL(url)
      showToast('Файл сохранён', 'success')
    }
  }

  const tabs = [
    { id: 'task', label: 'Задача', icon: FileText },
    { id: 'tests', label: 'Тесты', icon: TestTube },
    { id: 'code', label: 'Код', icon: Code2 },
    { id: 'reflection', label: 'Рефлексия', icon: Brain },
    { id: 'errors', label: 'Ошибки', icon: AlertCircle }
  ]

  const hasErrors = results.validation && (
    !results.validation.pytest?.success ||
    !results.validation.mypy?.success ||
    !results.validation.bandit?.success
  )

  // Функция для определения цвета скора
  const getScoreColor = (score: number) => {
    if (score >= 0.8) return 'text-green-400'
    if (score >= 0.5) return 'text-yellow-400'
    return 'text-red-400'
  }

  const getScoreBg = (score: number) => {
    if (score >= 0.8) return 'bg-green-500/20'
    if (score >= 0.5) return 'bg-yellow-500/20'
    return 'bg-red-500/20'
  }

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Улучшенные табы */}
      <div className="border-b border-gray-700">
        <nav className="flex space-x-1 overflow-x-auto">
          {tabs.map(tab => {
            const Icon = tab.icon
            const isActive = activeTab === tab.id
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-all duration-200 whitespace-nowrap ${
                  isActive
                    ? 'border-blue-500 text-blue-400 bg-blue-500/10'
                    : 'border-transparent text-gray-400 hover:text-gray-200 hover:bg-gray-800/50'
                }`}
              >
                <Icon className="w-4 h-4" />
                {tab.label}
                {tab.id === 'errors' && hasErrors && (
                  <span className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />
                )}
              </button>
            )
          })}
        </nav>
      </div>

      <div className="mt-4">
        {activeTab === 'task' && (
          <div className="space-y-4 animate-fade-in">
            <div className="p-4 bg-gray-800/50 rounded-lg border border-gray-700">
              <h4 className="font-medium mb-2 text-gray-200">Исходная задача:</h4>
              <p className="text-gray-300 whitespace-pre-wrap">{results.task}</p>
            </div>
            {results.intent && (
              <div className="p-4 bg-gray-800/50 rounded-lg border border-gray-700">
                <h4 className="font-medium mb-2 text-gray-200">Намерение:</h4>
                <div className="flex items-center gap-3">
                  <span className="px-3 py-1 bg-blue-500/20 text-blue-300 rounded-full text-sm">
                    {results.intent.type}
                  </span>
                  <div className="flex items-center gap-2">
                    <span className="text-gray-400 text-sm">Уверенность:</span>
                    <div className="w-24 h-2 bg-gray-700 rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-gradient-to-r from-blue-500 to-blue-400 rounded-full transition-all duration-500"
                        style={{ width: `${results.intent.confidence * 100}%` }}
                      />
                    </div>
                    <span className="text-blue-400 font-mono text-sm">
                      {(results.intent.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'tests' && (
          <div className="animate-fade-in">
            <h4 className="font-medium mb-3 text-gray-200">Сгенерированные тесты:</h4>
            <pre className="bg-gray-900 border border-gray-700 p-4 rounded-lg overflow-x-auto text-sm">
              <code className="text-green-400">{results.tests || 'Тесты не сгенерированы'}</code>
            </pre>
          </div>
        )}

        {activeTab === 'code' && (
          <div className="space-y-4 animate-fade-in">
            <div className="flex gap-2">
              <button
                onClick={handleCopyCode}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-all duration-200 ${
                  copiedCode 
                    ? 'bg-green-600 text-white' 
                    : 'bg-blue-600 text-white hover:bg-blue-700'
                } disabled:opacity-50 disabled:cursor-not-allowed`}
                disabled={!results.code}
              >
                {copiedCode ? <CheckCircle2 className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                {copiedCode ? 'Скопировано!' : 'Копировать'}
              </button>
              <button
                onClick={handleSaveFile}
                className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={!results.code}
              >
                <Download className="w-4 h-4" />
                Сохранить
              </button>
            </div>
            <pre className="bg-gray-900 border border-gray-700 p-4 rounded-lg overflow-x-auto text-sm">
              <code className="text-green-400">{results.code || 'Код не сгенерирован'}</code>
            </pre>
          </div>
        )}

        {activeTab === 'reflection' && (
          <div className="space-y-6 animate-fade-in">
            <div className="p-4 bg-gray-800/50 rounded-lg border border-gray-700">
              <h4 className="font-medium mb-4 text-gray-200">Оценка качества:</h4>
              <div className="grid grid-cols-2 gap-4">
                {[
                  { label: 'Планирование', value: metrics.planning },
                  { label: 'Исследование', value: metrics.research },
                  { label: 'Тестирование', value: metrics.testing },
                  { label: 'Кодирование', value: metrics.coding }
                ].map(({ label, value }) => (
                  <div key={label} className={`p-3 rounded-lg ${getScoreBg(value)}`}>
                    <div className="text-xs text-gray-400 mb-1">{label}</div>
                    <div className={`text-2xl font-bold font-mono ${getScoreColor(value)}`}>
                      {value.toFixed(2)}
                    </div>
                  </div>
                ))}
              </div>
              <div className={`mt-4 p-4 rounded-lg ${getScoreBg(metrics.overall)} text-center`}>
                <div className="text-sm text-gray-400 mb-1">Общий результат</div>
                <div className={`text-4xl font-bold font-mono ${getScoreColor(metrics.overall)}`}>
                  {metrics.overall.toFixed(2)}
                </div>
              </div>
            </div>
            
            {onFeedback && (
              <div className="p-4 bg-gray-800/50 rounded-lg border border-gray-700">
                <div className="text-sm font-medium mb-3 text-gray-200">Оцените результат:</div>
                <div className="flex gap-3">
                  <button
                    onClick={() => {
                      onFeedback('positive')
                      showToast('Спасибо за положительный отзыв!', 'success')
                    }}
                    className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-green-600/20 text-green-400 border border-green-600/50 rounded-lg hover:bg-green-600/30 transition-all duration-200"
                  >
                    <ThumbsUp className="w-5 h-5" />
                    Хорошо
                  </button>
                  <button
                    onClick={() => {
                      onFeedback('negative')
                      showToast('Спасибо за отзыв, учтём!', 'success')
                    }}
                    className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-red-600/20 text-red-400 border border-red-600/50 rounded-lg hover:bg-red-600/30 transition-all duration-200"
                  >
                    <ThumbsDown className="w-5 h-5" />
                    Плохо
                  </button>
                </div>
              </div>
            )}
            
            {results.reflection && (
              <div className="space-y-4">
                <div className="p-4 bg-gray-800/50 rounded-lg border border-gray-700">
                  <h5 className="font-medium text-gray-200 mb-2">Анализ:</h5>
                  <p className="text-sm text-gray-300 whitespace-pre-wrap">{results.reflection.analysis}</p>
                </div>
                <div className="p-4 bg-gray-800/50 rounded-lg border border-gray-700">
                  <h5 className="font-medium text-gray-200 mb-2">Предложения по улучшению:</h5>
                  <p className="text-sm text-gray-300 whitespace-pre-wrap">{results.reflection.improvements}</p>
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'errors' && (
          <div className="space-y-4 animate-fade-in">
            {hasErrors ? (
              <div className="space-y-3">
                {results.validation?.pytest && !results.validation.pytest.success && (
                  <div className="p-4 bg-red-900/20 border border-red-800/50 rounded-lg">
                    <div className="flex items-center gap-2 mb-2">
                      <AlertTriangle className="w-4 h-4 text-red-400" />
                      <h5 className="font-medium text-red-300">pytest ошибки:</h5>
                    </div>
                    <pre className="text-sm text-red-400 whitespace-pre-wrap overflow-x-auto">
                      {results.validation.pytest.output?.substring(0, 500)}
                    </pre>
                  </div>
                )}
                {results.validation?.mypy && !results.validation.mypy.success && (
                  <div className="p-4 bg-red-900/20 border border-red-800/50 rounded-lg">
                    <div className="flex items-center gap-2 mb-2">
                      <AlertTriangle className="w-4 h-4 text-red-400" />
                      <h5 className="font-medium text-red-300">mypy ошибки:</h5>
                    </div>
                    <pre className="text-sm text-red-400 whitespace-pre-wrap overflow-x-auto">
                      {results.validation.mypy.errors?.substring(0, 500)}
                    </pre>
                  </div>
                )}
                {results.validation?.bandit && !results.validation.bandit.success && (
                  <div className="p-4 bg-yellow-900/20 border border-yellow-800/50 rounded-lg">
                    <div className="flex items-center gap-2 mb-2">
                      <AlertTriangle className="w-4 h-4 text-yellow-400" />
                      <h5 className="font-medium text-yellow-300">bandit предупреждения:</h5>
                    </div>
                    <pre className="text-sm text-yellow-400 whitespace-pre-wrap overflow-x-auto">
                      {results.validation.bandit.issues?.substring(0, 500)}
                    </pre>
                  </div>
                )}
              </div>
            ) : (
              <div className="p-6 bg-green-900/20 border border-green-800/50 rounded-lg text-center">
                <CheckCircle2 className="w-12 h-12 text-green-400 mx-auto mb-3" />
                <p className="text-green-300 font-medium">Все проверки пройдены!</p>
                <p className="text-green-400/70 text-sm mt-1">Ошибок не обнаружено</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
