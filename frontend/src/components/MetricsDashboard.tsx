import { useState, useEffect } from 'react'
import { 
  BarChart3, 
  Clock, 
  Cpu, 
  Zap, 
  TrendingUp, 
  CheckCircle2, 
  XCircle, 
  AlertTriangle,
  RefreshCw,
  Activity,
  Brain,
  Code2,
  TestTube2,
  FileSearch
} from 'lucide-react'

interface GenerationMetrics {
  total_generations: number
  successful: number
  failed: number
  avg_time_ms: number
  avg_iterations: number
  success_rate: number
}

interface StageMetrics {
  stage: string
  avg_time_ms: number
  calls: number
  errors: number
}

interface ModelMetrics {
  model: string
  calls: number
  avg_tokens: number
  avg_time_ms: number
}

interface DashboardData {
  generation: GenerationMetrics
  stages: StageMetrics[]
  models: ModelMetrics[]
  last_updated: string
}

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
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [autoRefresh, setAutoRefresh] = useState(true)

  const fetchMetrics = async () => {
    try {
      const isDev = typeof window !== 'undefined' && window.location.port === '5173'
      const apiUrl = isDev ? 'http://localhost:8000/api/metrics' : '/api/metrics'
      
      const response = await fetch(apiUrl)
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }
      
      const result = await response.json()
      setData(result)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка загрузки')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchMetrics()
    
    if (autoRefresh) {
      const interval = setInterval(fetchMetrics, 30000) // Обновление каждые 30 сек
      return () => clearInterval(interval)
    }
  }, [autoRefresh])

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center">
        <RefreshCw className="w-6 h-6 text-purple-400 animate-spin" />
        <span className="ml-2 text-gray-400">Загрузка метрик...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-6 text-center">
        <AlertTriangle className="w-8 h-8 text-yellow-400 mx-auto mb-2" />
        <p className="text-gray-400">Не удалось загрузить метрики</p>
        <p className="text-sm text-gray-500 mt-1">{error}</p>
        <button 
          onClick={fetchMetrics}
          className="mt-4 px-4 py-2 bg-purple-500/20 text-purple-300 rounded-lg hover:bg-purple-500/30 transition-colors"
        >
          Повторить
        </button>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="p-6 text-center text-gray-400">
        Нет данных
      </div>
    )
  }

  const gen = data.generation
  const maxStageTime = Math.max(...data.stages.map(s => s.avg_time_ms), 1)

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
            <p className="text-xs text-gray-500">
              Обновлено: {new Date(data.last_updated).toLocaleTimeString('ru-RU')}
            </p>
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
          title="Всего генераций"
          value={gen.total_generations}
          icon={<Zap className="w-5 h-5" />}
          color="purple"
        />
        <MetricCard
          title="Успешных"
          value={gen.successful}
          subtitle={`${(gen.success_rate * 100).toFixed(0)}%`}
          icon={<CheckCircle2 className="w-5 h-5" />}
          color="green"
          trend={gen.success_rate > 0.7 ? 'up' : 'down'}
        />
        <MetricCard
          title="Ошибок"
          value={gen.failed}
          icon={<XCircle className="w-5 h-5" />}
          color={gen.failed > 0 ? 'red' : 'green'}
        />
        <MetricCard
          title="Среднее время"
          value={`${(gen.avg_time_ms / 1000).toFixed(1)}с`}
          subtitle={`~${gen.avg_iterations.toFixed(1)} итераций`}
          icon={<Clock className="w-5 h-5" />}
          color="blue"
        />
      </div>

      {/* Метрики по этапам */}
      {data.stages.length > 0 && (
        <div className="bg-gray-800/40 rounded-xl p-5 border border-gray-700/50">
          <h3 className="text-sm font-medium text-gray-300 mb-4 flex items-center gap-2">
            <Activity className="w-4 h-4 text-purple-400" />
            Время по этапам
          </h3>
          <div className="space-y-4">
            {data.stages.map((stage) => (
              <StageBar
                key={stage.stage}
                stage={stage.stage}
                avgTime={stage.avg_time_ms}
                calls={stage.calls}
                errors={stage.errors}
                maxTime={maxStageTime}
              />
            ))}
          </div>
        </div>
      )}

      {/* Метрики по моделям */}
      {data.models.length > 0 && (
        <div className="bg-gray-800/40 rounded-xl p-5 border border-gray-700/50">
          <h3 className="text-sm font-medium text-gray-300 mb-4 flex items-center gap-2">
            <Cpu className="w-4 h-4 text-purple-400" />
            Использование моделей
          </h3>
          <div className="space-y-3">
            {data.models.map((model) => (
              <div key={model.model} className="flex items-center justify-between p-3 bg-gray-900/50 rounded-lg">
                <div className="flex items-center gap-3">
                  <Brain className="w-4 h-4 text-purple-400" />
                  <span className="text-sm text-white font-mono">{model.model}</span>
                </div>
                <div className="flex items-center gap-4 text-xs text-gray-400">
                  <span>{model.calls} вызовов</span>
                  <span>~{Math.round(model.avg_tokens)} токенов</span>
                  <span>{(model.avg_time_ms / 1000).toFixed(1)}с</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
