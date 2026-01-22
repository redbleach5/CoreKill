/**
 * Константы для SSE событий
 */

// Типы SSE событий от backend
export const SSE_EVENTS = {
  STAGE_START: 'stage_start',
  STAGE_PROGRESS: 'stage_progress',
  STAGE_END: 'stage_end',
  CODE_CHUNK: 'code_chunk', // Стриминг кода по частям
  // Thinking события для reasoning моделей (DeepSeek-R1, QwQ)
  THINKING_STARTED: 'thinking_started',
  THINKING_IN_PROGRESS: 'thinking_in_progress',
  THINKING_COMPLETED: 'thinking_completed',
  THINKING_INTERRUPTED: 'thinking_interrupted',
  // Phase 7: Under The Hood
  LOG: 'log',                           // Live log entry
  TOOL_CALL_START: 'tool_call_start',   // Tool/LLM call started
  TOOL_CALL_END: 'tool_call_end',       // Tool/LLM call ended
  METRICS_UPDATE: 'metrics_update',     // Real-time metrics
  ERROR: 'error',
  WARNING: 'warning',
  COMPLETE: 'complete'
} as const

// Названия этапов агентов
export const AGENT_STAGES = {
  INTENT: 'intent',
  PLANNING: 'planning',
  RESEARCH: 'research',
  TESTING: 'testing',
  CODING: 'coding',
  VALIDATION: 'validation',
  DEBUG: 'debug',
  FIXING: 'fixing',
  REFLECTION: 'reflection',
  CRITIC: 'critic',
  GREETING: 'greeting',
  HELP: 'help',
  CHAT: 'chat'
} as const

// Типы intent (тип задачи)
export const INTENT_TYPES = {
  CREATE: 'create',
  MODIFY: 'modify',
  DEBUG: 'debug',
  OPTIMIZE: 'optimize',
  EXPLAIN: 'explain',
  TEST: 'test',
  REFACTOR: 'refactor',
  GREETING: 'greeting',
  HELP: 'help',
  CHAT: 'chat'
} as const

// Простые ответы (без генерации кода)
export const SIMPLE_RESPONSE_INTENTS = [
  INTENT_TYPES.GREETING,
  INTENT_TYPES.HELP,
  INTENT_TYPES.CHAT
] as const

export type SSEEventType = typeof SSE_EVENTS[keyof typeof SSE_EVENTS]
export type AgentStage = typeof AGENT_STAGES[keyof typeof AGENT_STAGES]
export type IntentType = typeof INTENT_TYPES[keyof typeof INTENT_TYPES]
