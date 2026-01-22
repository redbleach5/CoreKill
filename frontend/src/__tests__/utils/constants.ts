/**
 * Константы для frontend тестов.
 * 
 * Централизованное место для всех тестовых констант.
 */

// Тестовые модели
export const TEST_MODELS = {
  SIMPLE: 'phi3:mini',
  MEDIUM: 'qwen2.5-coder:7b',
  COMPLEX: 'deepseek-r1:7b',
  DEFAULT: 'test-model',
} as const

// Тестовые ID
export const TEST_IDS = {
  CONVERSATION: 'conv-test-123',
  TASK: 'task-test-123',
  MESSAGE: 'msg-test-123',
} as const

// Тестовые URL
export const TEST_URLS = {
  DEV: 'http://localhost:8000',
  PROD: '',
  FRONTEND_DEV: 'http://localhost:5173',
} as const

// Тестовые данные
export const TEST_DATA = {
  MODELS_RESPONSE: {
    models: ['model1', 'model2'],
    models_detailed: [],
    count: 2,
  },
  CONVERSATION: {
    id: TEST_IDS.CONVERSATION,
    title: 'Test Conversation',
    preview: 'Test preview',
    created_at: '2026-01-21T00:00:00Z',
    updated_at: '2026-01-21T00:00:00Z',
    message_count: 5,
    has_summary: false,
  },
  SETTINGS: {
    model: '',
    temperature: 0.25,
    topP: 0.9,
    maxIterations: 3,
    maxTokens: 4096,
    enableWebSearch: true,
    webSearchMaxResults: 3,
    enableRAG: true,
    ragSimilarityThreshold: 0.5,
    qualityThreshold: 0.7,
  },
} as const

// Таймауты
export const TEST_TIMEOUTS = {
  SHORT: 1000,
  MEDIUM: 5000,
  LONG: 10000,
  API: 30000,
} as const
