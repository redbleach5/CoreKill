/**
 * Главная панель Under The Hood.
 * 
 * Объединяет все debug-компоненты в единый интерфейс с табами.
 */

import { useState } from 'react'
import { 
  Eye, 
  X, 
  Terminal, 
  Brain, 
  GitBranch, 
  BarChart3,
  Minimize2,
  Maximize2
} from 'lucide-react'
import { LiveLogsPanel, LogEntry } from './LiveLogsPanel'
import { ToolCallsPanel, ToolCall } from './ToolCallsPanel'
import { WorkflowGraph } from './WorkflowGraph'
import { MetricsDashboard } from '../MetricsDashboard'
import { StageStatus } from '../../hooks/useAgentStream'

type TabId = 'logs' | 'tools' | 'graph' | 'metrics'

interface TabConfig {
  id: TabId
  label: string
  icon: typeof Terminal
}

const tabs: TabConfig[] = [
  { id: 'logs', label: 'Логи', icon: Terminal },
  { id: 'tools', label: 'Вызовы', icon: Brain },
  { id: 'graph', label: 'Граф', icon: GitBranch },
  { id: 'metrics', label: 'Метрики', icon: BarChart3 }
]

interface UnderTheHoodPanelProps {
  isOpen: boolean
  onClose: () => void
  logs: LogEntry[]
  toolCalls: ToolCall[]
  stages: Record<string, StageStatus>
  onClearLogs?: () => void
}

export function UnderTheHoodPanel({
  isOpen,
  onClose,
  logs,
  toolCalls,
  stages,
  onClearLogs
}: UnderTheHoodPanelProps) {
  const [activeTab, setActiveTab] = useState<TabId>('logs')
  const [isMaximized, setIsMaximized] = useState(false)
  
  if (!isOpen) return null
  
  const activeCallsCount = toolCalls.filter(c => c.status === 'running').length
  const errorsCount = logs.filter(l => l.level === 'error').length
  
  return (
    <div className={`fixed z-50 bg-gray-900/95 backdrop-blur-sm border border-gray-700/50 rounded-xl shadow-2xl flex flex-col transition-all duration-300 ${
      isMaximized 
        ? 'inset-4' 
        : 'bottom-4 right-4 w-[600px] h-[450px]'
    }`}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-700/50 bg-gray-800/50 rounded-t-xl">
        <div className="flex items-center gap-3">
          <div className="p-1.5 bg-purple-500/20 rounded-lg">
            <Eye className="w-4 h-4 text-purple-400" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-white">Under The Hood</h2>
            <p className="text-xs text-gray-500">Что происходит внутри</p>
          </div>
        </div>
        
        {/* Status indicators */}
        <div className="flex items-center gap-4">
          {activeCallsCount > 0 && (
            <span className="flex items-center gap-1.5 text-xs text-purple-400">
              <span className="w-2 h-2 bg-purple-400 rounded-full animate-pulse" />
              {activeCallsCount} активных
            </span>
          )}
          {errorsCount > 0 && (
            <span className="flex items-center gap-1.5 text-xs text-red-400">
              <span className="w-2 h-2 bg-red-400 rounded-full" />
              {errorsCount} ошибок
            </span>
          )}
        </div>
        
        {/* Controls */}
        <div className="flex items-center gap-1">
          <button
            onClick={() => setIsMaximized(!isMaximized)}
            className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-gray-700/50 transition-colors"
            title={isMaximized ? 'Уменьшить' : 'Развернуть'}
          >
            {isMaximized ? (
              <Minimize2 className="w-4 h-4" />
            ) : (
              <Maximize2 className="w-4 h-4" />
            )}
          </button>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-gray-700/50 transition-colors"
            title="Закрыть"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>
      
      {/* Tabs */}
      <div className="flex border-b border-gray-700/50 bg-gray-800/30">
        {tabs.map(tab => {
          const Icon = tab.icon
          const isActive = activeTab === tab.id
          
          // Badges
          let badge = null
          if (tab.id === 'logs' && logs.length > 0) {
            badge = <span className="ml-1.5 text-[10px] bg-gray-700 px-1.5 rounded-full">{logs.length}</span>
          } else if (tab.id === 'tools' && activeCallsCount > 0) {
            badge = <span className="ml-1.5 text-[10px] bg-purple-500/30 text-purple-300 px-1.5 rounded-full animate-pulse">{activeCallsCount}</span>
          }
          
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2.5 text-sm transition-colors border-b-2 ${
                isActive 
                  ? 'text-white border-purple-500 bg-purple-500/10' 
                  : 'text-gray-400 border-transparent hover:text-white hover:bg-gray-700/30'
              }`}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
              {badge}
            </button>
          )
        })}
      </div>
      
      {/* Content */}
      <div className="flex-1 overflow-hidden">
        {activeTab === 'logs' && (
          <LiveLogsPanel logs={logs} onClear={onClearLogs} />
        )}
        {activeTab === 'tools' && (
          <ToolCallsPanel toolCalls={toolCalls} />
        )}
        {activeTab === 'graph' && (
          <WorkflowGraph stages={stages} />
        )}
        {activeTab === 'metrics' && (
          <MetricsDashboard />
        )}
      </div>
    </div>
  )
}
