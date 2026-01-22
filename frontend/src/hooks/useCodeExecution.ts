/**
 * Hook для выполнения кода через backend API
 */
import { useState, useCallback } from 'react'
import { CodeExecutionResponse, CodeValidationResponse } from '../types/api'
import { extractErrorMessage } from '../utils/apiErrorHandler'
import { api } from '../services/apiClient'

interface ExecutionResult {
  output: string
  error?: string
  executionTime: number
}

interface UseCodeExecutionReturn {
  isExecuting: boolean
  error: string | null
  output: string | null
  executeCode: (code: string, timeout?: number) => Promise<ExecutionResult>
  clearOutput: () => void
}

export function useCodeExecution(): UseCodeExecutionReturn {
  const [isExecuting, setIsExecuting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [output, setOutput] = useState<string | null>(null)

  const executeCode = useCallback(
    async (code: string, timeout: number = 10): Promise<ExecutionResult> => {
      setIsExecuting(true)
      setError(null)
      setOutput(null)

      try {
        const result = await api.code.execute({
          code,
          language: 'python',
          timeout
        })

        if (result.error) {
          setError(result.error)
          return {
            output: result.output || '',
            error: result.error,
            executionTime: result.execution_time
          }
        }

        setOutput(result.output)
        return {
          output: result.output,
          executionTime: result.execution_time
        }
      } catch (err) {
        const errorMessage = extractErrorMessage(err)
        setError(errorMessage)
        return {
          output: '',
          error: errorMessage,
          executionTime: 0
        }
      } finally {
        setIsExecuting(false)
      }
    },
    []
  )

  const clearOutput = useCallback(() => {
    setOutput(null)
    setError(null)
  }, [])

  return {
    isExecuting,
    error,
    output,
    executeCode,
    clearOutput
  }
}

/**
 * Hook для валидации синтаксиса кода
 */
export function useCodeValidation() {
  const [isValidating, setIsValidating] = useState(false)

  const validateCode = useCallback(
    async (code: string): Promise<CodeValidationResponse> => {
      setIsValidating(true)

      try {
        return await api.code.validate({
          code,
          language: 'python'
        })
      } catch (err) {
        return {
          valid: false,
          error: extractErrorMessage(err)
        }
      } finally {
        setIsValidating(false)
      }
    },
    []
  )

  return {
    isValidating,
    validateCode
  }
}
