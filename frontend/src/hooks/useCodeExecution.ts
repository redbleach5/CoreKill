/**
 * Hook для выполнения кода через backend API
 */
import { useState, useCallback } from 'react'

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
        const response = await fetch('/api/code/execute', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            code,
            language: 'python',
            timeout
          })
        })

        if (!response.ok) {
          const errorData = await response.json()
          throw new Error(errorData.detail || 'Ошибка при выполнении кода')
        }

        const result = await response.json()

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
        const errorMessage = err instanceof Error ? err.message : 'Неизвестная ошибка'
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
interface ValidationResult {
  valid: boolean
  error?: string
  line?: number
  offset?: number
}

export function useCodeValidation() {
  const [isValidating, setIsValidating] = useState(false)

  const validateCode = useCallback(
    async (code: string): Promise<ValidationResult> => {
      setIsValidating(true)

      try {
        const response = await fetch('/api/code/validate', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            code,
            language: 'python'
          })
        })

        if (!response.ok) {
          throw new Error('Ошибка при валидации кода')
        }

        return await response.json()
      } catch (err) {
        return {
          valid: false,
          error: err instanceof Error ? err.message : 'Неизвестная ошибка'
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
