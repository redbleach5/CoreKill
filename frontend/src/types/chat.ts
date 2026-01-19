/**
 * Типы для чат-интерфейса
 */

import { StageStatus, Metrics } from '../hooks/useAgentStream'

// Типы режимов взаимодействия
export type InteractionMode = 'auto' | 'chat' | 'code'

// Метаданные сообщения
export interface ChatMessageMetadata {
  intentType?: string
  code?: string
  tests?: string
  stages?: Record<string, StageStatus>
  metrics?: Metrics
  quality?: number
}

// Типы сообщений в чате
export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  type: 'text' | 'code' | 'progress' | 'error'
  timestamp: Date
  metadata?: ChatMessageMetadata
}

// Конфигурация режимов
export interface ModeConfig {
  label: string
  icon: React.ComponentType<{ className?: string }>
  description: string
}

export const MODE_CONFIGS: Record<InteractionMode, ModeConfig> = {
  auto: { label: 'Авто', icon: () => null, description: 'Автовыбор режима' },
  chat: { label: 'Диалог', icon: () => null, description: 'Простое общение' },
  code: { label: 'Код', icon: () => null, description: 'Генерация с тестами' }
}
