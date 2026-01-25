import { useState, useEffect } from 'react'
import { 
  BarChart3, 
  Clock, 
  Cpu, 
  Zap, 
  TrendingUp, 
  CheckCircle2, 
  AlertTriangle,
  RefreshCw,
  Activity,
  Brain,
  Code2,
  TestTube2,
  FileSearch
} from 'lucide-react'
import { useApi } from '../hooks/useApi'
import { api } from '../services/apiClient'
import { LoadingState } from './ui/LoadingState'
import { ErrorState } from './ui/ErrorState'
import { EmptyState } from './ui/EmptyState'

// Типы из API используются через useApi hook

interface MetricCardProps {
  title: string
  value: string | number
  subtitle?: string
  icon: React.ReactNode
  trend?: 'up' | 'down' | 'neutral'
  color?: 'green' | 'red' | 'yellow' | 'blue' | 'purple'
}

function MetricCard({ title, value, subtitle, icon, trend, color = 'blue' }: MetricCardProps) {
  const colorClasses = {
    green: 'bg-green-500/10 text-green-400 border-green-500/30',
    red: 'bg-red-500/10 text-red-400 border-red-500/30',
    yellow: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/30',
    blue: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
    purple: 'bg-purple-500/10 text-purple-400 border-purple-500/30'
  }

  return (
    <div className={`p-4 rounded-xl border ${colorClasses[color]} transition-all hover:scale-105`}>
      <div className="flex items-start justify-between">
        <div className="p-2 rounded-lg bg-gray-800/50">
          {icon}
        </div>
        {trend && (
          <div className={`flex items-center text-xs ${
            trend === 'up' ? 'text-green-400' : trend === 'down' ? 'text-red-400' : 'text-gray-400'
          }`}>
            <TrendingUp className={`w-3 h-3 mr-1 ${trend === 'down' ? 'rotate-180' : ''}`} />
            {trend === 'up' ? '+' : trend === 'down' ? '-' : ''}
          </div>
        )}
      </div>
      <div className="mt-3">
        <p className="text-2xl font-bold text-white">{value}</p>
        <p className="text-sm text-gray-400 mt-1">{title}</p>
        {subtitle && (
          <p className="text-xs text-gray-500 mt-0.5">{subtitle}</p>
        )}
      </div>
    </div>
  )
}

interface StageBarProps {
  stage: string
  avgTime: number
  calls: number
  errors: number
  maxTime: number
}

function StageBar({ stage, avgTime, calls, errors, maxTime }: StageBarProps) {
  const width = maxTime > 0 ? (avgTime / maxTime) * 100 : 0
  const hasErrors = errors > 0
  
  const stageIcons: Record<string, React.ReactNode> = {
    planning: <Brain className="w-4 h-4" />,
    research: <FileSearch className="w-4 h-4" />,
    testing: <TestTube2 className="w-4 h-4" />,
    coding: <Code2 className="w-4 h-4" />,
    validation: <CheckCircle2 className="w-4 h-4" />,
    debug: <AlertTriangle className="w-4 h-4" />,
  }

  const stageNames: Record<string, string> = {
    planning: 'Планирование',
    research: 'Исследование',
    testing: 'Тестирование',
    coding: 'Генерация кода',
    validation: 'Валидация',
    debug: 'Отладка',
    reflection: 'Рефлексия',
    critic: 'Критика'
  }

  return (
    <div className="group">
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-2">
          <span className="text-gray-400">
            {stageIcons[stage] || <Activity className="w-4 h-4" />}
          </span>
          <span className="text-sm text-gray-300">{stageNames[stage] || stage}</span>
        </div>
        <div className="flex items-center gap-3 text-xs">
          <span className="text-gray-400">{calls} вызовов</span>
          <span className={hasErrors ? 'text-red-400' : 'text-gray-500'}>
            {errors > 0 && `${errors} ошибок`}
          </span>
          <span className="text-white font-medium">{(avgTime / 1000).toFixed(1)}с</span>
        </div>
      </div>
      <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
        <div 
          className={`h-full rounded-full transition-all duration-500 ${
            hasErrors ? 'bg-gradient-to-r from-red-500 to-red-400' : 'bg-gradient-to-r from-blue-500 to-purple-500'
          }`}
          style={{ width: `${Math.max(width, 2)}%` }}
        />
      </div>
    </div>
  )
}

export function MetricsDashboard() {
  const { data, loading, error, refetch } = useApi(() => api.metrics.get(), {
    immediate: true,
    cache: true,
    cacheTTL: 30000 // 30 секунд
  })
  const [autoRefresh, setAutoRefresh] = useState(true)

  // Автообновление каждые 30 секунд
  useEffect(() => {
    if (autoRefresh) {
      const interval = setInterval(() => refetch(), 30000)
      return () => clearInterval(interval)
    }
  }, [autoRefresh, refetch])

  if (loading) {
    return <LoadingState message="Загрузка метрик..." />
  }

  if (error) {
    return (
      <ErrorState
        title="Не удалось загрузить метрики"
        message={error}
        onRetry={refetch}
        retryLabel="Повторить"
      />
    )
  }

  if (!data) {
    return <EmptyState message="Нет данных" />
  }

  // Преобразуем stages из Record в массив для отображения
  const stagesArray = Object.entries(data.stages).map(([stage, metrics]) => ({
    stage,
    avgTime: metrics.average_time,
    calls: metrics.count,
    errors: 0, // В API нет информации об ошибках
    estimatedTime: metrics.estimated_time
  }))

  const maxStageTime = stagesArray.length > 0 
    ? Math.max(...stagesArray.map(s => s.avgTime), 1)
    : 1

  // Вычисляем общие метрики из stages
  const totalCalls = stagesArray.reduce((sum, s) => sum + s.calls, 0)
  const avgTime = stagesArray.length > 0
    ? stagesArray.reduce((sum, s) => sum + s.avgTime, 0) / stagesArray.length
    : 0

  return (
    <div className="p-6 space-y-6">
      {/* Заголовок */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-purple-500/20 rounded-lg">
            <BarChart3 className="w-5 h-5 text-purple-400" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-white">Метрики генерации</h2>
            {data.benchmark && (
              <p className="text-xs text-gray-500">
                Модель: {data.benchmark.model_used} | {data.benchmark.tokens_per_second.toFixed(1)} токенов/с
              </p>
            )}
          </div>
        </div>
        <button
          onClick={() => setAutoRefresh(!autoRefresh)}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm transition-colors ${
            autoRefresh 
              ? 'bg-green-500/20 text-green-300' 
              : 'bg-gray-700/50 text-gray-400'
          }`}
        >
          <RefreshCw className={`w-4 h-4 ${autoRefresh ? 'animate-spin' : ''}`} />
          {autoRefresh ? 'Авто' : 'Пауза'}
        </button>
      </div>

      {/* Основные метрики */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          title="Всего вызовов"
          value={totalCalls}
          icon={<Zap className="w-5 h-5" />}
          color="purple"
        />
        <MetricCard
          title="Этапов"
          value={stagesArray.length}
          icon={<CheckCircle2 className="w-5 h-5" />}
          color="green"
        />
        <MetricCard
          title="Среднее время"
          value={`${(avgTime / 1000).toFixed(1)}с`}
          icon={<Clock className="w-5 h-5" />}
          color="blue"
        />
        {data.benchmark && (
          <MetricCard
            title="Производительность"
            value={`${data.benchmark.performance_multiplier.toFixed(1)}x`}
            subtitle={`${data.benchmark.tokens_per_second.toFixed(0)} ток/с`}
            icon={<Cpu className="w-5 h-5" />}
            color="yellow"
          />
        )}
      </div>

      {/* Метрики по этапам */}
      {stagesArray.length > 0 && (
        <div className="bg-gray-800/40 rounded-xl p-5 border border-gray-700/50">
          <h3 className="text-sm font-medium text-gray-300 mb-4 flex items-center gap-2">
            <Activity className="w-4 h-4 text-purple-400" />
            Время по этапам
          </h3>
          <div className="space-y-4">
            {stagesArray.map((stage) => (
              <StageBar
                key={stage.stage}
                stage={stage.stage}
                avgTime={stage.avgTime}
                calls={stage.calls}
                errors={stage.errors}
                maxTime={maxStageTime}
              />
            ))}
          </div>
        </div>
      )}

      {/* Информация о системе */}
      {data.system_info && (
        <div className="bg-gray-800/40 rounded-xl p-5 border border-gray-700/50">
          <h3 className="text-sm font-medium text-gray-300 mb-4 flex items-center gap-2">
            <Cpu className="w-4 h-4 text-purple-400" />
            Информация о системе
          </h3>
          <div className="space-y-2 text-sm text-gray-400">
            <div>Платформа: {data.system_info.platform}</div>
            <div>Python: {data.system_info.python_version}</div>
          </div>
        </div>
      )}
    </div>
  )
}
