/**
 * Централизованный API клиент для всех запросов к backend.
 * 
 * Обеспечивает:
 * - Единую обработку ошибок
 * - Автоматическое определение dev/prod режима
 * - Типобезопасные методы для всех endpoints
 * - Поддержку SSE для стриминга
 * 
 * Использование:
 *   import { api } from './services/apiClient'
 *   
 *   const models = await api.models.list()
 *   const conversation = await api.conversations.get(id)
 */
import { extractErrorMessage } from '../utils/apiErrorHandler'
import type {
  ModelsResponse,
  ConversationsListResponse,
  ConversationResponse,
  ProjectFilesResponse,
  FileContentResponse,
  IndexProjectRequest,
  IndexProjectResponse,
  MetricsResponse,
  CodeExecutionRequest,
  CodeExecutionResponse,
  CodeValidationRequest,
  CodeValidationResponse,
  SettingsResponse,
  BrowseFolderResponse
} from '../types/api'

/**
 * Определяет базовый URL для API запросов.
 * 
 * @returns Базовый URL (пустая строка для production, localhost:8000 для dev)
 */
function getBaseUrl(): string {
  const isDev = typeof window !== 'undefined' && window.location.port === '5173'
  return isDev ? 'http://localhost:8000' : ''
}

/**
 * Создаёт полный URL для API endpoint.
 * 
 * @param endpoint - Endpoint (например, '/api/models')
 * @returns Полный URL
 */
function getApiUrl(endpoint: string): string {
  const baseUrl = getBaseUrl()
  // Убираем ведущий слэш если он есть, чтобы избежать двойных слэшей
  const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`
  return `${baseUrl}${cleanEndpoint}`
}

/**
 * Выполняет fetch запрос с обработкой ошибок.
 * 
 * @param url - URL для запроса
 * @param options - Опции для fetch
 * @returns Promise с Response
 * @throws Error с понятным сообщением на русском языке
 */
async function fetchWithErrorHandling(
  url: string,
  options: RequestInit = {}
): Promise<Response> {
  try {
    const response = await fetch(url, {
      ...options,
      signal: AbortSignal.timeout(30000) // 30 секунд timeout
    })
    
    if (!response.ok) {
      const errorMessage = await handleApiResponse(response)
      throw new Error(errorMessage || `HTTP ${response.status}: ${response.statusText}`)
    }
    
    return response
  } catch (error) {
    // Обрабатываем AbortError (timeout)
    if (error instanceof Error && error.name === 'AbortError') {
      throw new Error('Превышено время ожидания ответа от сервера (30 секунд)')
    }
    
    // Обрабатываем сетевые ошибки
    if (error instanceof TypeError && error.message.includes('fetch')) {
      throw new Error('Ошибка подключения к серверу. Проверьте, что backend запущен.')
    }
    
    // Пробрасываем остальные ошибки
    throw error
  }
}

/**
 * Обрабатывает ответ от fetch запроса и извлекает ошибку если есть.
 * 
 * @param response - Response объект от fetch
 * @returns Promise с сообщением об ошибке или null если успешно
 */
async function handleApiResponse(response: Response): Promise<string | null> {
  if (response.ok) {
    return null
  }
  
  try {
    const errorData = await response.json()
    return extractErrorMessage(errorData)
  } catch {
    // Если не удалось распарсить JSON, используем статус
    return `Ошибка ${response.status}: ${response.statusText}`
  }
}

/**
 * Базовые методы для HTTP запросов.
 */
const apiClient = {
  /**
   * Выполняет GET запрос.
   * 
   * @param endpoint - Endpoint (например, '/api/models')
   * @returns Promise с данными ответа
   */
  async get<T>(endpoint: string): Promise<T> {
    const url = getApiUrl(endpoint)
    const response = await fetchWithErrorHandling(url)
    return response.json() as Promise<T>
  },
  
  /**
   * Выполняет POST запрос.
   * 
   * @param endpoint - Endpoint
   * @param body - Тело запроса (будет сериализовано в JSON)
   * @returns Promise с данными ответа
   */
  async post<T>(endpoint: string, body?: unknown): Promise<T> {
    const url = getApiUrl(endpoint)
    const response = await fetchWithErrorHandling(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: body ? JSON.stringify(body) : undefined
    })
    return response.json() as Promise<T>
  },
  
  /**
   * Выполняет DELETE запрос.
   * 
   * @param endpoint - Endpoint
   * @returns Promise с данными ответа
   */
  async delete<T>(endpoint: string): Promise<T> {
    const url = getApiUrl(endpoint)
    const response = await fetchWithErrorHandling(url, {
      method: 'DELETE'
    })
    return response.json() as Promise<T>
  },
  
  /**
   * Создаёт EventSource для SSE соединения.
   * 
   * @param endpoint - Endpoint (например, '/api/stream')
   * @param params - URL параметры
   * @returns EventSource объект
   */
  createSSE(endpoint: string, params: URLSearchParams): EventSource {
    const baseUrl = getBaseUrl()
    const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`
    const url = `${baseUrl}${cleanEndpoint}?${params.toString()}`
    return new EventSource(url)
  }
}

/**
 * Типизированные методы для всех API endpoints.
 */
export const api = {
  /**
   * Методы для работы с моделями.
   */
  models: {
    /**
     * Получает список доступных моделей.
     */
    list: () => apiClient.get<ModelsResponse>('/api/models'),
    
    /**
     * Обновляет список моделей (сканирует Ollama).
     */
    refresh: () => apiClient.post<{ status: string; models: string[] }>('/api/models/refresh')
  },
  
  /**
   * Методы для работы с диалогами.
   */
  conversations: {
    /**
     * Получает список всех диалогов.
     */
    list: () => apiClient.get<ConversationsListResponse>('/api/conversations'),
    
    /**
     * Получает конкретный диалог по ID.
     */
    get: (id: string) => apiClient.get<ConversationResponse>(`/api/conversations/${id}`),
    
    /**
     * Удаляет диалог по ID.
     */
    delete: (id: string) => apiClient.delete<{ status: string }>(`/api/conversations/${id}`),
    
    /**
     * Создаёт новый диалог.
     */
    create: () => apiClient.post<{ conversation_id: string }>('/api/conversations/new')
  },
  
  /**
   * Методы для работы с проектами и файлами.
   */
  projects: {
    /**
     * Получает дерево файлов проекта.
     */
    getFiles: (projectPath: string, fileExtensions?: string) => {
      const params = new URLSearchParams({ path: projectPath })
      if (fileExtensions) {
        params.set('extensions', fileExtensions)
      }
      return apiClient.get<ProjectFilesResponse>(`/api/project-files?${params.toString()}`)
    },
    
    /**
     * Получает содержимое файла.
     */
    getFileContent: (filePath: string) => {
      return apiClient.get<FileContentResponse>(`/api/file-content?path=${encodeURIComponent(filePath)}`)
    },
    
    /**
     * Индексирует проект для RAG.
     */
    index: (request: IndexProjectRequest) => {
      return apiClient.post<IndexProjectResponse>('/api/index', request)
    },
    
    /**
     * Открывает диалог выбора папки.
     */
    browseFolder: (startPath?: string) => {
      const url = startPath
        ? `/api/browse-folder?start_path=${encodeURIComponent(startPath)}`
        : '/api/browse-folder'
      return apiClient.get<BrowseFolderResponse>(url)
    }
  },
  
  /**
   * Методы для работы с метриками.
   */
  metrics: {
    /**
     * Получает общие метрики производительности.
     */
    get: () => apiClient.get<MetricsResponse>('/api/metrics'),
    
    /**
     * Получает метрики по этапам.
     * Возвращает объект с полями: benchmark, stages, estimates, has_calibration, total_samples
     */
    getStages: () => apiClient.get<{ 
      benchmark?: unknown
      stages?: Record<string, unknown>
      estimates?: Record<string, number>
      has_calibration?: boolean
      total_samples?: number
    }>('/api/metrics/stages'),
    
    /**
     * Запускает бенчмарк производительности.
     */
    benchmark: () => apiClient.post<{ status: string }>('/api/metrics/benchmark')
  },
  
  /**
   * Методы для выполнения и валидации кода.
   */
  code: {
    /**
     * Выполняет код в изолированной среде.
     */
    execute: (request: CodeExecutionRequest) => {
      return apiClient.post<CodeExecutionResponse>('/api/code/execute', request)
    },
    
    /**
     * Валидирует синтаксис кода.
     */
    validate: (request: CodeValidationRequest) => {
      return apiClient.post<CodeValidationResponse>('/api/code/validate', request)
    }
  },
  
  /**
   * Методы для работы с настройками.
   */
  settings: {
    /**
     * Получает текущие настройки.
     */
    get: () => apiClient.get<SettingsResponse>('/api/settings')
  },
  
  /**
   * Методы для работы с задачами.
   */
  tasks: {
    /**
     * Получает список активных задач.
     */
    getActive: () => apiClient.get<{ tasks: unknown[] }>('/api/tasks/active'),
    
    /**
     * Получает историю задач.
     */
    getHistory: () => apiClient.get<{ tasks: unknown[] }>('/api/tasks/history'),
    
    /**
     * Получает конкретную задачу по ID.
     */
    get: (taskId: string) => apiClient.get<unknown>(`/api/tasks/${taskId}`),
    
    /**
     * Возобновляет выполнение задачи.
     */
    resume: (taskId: string) => apiClient.post<{ status: string }>(`/api/tasks/${taskId}/resume`),
    
    /**
     * Удаляет задачу.
     */
    delete: (taskId: string) => apiClient.delete<{ status: string }>(`/api/tasks/${taskId}`),
    
    /**
     * Отменяет выполнение задачи.
     */
    cancel: (taskId: string) => apiClient.post<{ status: string }>(`/api/tasks/${taskId}/cancel`)
  },
  
  /**
   * Методы для работы с базами данных.
   */
  databases: {
    /**
     * Получает список баз данных.
     */
    list: () => apiClient.get<{ status: string; count: number; databases: unknown[] }>('/api/databases/list'),
    
    /**
     * Получает статистику по базам данных.
     */
    getStats: () => apiClient.get<unknown>('/api/databases/stats'),
    
    /**
     * Создаёт бэкап базы данных.
     */
    backup: (database?: string, name?: string) => {
      return apiClient.post<{ status: string; backup_path?: string }>('/api/databases/backup', {
        database,
        name
      })
    },
    
    /**
     * Восстанавливает базу данных из бэкапа.
     */
    restore: (backupPath: string, targetDatabase?: string) => {
      return apiClient.post<{ status: string }>('/api/databases/restore', {
        backup_path: backupPath,
        target_database: targetDatabase
      })
    },
    
    /**
     * Очищает старые данные из базы данных.
     */
    cleanup: (database: string, days: number = 30, execute: boolean = false) => {
      return apiClient.post<{ status: string; deleted_count?: number }>('/api/databases/cleanup', {
        database,
        days,
        execute
      })
    },
    
    /**
     * Получает список бэкапов.
     */
    getBackups: () => apiClient.get<{ backups: unknown[] }>('/api/databases/backups')
  },
  
  /**
   * Создаёт SSE соединение для стриминга.
   * 
   * @param params - URL параметры для стриминга
   * @returns EventSource объект
   */
  stream: (params: URLSearchParams) => {
    return apiClient.createSSE('/api/stream', params)
  }
}

/**
 * Экспортируем также базовый клиент для случаев, когда нужен прямой доступ.
 */
export { apiClient }
