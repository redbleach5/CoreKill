/**
 * Базовые тесты для компонентов.
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { LoadingState } from '../components/ui/LoadingState'
import { ErrorState } from '../components/ui/ErrorState'
import { EmptyState } from '../components/ui/EmptyState'

describe('UI Components', () => {
  describe('LoadingState', () => {
    it('should render with default message', () => {
      render(<LoadingState />)
      expect(screen.getByText('Загрузка...')).toBeInTheDocument()
    })

    it('should render with custom message', () => {
      render(<LoadingState message="Загрузка данных..." />)
      expect(screen.getByText('Загрузка данных...')).toBeInTheDocument()
    })
  })

  describe('ErrorState', () => {
    it('should render with default title', () => {
      render(<ErrorState />)
      expect(screen.getByText('Произошла ошибка')).toBeInTheDocument()
    })

    it('should render with custom title and message', () => {
      render(
        <ErrorState
          title="Ошибка загрузки"
          message="Не удалось загрузить данные"
        />
      )
      expect(screen.getByText('Ошибка загрузки')).toBeInTheDocument()
      expect(screen.getByText('Не удалось загрузить данные')).toBeInTheDocument()
    })

    it('should render retry button when onRetry provided', () => {
      const onRetry = vi.fn()
      render(<ErrorState onRetry={onRetry} />)
      
      const button = screen.getByText('Повторить')
      expect(button).toBeInTheDocument()
    })

    it('should not render retry button when onRetry not provided', () => {
      render(<ErrorState />)
      expect(screen.queryByText('Повторить')).not.toBeInTheDocument()
    })
  })

  describe('EmptyState', () => {
    it('should render with default message', () => {
      render(<EmptyState />)
      expect(screen.getByText('Нет данных')).toBeInTheDocument()
    })

    it('should render with custom message', () => {
      render(<EmptyState message="Список пуст" />)
      expect(screen.getByText('Список пуст')).toBeInTheDocument()
    })
  })
})
