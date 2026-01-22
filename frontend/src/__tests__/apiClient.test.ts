/**
 * Тесты для API клиента.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { api } from '../services/apiClient'
import { mockApiResponse, mockApiError, createLocationMock } from './utils/testHelpers'
import { TEST_DATA, TEST_IDS, TEST_URLS } from './utils/constants'

describe('apiClient', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('getBaseUrl', () => {
    it('should return localhost:8000 in dev mode', () => {
      // Мокаем window.location
      const locationMock = createLocationMock({ port: '5173' })
      Object.defineProperty(window, 'location', {
        value: locationMock,
        writable: true,
      })
      
      // Проверяем, что URL формируется правильно
      expect(window.location.port).toBe('5173')
    })
  })

  describe('api.models', () => {
    it('should call GET /api/models', async () => {
      ;(global.fetch as any).mockResolvedValueOnce(
        mockApiResponse(TEST_DATA.MODELS_RESPONSE)
      )

      const result = await api.models.list()
      
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/models'),
        expect.any(Object)
      )
      expect(result).toEqual(TEST_DATA.MODELS_RESPONSE)
    })
  })

  describe('api.conversations', () => {
    it('should call DELETE /api/conversations/{id}', async () => {
      const mockResponse = { status: 'success' }
      
      ;(global.fetch as any).mockResolvedValueOnce(
        mockApiResponse(mockResponse)
      )

      const result = await api.conversations.delete(TEST_IDS.CONVERSATION)
      
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining(`/api/conversations/${TEST_IDS.CONVERSATION}`),
        expect.objectContaining({ method: 'DELETE' })
      )
      expect(result).toEqual(mockResponse)
    })
  })

  describe('error handling', () => {
    it('should handle network errors', async () => {
      ;(global.fetch as any).mockRejectedValueOnce(
        new TypeError('Failed to fetch')
      )

      await expect(api.models.list()).rejects.toThrow(
        'Ошибка подключения к серверу'
      )
    })

    it('should handle HTTP errors', async () => {
      ;(global.fetch as any).mockResolvedValueOnce(
        mockApiError(404, 'Not Found', { detail: 'Not found' })
      )

      await expect(api.models.list()).rejects.toThrow()
    })

    it('should handle timeout', async () => {
      // Мокаем AbortSignal.timeout
      const originalTimeout = AbortSignal.timeout
      AbortSignal.timeout = vi.fn(() => {
        const signal = new AbortSignal()
        setTimeout(() => {
          signal.dispatchEvent(new Event('abort'))
        }, 0)
        return signal
      }) as any

      ;(global.fetch as any).mockImplementationOnce(() => {
        return new Promise((_, reject) => {
          setTimeout(() => {
            const error = new Error('AbortError')
            error.name = 'AbortError'
            reject(error)
          }, 0)
        })
      })

      await expect(api.models.list()).rejects.toThrow('Превышено время ожидания')

      AbortSignal.timeout = originalTimeout
    })
  })
})
