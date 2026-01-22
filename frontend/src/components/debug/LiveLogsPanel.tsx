/**
 * Панель live-логов для Under The Hood.
 * 
 * Показывает логи в реальном времени с фильтрацией по уровню и этапу.
 */

import { useState, useRef, useEffect } from 'react'
import { 
  Terminal, 
  Filter, 
  Trash2, 
  Download,
  AlertCircle,
  AlertTriangle,
  Info,
  Bug,
  Pause,
  Play
} from 'lucide-react'

export interface LogEntry {
  timestamp: string
  level: 'debug' | 'info' | 'warning' | 'error'
  stage: string
  message: string
  details?: Record<string, unknown>
}

interface LiveLogsPanelProps {
  logs: LogEntry[]
  onClear?: () => void
}

const levelConfig = {
  debug: { icon: Bug, color: 'text-gray-400', bg: 'bg-gray-500/10' },
  info: { icon: Info, color: 'text-blue-400', bg: 'bg-blue-500/10' },
  warning: { icon: AlertTriangle, color: 'text-yellow-400', bg: 'bg-yellow-500/10' },
  error: { icon: AlertCircle, color: 'text-red-400', bg: 'bg-red-500/10' }
}

const stageColors: Record<string, string> = {
  intent: 'text-purple-400',
  planning: 'text-blue-400',
  research: 'text-cyan-400',
  testing: 'text-green-400',
  coding: 'text-yellow-400',
  validation: 'text-orange-400',
  debug: 'text-red-400',
  critic: 'text-pink-400',
  reflection: 'text-indigo-400'
}

export function LiveLogsPanel({ logs, onClear }: LiveLogsPanelProps) {
  const [filter, setFilter] = useState<string>('all')
  const [stageFilter, setStageFilter] = useState<string>('all')
  const [autoscroll, setAutoscroll] = useState(true)
  const [expandedLogs, setExpandedLogs] = useState<Set<number>>(new Set())
  const logsEndRef = useRef<HTMLDivElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  // Автопрокрутка
  useEffect(() => {
    if (autoscroll && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [logs, autoscroll])

  // Фильтрация логов
  const filteredLogs = logs.filter(log => {
    if (filter !== 'all' && log.level !== filter) return false
    if (stageFilter !== 'all' && log.stage !== stageFilter) return false
    return true
  })

  // Уникальные этапы для фильтра
  const stages = [...new Set(logs.map(l => l.stage))]

  // Экспорт логов
  const handleExport = () => {
    const content = filteredLogs.map(log => 
      `[${log.timestamp}] [${log.level.toUpperCase()}] [${log.stage}] ${log.message}` +
      (log.details ? `\n  ${JSON.stringify(log.details)}` : '')
    ).join('\n')
    
    const blob = new Blob([content], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `logs-${new Date().toISOString().slice(0, 19)}.txt`
    a.click()
    URL.revokeObjectURL(url)
  }

  const toggleExpand = (index: number) => {
    const newExpanded = new Set(expandedLogs)
    if (newExpanded.has(index)) {
      newExpanded.delete(index)
    } else {
      newExpanded.add(index)
    }
    setExpandedLogs(newExpanded)
  }

  const formatTime = (timestamp: string) => {
    try {
      const date = new Date(timestamp)
      const time = date.toLocaleTimeString('ru-RU', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
      })
      const ms = date.getMilliseconds().toString().padStart(3, '0')
      return `${time}.${ms}`
    } catch {
      return timestamp
    }
  }

  return (
    <div className="h-full flex flex-col bg-gray-900/50">
      {/* Toolbar */}
      <div className="flex items-center justify-between p-3 border-b border-gray-700/50 bg-gray-800/50">
        <div className="flex items-center gap-2">
          <Terminal className="w-4 h-4 text-green-400" />
          <span className="text-sm font-medium text-gray-300">
            Логи ({filteredLogs.length})
          </span>
        </div>
        
        <div className="flex items-center gap-2">
          {/* Level filter */}
          <div className="flex items-center gap-1">
            <Filter className="w-3 h-3 text-gray-500" />
            <select
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="text-xs bg-gray-800 border border-gray-700 rounded px-2 py-1 text-gray-300"
            >
              <option value="all">Все уровни</option>
              <option value="debug">Debug</option>
              <option value="info">Info</option>
              <option value="warning">Warning</option>
              <option value="error">Error</option>
            </select>
          </div>
          
          {/* Stage filter */}
          {stages.length > 0 && (
            <select
              value={stageFilter}
              onChange={(e) => setStageFilter(e.target.value)}
              className="text-xs bg-gray-800 border border-gray-700 rounded px-2 py-1 text-gray-300"
            >
              <option value="all">Все этапы</option>
              {stages.map(stage => (
                <option key={stage} value={stage}>{stage}</option>
              ))}
            </select>
          )}
          
          {/* Autoscroll toggle */}
          <button
            onClick={() => setAutoscroll(!autoscroll)}
            title={autoscroll ? 'Пауза автопрокрутки' : 'Включить автопрокрутку'}
            className={`p-1.5 rounded transition-colors ${
              autoscroll ? 'bg-green-500/20 text-green-400' : 'bg-gray-700/50 text-gray-400'
            }`}
          >
            {autoscroll ? <Play className="w-3 h-3" /> : <Pause className="w-3 h-3" />}
          </button>
          
          {/* Export */}
          <button
            onClick={handleExport}
            title="Экспорт логов"
            className="p-1.5 rounded bg-gray-700/50 text-gray-400 hover:text-white transition-colors"
          >
            <Download className="w-3 h-3" />
          </button>
          
          {/* Clear */}
          {onClear && (
            <button
              onClick={onClear}
              title="Очистить логи"
              className="p-1.5 rounded bg-gray-700/50 text-gray-400 hover:text-red-400 transition-colors"
            >
              <Trash2 className="w-3 h-3" />
            </button>
          )}
        </div>
      </div>
      
      {/* Logs list */}
      <div 
        ref={containerRef}
        className="flex-1 overflow-auto font-mono text-xs"
      >
        {filteredLogs.length === 0 ? (
          <div className="flex items-center justify-center h-full text-gray-500">
            <span>Нет логов</span>
          </div>
        ) : (
          <div className="p-2 space-y-0.5">
            {filteredLogs.map((log, index) => {
              const config = levelConfig[log.level]
              const Icon = config.icon
              const isExpanded = expandedLogs.has(index)
              const hasDetails = log.details && Object.keys(log.details).length > 0
              
              return (
                <div 
                  key={index}
                  className={`group flex items-start gap-2 p-1.5 rounded hover:bg-gray-800/50 ${config.bg}`}
                >
                  {/* Icon */}
                  <Icon className={`w-3 h-3 mt-0.5 flex-shrink-0 ${config.color}`} />
                  
                  {/* Timestamp */}
                  <span className="text-gray-500 flex-shrink-0 w-20">
                    {formatTime(log.timestamp)}
                  </span>
                  
                  {/* Stage */}
                  <span className={`flex-shrink-0 w-16 ${stageColors[log.stage] || 'text-gray-400'}`}>
                    [{log.stage}]
                  </span>
                  
                  {/* Message */}
                  <div className="flex-1 min-w-0">
                    <span 
                      className={`text-gray-300 ${hasDetails ? 'cursor-pointer hover:text-white' : ''}`}
                      onClick={() => hasDetails && toggleExpand(index)}
                    >
                      {log.message}
                      {hasDetails && (
                        <span className="ml-1 text-gray-500">
                          {isExpanded ? '▼' : '▶'}
                        </span>
                      )}
                    </span>
                    
                    {/* Details */}
                    {isExpanded && hasDetails && (
                      <pre className="mt-1 p-2 bg-gray-900/80 rounded text-gray-400 overflow-x-auto">
                        {JSON.stringify(log.details, null, 2)}
                      </pre>
                    )}
                  </div>
                </div>
              )
            })}
            <div ref={logsEndRef} />
          </div>
        )}
      </div>
    </div>
  )
}
