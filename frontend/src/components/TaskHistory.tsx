/**
 * Компонент для отображения истории выполненных задач
 */
import { useState } from 'react'
import { Trash2, Copy, Eye, EyeOff, Clock, CheckCircle2, AlertCircle } from 'lucide-react'

interface Task {
  id: string
  title: string
  description: string
  status: 'completed' | 'failed' | 'pending'
  timestamp: Date
  duration: number
  quality?: number
  code?: string
}

interface TaskHistoryProps {
  tasks: Task[]
  onTaskSelect?: (task: Task) => void
  onTaskDelete?: (taskId: string) => void
}

export function TaskHistory({ tasks, onTaskSelect, onTaskDelete }: TaskHistoryProps) {
  const [expandedTaskId, setExpandedTaskId] = useState<string | null>(null)
  const [filter, setFilter] = useState<'all' | 'completed' | 'failed'>('all')

  const filteredTasks = tasks.filter(task => {
    if (filter === 'all') return true
    return task.status === filter
  })

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle2 className="w-4 h-4 text-emerald-400" />
      case 'failed':
        return <AlertCircle className="w-4 h-4 text-red-400" />
      default:
        return <Clock className="w-4 h-4 text-amber-400" />
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
      case 'failed':
        return 'bg-red-500/10 text-red-400 border-red-500/20'
      default:
        return 'bg-amber-500/10 text-amber-400 border-amber-500/20'
    }
  }

  const formatTime = (date: Date) => {
    return new Intl.DateTimeFormat('ru-RU', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    }).format(date)
  }

  const formatDuration = (ms: number) => {
    if (ms < 1000) return `${Math.round(ms)}ms`
    return `${(ms / 1000).toFixed(1)}s`
  }

  return (
    <div className="flex flex-col h-full bg-[#0a0a0f] rounded-xl border border-white/10 overflow-hidden">
      {/* Header */}
      <div className="flex-shrink-0 px-4 py-3 border-b border-white/10 bg-white/5">
        <h3 className="text-sm font-semibold text-white mb-3">История задач</h3>
        <div className="flex gap-2">
          {(['all', 'completed', 'failed'] as const).map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-2 py-1 text-xs rounded transition-colors ${
                filter === f
                  ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                  : 'bg-white/5 text-gray-400 hover:bg-white/10'
              }`}
            >
              {f === 'all' && 'Все'}
              {f === 'completed' && 'Успешные'}
              {f === 'failed' && 'Ошибки'}
            </button>
          ))}
        </div>
      </div>

      {/* Tasks List */}
      <div className="flex-1 overflow-y-auto">
        {filteredTasks.length === 0 ? (
          <div className="flex items-center justify-center h-full text-gray-500 text-sm">
            Нет задач
          </div>
        ) : (
          <div className="space-y-2 p-3">
            {filteredTasks.map(task => (
              <div
                key={task.id}
                className="bg-white/5 border border-white/10 rounded-lg overflow-hidden hover:bg-white/10 transition-colors"
              >
                {/* Task Header */}
                <button
                  onClick={() => setExpandedTaskId(expandedTaskId === task.id ? null : task.id)}
                  className="w-full flex items-start gap-3 p-3 text-left"
                >
                  {getStatusIcon(task.status)}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-white truncate">{task.title}</p>
                    <p className="text-xs text-gray-500 mt-1">
                      {formatTime(task.timestamp)} • {formatDuration(task.duration)}
                    </p>
                  </div>
                  {task.quality !== undefined && (
                    <div className={`text-xs font-medium px-2 py-1 rounded ${
                      task.quality >= 0.8 ? 'bg-emerald-500/10 text-emerald-400' :
                      task.quality >= 0.6 ? 'bg-amber-500/10 text-amber-400' :
                      'bg-red-500/10 text-red-400'
                    }`}>
                      {Math.round(task.quality * 100)}%
                    </div>
                  )}
                </button>

                {/* Task Details */}
                {expandedTaskId === task.id && (
                  <div className="px-3 pb-3 border-t border-white/10 bg-white/5 space-y-3">
                    <p className="text-xs text-gray-400">{task.description}</p>

                    {task.code && (
                      <div className="bg-[#0d1117] border border-white/10 rounded p-2">
                        <pre className="text-xs text-gray-300 overflow-x-auto max-h-32">
                          <code>{task.code.substring(0, 200)}...</code>
                        </pre>
                      </div>
                    )}

                    <div className="flex gap-2">
                      <button
                        onClick={() => onTaskSelect?.(task)}
                        className="flex-1 flex items-center justify-center gap-1 px-2 py-1.5 text-xs text-blue-400 hover:bg-blue-500/10 rounded transition-colors"
                      >
                        <Eye className="w-3 h-3" />
                        Открыть
                      </button>
                      {task.code && (
                        <button
                          onClick={() => navigator.clipboard.writeText(task.code!)}
                          className="flex-1 flex items-center justify-center gap-1 px-2 py-1.5 text-xs text-gray-400 hover:bg-white/10 rounded transition-colors"
                        >
                          <Copy className="w-3 h-3" />
                          Копировать
                        </button>
                      )}
                      <button
                        onClick={() => onTaskDelete?.(task.id)}
                        className="flex-1 flex items-center justify-center gap-1 px-2 py-1.5 text-xs text-red-400 hover:bg-red-500/10 rounded transition-colors"
                      >
                        <Trash2 className="w-3 h-3" />
                        Удалить
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
