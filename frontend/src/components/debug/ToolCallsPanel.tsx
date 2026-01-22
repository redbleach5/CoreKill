/**
 * Панель отслеживания вызовов инструментов.
 * 
 * Показывает вызовы LLM, валидации и других инструментов.
 */

import { useState } from 'react'
import { 
  Brain, 
  CheckCircle, 
  Search, 
  FileCode,
  Loader2,
  XCircle,
  Clock,
  ChevronDown,
  ChevronRight,
  Zap
} from 'lucide-react'

export interface ToolCall {
  id: string
  type: 'llm' | 'validation' | 'search' | 'file'
  name: string
  input_preview: string
  output_preview?: string
  tokens_in?: number
  tokens_out?: number
  duration_ms: number
  status: 'running' | 'success' | 'error'
}

interface ToolCallsPanelProps {
  toolCalls: ToolCall[]
}

const typeConfig = {
  llm: { 
    icon: Brain, 
    label: 'LLM', 
    color: 'text-purple-400',
    bg: 'bg-purple-500/10',
    border: 'border-purple-500/30'
  },
  validation: { 
    icon: CheckCircle, 
    label: 'Валидация', 
    color: 'text-green-400',
    bg: 'bg-green-500/10',
    border: 'border-green-500/30'
  },
  search: { 
    icon: Search, 
    label: 'Поиск', 
    color: 'text-cyan-400',
    bg: 'bg-cyan-500/10',
    border: 'border-cyan-500/30'
  },
  file: { 
    icon: FileCode, 
    label: 'Файл', 
    color: 'text-yellow-400',
    bg: 'bg-yellow-500/10',
    border: 'border-yellow-500/30'
  }
}

function ToolCallCard({ call }: { call: ToolCall }) {
  const [expanded, setExpanded] = useState(false)
  const config = typeConfig[call.type]
  const Icon = config.icon
  
  const isRunning = call.status === 'running'
  const isError = call.status === 'error'
  
  return (
    <div 
      className={`rounded-lg border transition-all ${config.border} ${config.bg} ${
        isRunning ? 'ring-1 ring-purple-500/50 animate-pulse' : ''
      }`}
    >
      {/* Header */}
      <div 
        className="flex items-center justify-between p-3 cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-3">
          {/* Expand icon */}
          {expanded ? (
            <ChevronDown className="w-4 h-4 text-gray-400" />
          ) : (
            <ChevronRight className="w-4 h-4 text-gray-400" />
          )}
          
          {/* Type icon */}
          <div className={`p-1.5 rounded ${config.bg}`}>
            {isRunning ? (
              <Loader2 className={`w-4 h-4 ${config.color} animate-spin`} />
            ) : isError ? (
              <XCircle className="w-4 h-4 text-red-400" />
            ) : (
              <Icon className={`w-4 h-4 ${config.color}`} />
            )}
          </div>
          
          {/* Name */}
          <div>
            <span className="text-sm font-medium text-white">{call.name}</span>
            <span className={`ml-2 text-xs ${config.color}`}>{config.label}</span>
          </div>
        </div>
        
        {/* Metrics */}
        <div className="flex items-center gap-4 text-xs text-gray-400">
          {/* Duration */}
          <span className="flex items-center gap-1">
            <Clock className="w-3 h-3" />
            {isRunning ? '...' : `${call.duration_ms.toFixed(0)}ms`}
          </span>
          
          {/* Tokens */}
          {(call.tokens_in || call.tokens_out) && (
            <span className="flex items-center gap-1">
              <Zap className="w-3 h-3" />
              {call.tokens_in || 0} → {call.tokens_out || 0}
            </span>
          )}
          
          {/* Status indicator */}
          <div className={`w-2 h-2 rounded-full ${
            isRunning ? 'bg-purple-400 animate-pulse' :
            isError ? 'bg-red-400' :
            'bg-green-400'
          }`} />
        </div>
      </div>
      
      {/* Expanded content */}
      {expanded && (
        <div className="px-3 pb-3 space-y-2 border-t border-gray-700/50 pt-2">
          {/* Input */}
          <div>
            <div className="text-xs text-gray-500 mb-1">Input:</div>
            <pre className="text-xs text-gray-300 bg-gray-900/70 p-2 rounded overflow-x-auto max-h-32 overflow-y-auto">
              {call.input_preview || '—'}
            </pre>
          </div>
          
          {/* Output */}
          {call.output_preview && (
            <div>
              <div className="text-xs text-gray-500 mb-1">Output:</div>
              <pre className={`text-xs p-2 rounded overflow-x-auto max-h-32 overflow-y-auto ${
                isError ? 'text-red-300 bg-red-900/20' : 'text-gray-300 bg-gray-900/70'
              }`}>
                {call.output_preview}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export function ToolCallsPanel({ toolCalls }: ToolCallsPanelProps) {
  const activeCount = toolCalls.filter(c => c.status === 'running').length
  const errorCount = toolCalls.filter(c => c.status === 'error').length
  
  // Сортируем: активные первые, потом по времени
  const sortedCalls = [...toolCalls].sort((a, b) => {
    if (a.status === 'running' && b.status !== 'running') return -1
    if (b.status === 'running' && a.status !== 'running') return 1
    return 0
  })
  
  return (
    <div className="h-full flex flex-col bg-gray-900/50">
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-gray-700/50 bg-gray-800/50">
        <div className="flex items-center gap-2">
          <Brain className="w-4 h-4 text-purple-400" />
          <span className="text-sm font-medium text-gray-300">
            Tool Calls ({toolCalls.length})
          </span>
        </div>
        
        <div className="flex items-center gap-3 text-xs">
          {activeCount > 0 && (
            <span className="flex items-center gap-1 text-purple-400">
              <Loader2 className="w-3 h-3 animate-spin" />
              {activeCount} активных
            </span>
          )}
          {errorCount > 0 && (
            <span className="flex items-center gap-1 text-red-400">
              <XCircle className="w-3 h-3" />
              {errorCount} ошибок
            </span>
          )}
        </div>
      </div>
      
      {/* List */}
      <div className="flex-1 overflow-auto p-3 space-y-2">
        {sortedCalls.length === 0 ? (
          <div className="flex items-center justify-center h-full text-gray-500">
            <span>Нет вызовов</span>
          </div>
        ) : (
          sortedCalls.map(call => (
            <ToolCallCard key={call.id} call={call} />
          ))
        )}
      </div>
    </div>
  )
}
