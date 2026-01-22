/**
 * TypeScript типы для API ответов
 * 
 * Синхронизированы с backend Pydantic моделями.
 */

// ========== Models API ==========

export interface ModelInfo {
  name: string
  size_gb: number
  parameters: string
  family: string
  is_coder: boolean
  is_reasoning: boolean
  quality_score: number
  recommended_for: string[]
}

export interface ModelsResponse {
  models: string[]
  models_detailed: ModelInfo[]
  count: number
  recommendations: {
    simple?: string
    medium?: string
    complex?: string
  }
}

// ========== Conversations API ==========

export interface ConversationPreview {
  id: string
  title?: string
  preview?: string
  created_at: string
  updated_at: string
  message_count: number
  has_summary: boolean
}

export interface ConversationResponse {
  id: string
  created_at: string
  updated_at: string
  summary: string | null
  messages: Message[]
}

export interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: string
  metadata?: Record<string, unknown>
}

export interface ConversationsListResponse {
  conversations: ConversationPreview[]
  total: number
}

// ========== Project Files API ==========

export interface FileTreeNode {
  name: string
  path: string
  type: 'file' | 'directory'
  extension?: string
  size?: number
  children?: FileTreeNode[]
  truncated?: boolean
  error?: string
}

export interface ProjectFilesResponse {
  tree: FileTreeNode
  stats: {
    total_files: number
    total_directories: number
    root_path: string
  }
  error?: string
}

export interface FileContentResponse {
  path: string
  name: string
  content: string
  size: number
  error?: string
}

// ========== Index API ==========

export interface IndexProjectRequest {
  project_path: string
  file_extensions: string[]
}

export interface IndexProjectResponse {
  status: 'success' | 'error'
  project_path: string
  indexed_files: number
  total_chunks: number
  extensions: string[]
  error?: string
}

// ========== Metrics API ==========

export interface StageMetrics {
  stage: string
  average_time: number
  median_time: number
  count: number
  estimated_time: number
}

export interface MetricsResponse {
  benchmark: {
    model_used: string
    tokens_per_second: number
    performance_multiplier: number
    timestamp: string
  } | null
  stages: Record<string, StageMetrics>
  system_info: {
    platform: string
    python_version: string
  }
}

// ========== Code Execution API ==========

export interface CodeExecutionRequest {
  code: string
  language: string
  timeout: number
}

export interface CodeExecutionResponse {
  success: boolean
  output: string
  error?: string
  execution_time: number
}

export interface CodeValidationRequest {
  code: string
  language: string
}

export interface CodeValidationResponse {
  valid: boolean
  error?: string
  line?: number
  offset?: number
}

// ========== Settings API ==========

export interface SettingsResponse {
  interaction: {
    default_mode: string
    auto_confirm: boolean
    show_thinking: boolean
    max_context_messages: number
    persist_conversations: boolean
    chat_model: string
    chat_model_fallback: string
  }
  llm: {
    default_model: string
    temperature: number
    tokens_chat: number
    tokens_code: number
  }
  quality: {
    threshold: number
    confidence_threshold: number
  }
  web_search: {
    enabled: boolean
    timeout: number
  }
  modes: Array<{
    id: string
    name: string
    description: string
  }>
}

// ========== Browse Folder API ==========

export interface BrowseFolderResponse {
  path?: string
  name?: string
  exists?: boolean
  cancelled?: boolean
}

// ========== Validation API ==========

/**
 * Результат валидации от конкретного инструмента (pytest, mypy, bandit).
 */
export interface ToolValidationResult {
  success: boolean
  output?: string
  errors?: string
  issues?: string
}

/**
 * Полный результат валидации кода (pytest, mypy, bandit).
 * Используется в workflow для проверки качества кода.
 */
export interface ValidationResult {
  success: boolean
  pytest_passed: boolean
  mypy_passed: boolean
  bandit_passed: boolean
  pytest?: ToolValidationResult
  mypy?: ToolValidationResult
  bandit?: ToolValidationResult
  errors?: string[]
}
