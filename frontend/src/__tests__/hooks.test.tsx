/**
 * Тесты для кастомных хуков.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { useLocalStorage, useLocalStorageString } from '../hooks/useLocalStorage'
import { useModels } from '../hooks/useModels'
import { useApi } from '../hooks/useApi'
import { api } from '../services/apiClient'
import { mockApiResponse, mockApiError } from './utils/testHelpers'
import { TEST_DATA } from './utils/constants'

describe('useLocalStorage', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('should return initial value when key does not exist', () => {
    const { result } = renderHook(() => useLocalStorage('test-key', 'default'))
    
    expect(result.current[0]).toBe('default')
  })

  it('should save and retrieve value', () => {
    const { result } = renderHook(() => useLocalStorage('test-key', 'default'))
    
    const [, setValue] = result.current
    setValue('new-value')
    
    expect(result.current[0]).toBe('new-value')
    expect(localStorage.getItem('test-key')).toBe('"new-value"')
  })

  it('should handle JSON serialization', () => {
    const { result } = renderHook(() => 
      useLocalStorage('test-key', { foo: 'bar' })
    )
    
    const [, setValue] = result.current
    setValue({ foo: 'baz' })
    
    expect(result.current[0]).toEqual({ foo: 'baz' })
    expect(JSON.parse(localStorage.getItem('test-key') || '{}')).toEqual({ foo: 'baz' })
  })
})

describe('useLocalStorageString', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('should return initial value when key does not exist', () => {
    const { result } = renderHook(() => useLocalStorageString('test-key', 'default'))
    
    expect(result.current[0]).toBe('default')
  })

  it('should save and retrieve string value', () => {
    const { result } = renderHook(() => useLocalStorageString('test-key', 'default'))
    
    const [, setValue] = result.current
    setValue('new-value')
    
    expect(result.current[0]).toBe('new-value')
    expect(localStorage.getItem('test-key')).toBe('new-value')
  })
})

describe('useModels', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should load models on mount', async () => {
    ;(global.fetch as any).mockResolvedValueOnce(
      mockApiResponse(TEST_DATA.MODELS_RESPONSE)
    )

    const { result } = renderHook(() => useModels())
    
    expect(result.current.loading).toBe(true)
    
    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })
    
    expect(result.current.models).toEqual(TEST_DATA.MODELS_RESPONSE.models)
    expect(result.current.error).toBeNull()
  })

  it('should handle errors', async () => {
    ;(global.fetch as any).mockRejectedValueOnce(new Error('Network error'))

    const { result } = renderHook(() => useModels())
    
    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })
    
    expect(result.current.error).toBeTruthy()
    expect(result.current.models).toEqual([])
  })
})

describe('useApi', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should fetch data on mount', async () => {
    const mockResponse = { data: 'test' }
    
    ;(global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    })

    const { result } = renderHook(() => 
      useApi(() => api.models.list(), { immediate: true })
    )
    
    expect(result.current.loading).toBe(true)
    
    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })
    
    expect(result.current.data).toEqual(mockResponse)
    expect(result.current.error).toBeNull()
  })

  it('should handle errors', async () => {
    ;(global.fetch as any).mockRejectedValueOnce(new Error('Network error'))

    const { result } = renderHook(() => 
      useApi(() => api.models.list(), { immediate: true })
    )
    
    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })
    
    expect(result.current.error).toBeTruthy()
    expect(result.current.data).toBeNull()
  })

  it('should support refetch', async () => {
    const mockResponse = { data: 'test' }
    
    ;(global.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => mockResponse,
    })

    const { result } = renderHook(() => 
      useApi(() => api.models.list(), { immediate: false })
    )
    
    expect(result.current.loading).toBe(false)
    
    await result.current.refetch()
    
    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })
    
    expect(result.current.data).toEqual(mockResponse)
  })
})
