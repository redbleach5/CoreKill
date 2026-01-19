/**
 * Современный компонент прогресса агентов
 * Вдохновлён UI Cursor, Claude, Vercel AI SDK
 */
import { useState } from 'react'
import { 
  Brain, ListTodo, Search, TestTube, Code2, Shield, RefreshCw,
  AlertCircle, CheckCircle2, Loader2, ChevronDown, Sparkles,
  Bug, Wrench, MessageSquare
} from 'lucide-react'

// Конфигурация этапов с иконками и описаниями
const stageConfig: Record<string, { 
  label: string
  icon: typeof Brain
  description: string
  activeText: string
}> = {
  intent: { 
    label: 'Анализ задачи', 
    icon: Brain, 
    description: 'Понимание намерения',
    activeText: 'Анализирую задачу...'
  },
  planning: { 
    label: 'Планирование', 
    icon: ListTodo, 
    description: 'Разработка плана',
    activeText: 'Составляю план решения...'
  },
  research: { 
    label: 'Исследование', 
    icon: Search, 
    description: 'Сбор контекста',
    activeText: 'Ищу релевантную информацию...'
  },
  testing: { 
    label: 'Тесты', 
    icon: TestTube, 
    description: 'Генерация тестов',
    activeText: 'Пишу тесты...'
  },
  coding: { 
    label: 'Кодирование', 
    icon: Code2, 
    description: 'Написание кода',
    activeText: 'Генерирую код...'
  },
  validation: { 
    label: 'Валидация', 
    icon: Shield, 
    description: 'Проверка качества',
    activeText: 'Проверяю код...'
  },
  debug: { 
    label: 'Отладка', 
    icon: Bug, 
    description: 'Анализ ошибок',
    activeText: 'Анализирую ошибки...'
  },
  fixing: { 
    label: 'Исправление', 
    icon: Wrench, 
    description: 'Фикс кода',
    activeText: 'Исправляю код...'
  },
  reflection: { 
    label: 'Рефлексия', 
    icon: RefreshCw, 
    description: 'Оценка качества',
    activeText: 'Оцениваю результат...'
  },
  critic: { 
    label: 'Критика', 
    icon: MessageSquare, 
    description: 'Критический анализ',
    activeText: 'Финальный анализ...'
  },
  greeting: { 
    label: 'Приветствие', 
    icon: Sparkles, 
    description: 'Приветствие',
    activeText: 'Готовлю ответ...'
  },
  help: { 
    label: 'Помощь', 
    icon: MessageSquare, 
    description: 'Справка',
    activeText: 'Готовлю справку...'
  }
}

// Порядок отображения этапов
const stageOrder = ['intent', 'planning', 'research', 'testing', 'coding', 'validation', 'reflection', 'critic']

interface StageData {
  stage: string
  status: 'idle' | 'start' | 'progress' | 'end' | 'error'
  message: string
  progress?: number
  result?: any
  error?: string
}

interface AgentProgressProps {
  stages: Record<string, StageData>
  isCompact?: boolean
}

type StageStatus = 'pending' | 'active' | 'completed' | 'error'

export function AgentProgress({ stages, isCompact = false }: AgentProgressProps) {
  const [expanded, setExpanded] = useState(true)
  
  // Определяем статус этапа
  const getStageStatus = (stageName: string): StageStatus => {
    const data = stages[stageName]
    if (!data || data.status === 'idle') return 'pending'
    if (data.status === 'error') return 'error'
    if (data.status === 'end') return 'completed'
    return 'active'
  }

  // Находим текущий активный этап
  const activeStage = Object.entries(stages).find(([_, data]) => 
    data.status === 'start' || data.status === 'progress'
  )
  
  // Считаем завершённые этапы
  const completedStages = Object.values(stages).filter(s => s.status === 'end').length
  const totalStages = stageOrder.length
  const progress = (completedStages / totalStages) * 100

  // Рендер иконки статуса
  const renderStatusIcon = (status: StageStatus, Icon: typeof Brain) => {
    switch (status) {
      case 'completed':
        return (
          <div className="w-6 h-6 rounded-full bg-emerald-500/20 flex items-center justify-center">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
          </div>
        )
      case 'active':
        return (
          <div className="w-6 h-6 rounded-full bg-blue-500/20 flex items-center justify-center relative">
            <Icon className="w-3.5 h-3.5 text-blue-400" />
            <span className="absolute inset-0 rounded-full border-2 border-blue-400/50 animate-ping" />
          </div>
        )
      case 'error':
        return (
          <div className="w-6 h-6 rounded-full bg-red-500/20 flex items-center justify-center">
            <AlertCircle className="w-3.5 h-3.5 text-red-400" />
          </div>
        )
      default:
        return (
          <div className="w-6 h-6 rounded-full bg-white/5 flex items-center justify-center">
            <Icon className="w-3.5 h-3.5 text-gray-600" />
          </div>
        )
    }
  }

  // Компактный вид — только текущий этап
  if (isCompact && activeStage) {
    const [stageName, stageData] = activeStage
    const config = stageConfig[stageName]
    if (!config) return null

    return (
      <div className="flex items-center gap-3 text-sm">
        <div className="relative">
          <config.icon className="w-4 h-4 text-blue-400" />
          <Loader2 className="w-4 h-4 text-blue-400 absolute inset-0 animate-spin opacity-50" />
        </div>
        <span className="text-gray-300">{config.activeText}</span>
        <span className="text-gray-500 text-xs">{completedStages}/{totalStages}</span>
      </div>
    )
  }

  return (
    <div className="bg-[#0d1117] border border-white/10 rounded-xl overflow-hidden">
      {/* Header с общим прогрессом */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-4 py-3 flex items-center gap-3 hover:bg-white/5 transition-colors"
      >
        <div className="relative w-8 h-8">
          {/* Circular progress */}
          <svg className="w-8 h-8 -rotate-90" viewBox="0 0 32 32">
            <circle
              cx="16"
              cy="16"
              r="14"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              className="text-white/10"
            />
            <circle
              cx="16"
              cy="16"
              r="14"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeDasharray={`${progress * 0.88} 88`}
              strokeLinecap="round"
              className="text-blue-500 transition-all duration-500"
            />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            {activeStage ? (
              <Loader2 className="w-3.5 h-3.5 text-blue-400 animate-spin" />
            ) : (
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
            )}
          </div>
        </div>
        
        <div className="flex-1 text-left">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-white">
              {activeStage ? stageConfig[activeStage[0]]?.activeText || 'Выполнение...' : 'Готово'}
            </span>
          </div>
          <div className="text-xs text-gray-500 mt-0.5">
            {completedStages} из {totalStages} этапов завершено
          </div>
        </div>

        <ChevronDown className={`w-4 h-4 text-gray-500 transition-transform ${expanded ? 'rotate-180' : ''}`} />
      </button>

      {/* Детальный список этапов */}
      {expanded && (
        <div className="px-4 pb-4 space-y-1">
          {stageOrder.map((stageName, index) => {
            const config = stageConfig[stageName]
            if (!config) return null
            
            const status = getStageStatus(stageName)
            const stageData = stages[stageName]
            const isLast = index === stageOrder.length - 1
            
            return (
              <div key={stageName} className="relative">
                {/* Вертикальная линия между этапами */}
                {!isLast && (
                  <div 
                    className={`absolute left-3 top-7 w-px h-6 transition-colors duration-300 ${
                      status === 'completed' ? 'bg-emerald-500/50' : 'bg-white/10'
                    }`}
                  />
                )}
                
                <div className={`flex items-center gap-3 py-1.5 px-2 rounded-lg transition-colors ${
                  status === 'active' ? 'bg-blue-500/10' : ''
                }`}>
                  {renderStatusIcon(status, config.icon)}
                  
                  <div className="flex-1 min-w-0">
                    <div className={`text-sm font-medium transition-colors ${
                      status === 'completed' ? 'text-emerald-400' :
                      status === 'active' ? 'text-blue-400' :
                      status === 'error' ? 'text-red-400' :
                      'text-gray-500'
                    }`}>
                      {config.label}
                    </div>
                    
                    {/* Сообщение для активного или с ошибкой */}
                    {status === 'active' && stageData?.message && (
                      <div className="text-xs text-gray-500 truncate mt-0.5">
                        {stageData.message}
                      </div>
                    )}
                    {status === 'error' && stageData?.error && (
                      <div className="text-xs text-red-400/70 truncate mt-0.5">
                        {stageData.error}
                      </div>
                    )}
                  </div>

                  {/* Индикатор справа */}
                  {status === 'active' && (
                    <div className="flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
                      <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse delay-75" />
                      <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse delay-150" />
                    </div>
                  )}
                </div>
              </div>
            )
          })}
          
          {/* Показываем debug/fixing если они активны (self-healing loop) */}
          {(stages['debug'] || stages['fixing']) && (
            <div className="mt-2 pt-2 border-t border-white/5">
              <div className="text-xs text-amber-400/70 mb-2 flex items-center gap-1">
                <RefreshCw className="w-3 h-3" />
                Цикл самоисправления
              </div>
              {['debug', 'fixing'].map(stageName => {
                const config = stageConfig[stageName]
                const status = getStageStatus(stageName)
                const stageData = stages[stageName]
                
                if (!stageData) return null
                
                return (
                  <div key={stageName} className={`flex items-center gap-3 py-1.5 px-2 rounded-lg ${
                    status === 'active' ? 'bg-amber-500/10' : ''
                  }`}>
                    {renderStatusIcon(status, config.icon)}
                    <span className={`text-sm ${
                      status === 'completed' ? 'text-emerald-400' :
                      status === 'active' ? 'text-amber-400' :
                      'text-gray-500'
                    }`}>
                      {config.label}
                    </span>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
