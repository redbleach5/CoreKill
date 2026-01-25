import { StageStatus } from '../hooks/useAgentStream'
import { CheckCircle2, Circle, Loader2, XCircle, Brain, FileSearch, TestTube, Code2, Shield, RefreshCw, ListTodo } from 'lucide-react'
import { ThinkingBlock } from './ThinkingBlock'

interface ProgressStepsProps {
  stages: Record<string, StageStatus>
}

const stageConfig: Record<string, { label: string; icon: typeof Circle }> = {
  intent: { label: 'Анализ намерения', icon: Brain },
  planning: { label: 'Планирование', icon: ListTodo },
  research: { label: 'Исследование', icon: FileSearch },
  testing: { label: 'Генерация тестов', icon: TestTube },
  coding: { label: 'Генерация кода', icon: Code2 },
  validation: { label: 'Валидация', icon: Shield },
  reflection: { label: 'Рефлексия', icon: RefreshCw }
}

const stageOrder = ['intent', 'planning', 'research', 'testing', 'coding', 'validation', 'reflection']

export function ProgressSteps({ stages }: ProgressStepsProps) {
  const getStageStatus = (stage: string): 'idle' | 'active' | 'completed' | 'error' => {
    const stageData = stages[stage]
    if (!stageData || stageData.status === 'idle') return 'idle'
    if (stageData.status === 'error') return 'error'
    if (stageData.status === 'end') return 'completed'
    return 'active'
  }

  const getStatusLabel = (status: 'idle' | 'active' | 'completed' | 'error'): string => {
    switch (status) {
      case 'active':
        return 'Выполняется...'
      case 'completed':
        return 'Готово'
      case 'error':
        return 'Ошибка'
      default:
        return 'Ожидание'
    }
  }

  const getStageProgress = (stage: string): number => {
    const stageData = stages[stage]
    return stageData?.progress || 0
  }

  return (
    <div className="relative">
      {stageOrder.map((stage, index) => {
        const status = getStageStatus(stage)
        const config = stageConfig[stage]
        const Icon = config?.icon || Circle
        const progress = getStageProgress(stage)
        const isLast = index === stageOrder.length - 1

        return (
          <div key={stage} className="relative">
            {/* Вертикальная линия соединения */}
            {!isLast && (
              <div className="absolute left-[15px] top-[36px] w-[2px] h-[calc(100%-8px)]">
                <div 
                  className={`w-full h-full transition-all duration-500 ${
                    status === 'completed' ? 'bg-green-500' :
                    status === 'active' ? 'bg-gradient-to-b from-blue-500 to-gray-600' :
                    'bg-gray-700'
                  }`}
                />
              </div>
            )}
            
            <div className={`flex items-start gap-4 py-3 px-2 rounded-lg transition-all duration-300 ${
              status === 'active' ? 'bg-blue-500/10 border border-blue-500/30' : ''
            }`}>
              {/* Иконка статуса */}
              <div className={`relative flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center transition-all duration-300 ${
                status === 'active' ? 'bg-blue-500/20 ring-2 ring-blue-500 ring-offset-2 ring-offset-gray-900' :
                status === 'completed' ? 'bg-green-500/20' :
                status === 'error' ? 'bg-red-500/20' :
                'bg-gray-700/50'
              }`}>
                {status === 'active' ? (
                  <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />
                ) : status === 'completed' ? (
                  <CheckCircle2 className="w-4 h-4 text-green-400" />
                ) : status === 'error' ? (
                  <XCircle className="w-4 h-4 text-red-400" />
                ) : (
                  <Icon className="w-4 h-4 text-gray-500" />
                )}
                
                {/* Пульсация для активного состояния */}
                {status === 'active' && (
                  <span className="absolute inset-0 rounded-full animate-ping bg-blue-500/30" />
                )}
              </div>

              {/* Контент */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <span className={`font-medium transition-colors duration-300 ${
                    status === 'active' ? 'text-blue-300' :
                    status === 'completed' ? 'text-green-300' :
                    status === 'error' ? 'text-red-300' :
                    'text-gray-400'
                  }`}>
                    {config?.label || stage}
                  </span>
                  <span className={`text-xs px-2 py-0.5 rounded-full transition-all duration-300 ${
                    status === 'active' ? 'bg-blue-500/20 text-blue-300' :
                    status === 'completed' ? 'bg-green-500/20 text-green-300' :
                    status === 'error' ? 'bg-red-500/20 text-red-300' :
                    'text-gray-500'
                  }`}>
                    {getStatusLabel(status)}
                  </span>
                </div>
                
                {/* ИСПРАВЛЕНИЕ: Показываем сообщение о прогрессе для активных этапов (non-reasoning модели) */}
                {status === 'active' && stages[stage]?.message && (
                  <p className="mt-1 text-xs text-blue-400/80 truncate">
                    {stages[stage].message}
                  </p>
                )}
                
                {/* Прогресс-бар для активного состояния */}
                {status === 'active' && (
                  <div className="mt-2 h-1.5 bg-gray-700 rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-gradient-to-r from-blue-500 to-blue-400 rounded-full transition-all duration-300 relative"
                      style={{ width: progress > 0 ? `${progress}%` : '30%' }}
                    >
                      {/* Эффект shimmer */}
                      <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent animate-shimmer" />
                    </div>
                  </div>
                )}

                {/* Сообщение об ошибке */}
                {status === 'error' && stages[stage]?.error && (
                  <p className="mt-1 text-xs text-red-400 truncate">
                    {stages[stage].error}
                  </p>
                )}

                {/* Блок рассуждений (thinking) для reasoning моделей */}
                {stages[stage]?.thinking && stages[stage].thinking.status !== 'idle' && (
                  <ThinkingBlock
                    thinking={stages[stage].thinking}
                    stageName={stage}
                  />
                )}
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}
