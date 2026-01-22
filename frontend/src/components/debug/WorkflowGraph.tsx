/**
 * Визуализация workflow в виде графа.
 * 
 * Показывает текущий этап и прогресс выполнения.
 */

import { StageStatus } from '../../hooks/useAgentStream'

interface WorkflowGraphProps {
  stages: Record<string, StageStatus>
}

interface WorkflowNode {
  id: string
  label: string
  labelRu: string
}

const WORKFLOW_NODES: WorkflowNode[] = [
  { id: 'intent', label: 'Intent', labelRu: 'Намерение' },
  { id: 'planning', label: 'Plan', labelRu: 'План' },
  { id: 'research', label: 'Research', labelRu: 'Контекст' },
  { id: 'testing', label: 'Tests', labelRu: 'Тесты' },
  { id: 'coding', label: 'Code', labelRu: 'Код' },
  { id: 'validation', label: 'Validate', labelRu: 'Проверка' },
  { id: 'critic', label: 'Review', labelRu: 'Ревью' },
  { id: 'reflection', label: 'Reflect', labelRu: 'Рефлексия' }
]

function getNodeStatus(stageStatus?: StageStatus): 'pending' | 'running' | 'completed' | 'error' {
  if (!stageStatus) return 'pending'
  switch (stageStatus.status) {
    case 'start':
    case 'progress':
      return 'running'
    case 'end':
      return 'completed'
    case 'error':
      return 'error'
    default:
      return 'pending'
  }
}

function getNodeColor(status: string): string {
  switch (status) {
    case 'running': return '#8b5cf6'   // purple
    case 'completed': return '#22c55e' // green
    case 'error': return '#ef4444'     // red
    default: return '#374151'          // gray
  }
}

function getNodeGlow(status: string): string {
  switch (status) {
    case 'running': return 'drop-shadow(0 0 8px rgba(139, 92, 246, 0.6))'
    case 'completed': return 'drop-shadow(0 0 4px rgba(34, 197, 94, 0.4))'
    case 'error': return 'drop-shadow(0 0 4px rgba(239, 68, 68, 0.4))'
    default: return 'none'
  }
}

export function WorkflowGraph({ stages }: WorkflowGraphProps) {
  // Расчёт позиций узлов (2 ряда по 4)
  const nodeWidth = 80
  const nodeHeight = 40
  const gapX = 30
  const gapY = 60
  const startX = 40
  const startY = 40

  const getPosition = (index: number) => {
    const row = Math.floor(index / 4)
    const col = index % 4
    return {
      x: startX + col * (nodeWidth + gapX),
      y: startY + row * (nodeHeight + gapY)
    }
  }

  // Найти текущий активный этап
  const currentStageId = Object.entries(stages).find(
    ([, status]) => status.status === 'start' || status.status === 'progress'
  )?.[0]

  // Статистика
  const completedCount = Object.values(stages).filter(s => s.status === 'end').length
  const totalTime = Object.values(stages).reduce((acc, s) => {
    if (s.thinking?.elapsedMs) return acc + s.thinking.elapsedMs
    return acc
  }, 0)

  return (
    <div className="h-full flex flex-col bg-gray-900/50 p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-gray-300">Workflow Graph</h3>
        <div className="flex items-center gap-4 text-xs text-gray-400">
          <span>{completedCount}/{WORKFLOW_NODES.length} этапов</span>
          {totalTime > 0 && <span>{(totalTime / 1000).toFixed(1)}с thinking</span>}
        </div>
      </div>

      {/* Graph */}
      <div className="flex-1 flex items-center justify-center">
        <svg 
          viewBox="0 0 480 180" 
          className="w-full max-w-2xl"
          style={{ maxHeight: '200px' }}
        >
          {/* Connections */}
          {WORKFLOW_NODES.map((node, i) => {
            if (i === WORKFLOW_NODES.length - 1) return null
            
            const pos = getPosition(i)
            const nextPos = getPosition(i + 1)
            const status = getNodeStatus(stages[node.id])
            const nextStatus = getNodeStatus(stages[WORKFLOW_NODES[i + 1].id])
            
            // Определяем цвет линии
            let lineColor = '#374151'
            if (status === 'completed' && nextStatus !== 'pending') {
              lineColor = '#22c55e'
            } else if (status === 'running') {
              lineColor = '#8b5cf6'
            }
            
            // Для перехода между рядами
            if (i === 3) {
              // Вертикальная линия вниз
              return (
                <g key={`line-${i}`}>
                  <line
                    x1={pos.x + nodeWidth}
                    y1={pos.y + nodeHeight / 2}
                    x2={pos.x + nodeWidth + 15}
                    y2={pos.y + nodeHeight / 2}
                    stroke={lineColor}
                    strokeWidth={2}
                  />
                  <line
                    x1={pos.x + nodeWidth + 15}
                    y1={pos.y + nodeHeight / 2}
                    x2={pos.x + nodeWidth + 15}
                    y2={nextPos.y + nodeHeight / 2}
                    stroke={lineColor}
                    strokeWidth={2}
                  />
                  <line
                    x1={pos.x + nodeWidth + 15}
                    y1={nextPos.y + nodeHeight / 2}
                    x2={nextPos.x}
                    y2={nextPos.y + nodeHeight / 2}
                    stroke={lineColor}
                    strokeWidth={2}
                  />
                </g>
              )
            }
            
            // Горизонтальная линия
            return (
              <line
                key={`line-${i}`}
                x1={pos.x + nodeWidth}
                y1={pos.y + nodeHeight / 2}
                x2={nextPos.x}
                y2={nextPos.y + nodeHeight / 2}
                stroke={lineColor}
                strokeWidth={2}
                strokeDasharray={status === 'pending' ? '4 4' : 'none'}
              />
            )
          })}

          {/* Nodes */}
          {WORKFLOW_NODES.map((node, i) => {
            const pos = getPosition(i)
            const status = getNodeStatus(stages[node.id])
            const color = getNodeColor(status)
            const glow = getNodeGlow(status)
            const isActive = node.id === currentStageId
            
            return (
              <g 
                key={node.id}
                style={{ filter: glow }}
              >
                {/* Node background */}
                <rect
                  x={pos.x}
                  y={pos.y}
                  width={nodeWidth}
                  height={nodeHeight}
                  rx={8}
                  fill={color}
                  className={isActive ? 'animate-pulse' : ''}
                />
                
                {/* Progress ring for active */}
                {isActive && (
                  <circle
                    cx={pos.x + nodeWidth / 2}
                    cy={pos.y + nodeHeight / 2}
                    r={nodeHeight / 2 + 5}
                    fill="none"
                    stroke="#8b5cf6"
                    strokeWidth={2}
                    strokeDasharray="8 4"
                    className="animate-spin"
                    style={{ 
                      transformOrigin: `${pos.x + nodeWidth / 2}px ${pos.y + nodeHeight / 2}px`,
                      animationDuration: '3s'
                    }}
                  />
                )}
                
                {/* Label */}
                <text
                  x={pos.x + nodeWidth / 2}
                  y={pos.y + nodeHeight / 2 - 4}
                  textAnchor="middle"
                  fill="white"
                  fontSize={11}
                  fontWeight={500}
                >
                  {node.label}
                </text>
                <text
                  x={pos.x + nodeWidth / 2}
                  y={pos.y + nodeHeight / 2 + 10}
                  textAnchor="middle"
                  fill="rgba(255,255,255,0.6)"
                  fontSize={8}
                >
                  {node.labelRu}
                </text>
                
                {/* Status icon */}
                {status === 'completed' && (
                  <text
                    x={pos.x + nodeWidth - 10}
                    y={pos.y + 12}
                    fill="white"
                    fontSize={10}
                  >
                    ✓
                  </text>
                )}
                {status === 'error' && (
                  <text
                    x={pos.x + nodeWidth - 10}
                    y={pos.y + 12}
                    fill="white"
                    fontSize={10}
                  >
                    ✕
                  </text>
                )}
              </g>
            )
          })}
        </svg>
      </div>

      {/* Legend */}
      <div className="flex items-center justify-center gap-6 mt-4 text-xs text-gray-400">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded bg-gray-600" />
          <span>Ожидание</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded bg-purple-500 animate-pulse" />
          <span>Выполняется</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded bg-green-500" />
          <span>Готово</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded bg-red-500" />
          <span>Ошибка</span>
        </div>
      </div>
    </div>
  )
}
