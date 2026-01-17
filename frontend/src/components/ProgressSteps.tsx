import { StageStatus } from '../hooks/useAgentStream'

interface ProgressStepsProps {
  stages: Record<string, StageStatus>
}

const stageLabels: Record<string, string> = {
  intent: 'Определение намерения',
  planning: 'Планирование',
  research: 'Исследование',
  testing: 'Генерация тестов',
  coding: 'Генерация кода',
  validation: 'Валидация',
  reflection: 'Рефлексия'
}

const stageIcons: Record<string, string> = {
  intent: '🔍',
  planning: '📋',
  research: '📚',
  testing: '🧪',
  coding: '💻',
  validation: '🔍',
  reflection: '🤔'
}

export function ProgressSteps({ stages }: ProgressStepsProps) {
  const stageOrder = ['intent', 'planning', 'research', 'testing', 'coding', 'validation', 'reflection']

  const getStageStatus = (stage: string): 'idle' | 'active' | 'completed' | 'error' => {
    const stageData = stages[stage]
    if (!stageData || stageData.status === 'idle') return 'idle'
    if (stageData.status === 'error') return 'error'
    if (stageData.status === 'end') return 'completed'
    return 'active'
  }

  return (
    <div className="space-y-3">
      <h3 className="text-lg font-semibold mb-4">Прогресс выполнения</h3>
      {stageOrder.map((stage, index) => {
        const status = getStageStatus(stage)
        const stageData = stages[stage]
        const label = stageLabels[stage] || stage
        const icon = stageIcons[stage] || '•'

        return (
          <div key={stage} className="flex items-start space-x-3">
            <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-sm ${
              status === 'completed' ? 'bg-green-500 text-white' :
              status === 'active' ? 'bg-blue-500 text-white animate-pulse' :
              status === 'error' ? 'bg-red-500 text-white' :
              'bg-gray-300 text-gray-600'
            }`}>
              {status === 'completed' ? '✓' : icon}
            </div>
            <div className="flex-1 min-w-0">
              <div className={`text-sm font-medium ${
                status === 'active' ? 'text-blue-600' :
                status === 'completed' ? 'text-green-600' :
                status === 'error' ? 'text-red-600' :
                'text-gray-500'
              }`}>
                {label}
              </div>
              {stageData && stageData.message && (
                <div className="text-xs text-gray-600 mt-1">
                  {stageData.message}
                </div>
              )}
              {stageData && stageData.progress !== undefined && (
                <div className="mt-2">
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div
                      className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                      style={{ width: `${stageData.progress * 100}%` }}
                    />
                  </div>
                </div>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
