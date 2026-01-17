import { useState } from 'react'
import { AgentResults, Metrics } from '../hooks/useAgentStream'

interface ResultDisplayProps {
  results: AgentResults
  metrics: Metrics
  task: string
  onFeedback?: (feedback: 'positive' | 'negative') => void
}

export function ResultDisplay({ results, metrics, task, onFeedback }: ResultDisplayProps) {
  const [activeTab, setActiveTab] = useState<'task' | 'tests' | 'code' | 'reflection' | 'errors'>('task')

  const handleCopyCode = () => {
    if (results.code) {
      navigator.clipboard.writeText(results.code)
      alert('Код скопирован в буфер обмена')
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
    }
  }

  const tabs = [
    { id: 'task', label: 'Задача' },
    { id: 'tests', label: 'Тесты' },
    { id: 'code', label: 'Код' },
    { id: 'reflection', label: 'Рефлексия' },
    { id: 'errors', label: 'Ошибки' }
  ]

  const hasErrors = results.validation && (
    !results.validation.pytest?.success ||
    !results.validation.mypy?.success ||
    !results.validation.bandit?.success
  )

  return (
    <div className="space-y-4">
      <div className="border-b border-gray-200">
        <nav className="flex space-x-4">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.id
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      <div className="mt-4">
        {activeTab === 'task' && (
          <div className="space-y-4">
            <div>
              <h4 className="font-medium mb-2">Исходная задача:</h4>
              <p className="text-gray-700 whitespace-pre-wrap">{results.task}</p>
            </div>
            {results.intent && (
              <div>
                <h4 className="font-medium mb-2">Намерение:</h4>
                <p className="text-gray-700">
                  {results.intent.type} (уверенность: {results.intent.confidence.toFixed(2)})
                </p>
              </div>
            )}
          </div>
        )}

        {activeTab === 'tests' && (
          <div>
            <h4 className="font-medium mb-2">Сгенерированные тесты:</h4>
            <pre className="bg-gray-50 p-4 rounded-lg overflow-x-auto text-sm">
              <code>{results.tests || 'Тесты не сгенерированы'}</code>
            </pre>
          </div>
        )}

        {activeTab === 'code' && (
          <div className="space-y-4">
            <div className="flex space-x-2">
              <button
                onClick={handleCopyCode}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                disabled={!results.code}
              >
                Копировать код
              </button>
              <button
                onClick={handleSaveFile}
                className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
                disabled={!results.code}
              >
                Сохранить в файл
              </button>
            </div>
            <pre className="bg-gray-900 text-green-400 p-4 rounded-lg overflow-x-auto text-sm">
              <code>{results.code || 'Код не сгенерирован'}</code>
            </pre>
          </div>
        )}

        {activeTab === 'reflection' && (
          <div className="space-y-4">
            <div>
              <h4 className="font-medium mb-4">Оценка системы:</h4>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-sm text-gray-600">Planning:</div>
                  <div className="text-2xl font-bold">{metrics.planning.toFixed(2)}</div>
                </div>
                <div>
                  <div className="text-sm text-gray-600">Research:</div>
                  <div className="text-2xl font-bold">{metrics.research.toFixed(2)}</div>
                </div>
                <div>
                  <div className="text-sm text-gray-600">Testing:</div>
                  <div className="text-2xl font-bold">{metrics.testing.toFixed(2)}</div>
                </div>
                <div>
                  <div className="text-sm text-gray-600">Coding:</div>
                  <div className="text-2xl font-bold">{metrics.coding.toFixed(2)}</div>
                </div>
              </div>
              <div className="mt-4">
                <div className="text-sm text-gray-600">Overall:</div>
                <div className="text-3xl font-bold">{metrics.overall.toFixed(2)}</div>
              </div>
            </div>
            {onFeedback && (
              <div className="mt-6 pt-4 border-t border-gray-200">
                <div className="text-sm font-medium mb-2">Оцените результат:</div>
                <div className="flex space-x-4">
                  <button
                    onClick={() => onFeedback('positive')}
                    className="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 flex items-center space-x-2"
                  >
                    <span>👍</span>
                    <span>Хорошо</span>
                  </button>
                  <button
                    onClick={() => onFeedback('negative')}
                    className="px-6 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 flex items-center space-x-2"
                  >
                    <span>👎</span>
                    <span>Плохо</span>
                  </button>
                </div>
              </div>
            )}
            {results.reflection && (
              <div className="space-y-2">
                <div>
                  <h5 className="font-medium">Анализ:</h5>
                  <p className="text-sm text-gray-700 whitespace-pre-wrap">{results.reflection.analysis}</p>
                </div>
                <div>
                  <h5 className="font-medium">Улучшения:</h5>
                  <p className="text-sm text-gray-700 whitespace-pre-wrap">{results.reflection.improvements}</p>
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'errors' && (
          <div className="space-y-4">
            {hasErrors ? (
              <div className="space-y-2">
                {results.validation?.pytest && !results.validation.pytest.success && (
                  <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
                    <h5 className="font-medium text-red-800 mb-2">pytest ошибки:</h5>
                    <pre className="text-sm text-red-700 whitespace-pre-wrap">
                      {results.validation.pytest.output?.substring(0, 500)}
                    </pre>
                  </div>
                )}
                {results.validation?.mypy && !results.validation.mypy.success && (
                  <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
                    <h5 className="font-medium text-red-800 mb-2">mypy ошибки:</h5>
                    <pre className="text-sm text-red-700 whitespace-pre-wrap">
                      {results.validation.mypy.errors?.substring(0, 500)}
                    </pre>
                  </div>
                )}
                {results.validation?.bandit && !results.validation.bandit.success && (
                  <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
                    <h5 className="font-medium text-red-800 mb-2">bandit проблемы:</h5>
                    <pre className="text-sm text-red-700 whitespace-pre-wrap">
                      {results.validation.bandit.issues?.substring(0, 500)}
                    </pre>
                  </div>
                )}
              </div>
            ) : (
              <div className="p-4 bg-green-50 border border-green-200 rounded-lg text-green-800">
                Ошибок не найдено! Все проверки пройдены.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
