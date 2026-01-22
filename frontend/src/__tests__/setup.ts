import { expect, afterEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import { setupTestMocks, cleanupTestMocks } from './utils/mocks'

// Настраиваем моки для всех тестов
setupTestMocks()

// runs a cleanup after each test case
afterEach(() => {
  cleanup()
  cleanupTestMocks()
})
