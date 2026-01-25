/**
 * Тесты для проверки импортов в frontend компонентах.
 * 
 * Проверяет, что все используемые функции/хуки имеют соответствующие импорты.
 */
import { describe, it } from 'vitest'
import { readFileSync, existsSync, readdirSync, statSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

// Получаем __dirname для ES modules
const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const FRONTEND_SRC = join(__dirname, '..')
const COMPONENTS_DIR = join(FRONTEND_SRC, 'components')
const HOOKS_DIR = join(FRONTEND_SRC, 'hooks')
const UTILS_DIR = join(FRONTEND_SRC, 'utils')

// Паттерны для проверки
const PATTERNS = [
  {
    name: 'api',
    usage: /\bapi\.(models|conversations|projects|metrics|code|settings|tasks|databases|stream)\s*\(/,
    importPattern: /import\s+.*\bapi\b.*from\s+['"][\.\/]*services\/apiClient['"]/,
  },
  {
    name: 'useLocalStorage',
    usage: /\buseLocalStorage\s*\(/,
    importPattern: /import\s+.*\buseLocalStorage\b.*from\s+['"][\.\/]*hooks\/useLocalStorage['"]/,
  },
  {
    name: 'useLocalStorageString',
    usage: /\buseLocalStorageString\s*\(/,
    importPattern: /import\s+.*\buseLocalStorageString\b.*from\s+['"][\.\/]*hooks\/useLocalStorage['"]/,
  },
  {
    name: 'useModels',
    usage: /\buseModels\s*\(/,
    importPattern: /import\s+.*\buseModels\b.*from\s+['"][\.\/]*hooks\/useModels['"]/,
  },
  {
    name: 'useApi',
    usage: /\buseApi\s*\(/,
    importPattern: /import\s+.*\buseApi\b.*from\s+['"][\.\/]*hooks\/useApi['"]/,
  },
]

// Файлы, которые определяют эти функции (пропускаем)
const SKIP_FILES = [
  'apiClient.ts',
  'useLocalStorage.ts',
  'useModels.ts',
  'useApi.ts',
]

function getAllTsFiles(dir: string): string[] {
  const files: string[] = []
  
  function walkDir(currentDir: string) {
    try {
      const entries = readdirSync(currentDir)
      
      for (const entry of entries) {
        const fullPath = join(currentDir, entry)
        const stat = statSync(fullPath)
        
        if (stat.isDirectory()) {
          walkDir(fullPath)
        } else if (entry.endsWith('.ts') || entry.endsWith('.tsx')) {
          files.push(fullPath)
        }
      }
    } catch {
      // Игнорируем ошибки доступа
    }
  }
  
  if (existsSync(dir)) {
    walkDir(dir)
  }
  
  return files
}

function checkFile(filePath: string): Array<{ pattern: string; line: number }> {
  const content = readFileSync(filePath, 'utf-8')
  const fileName = filePath.split('/').pop() || ''
  
  // Пропускаем файлы, которые определяют эти функции
  if (SKIP_FILES.some(skip => fileName.includes(skip))) {
    return []
  }
  
  const issues: Array<{ pattern: string; line: number }> = []
  const lines = content.split('\n')
  
  PATTERNS.forEach(({ name, usage, importPattern }) => {
    // Проверяем использование
    const hasUsage = usage.test(content)
    
    if (hasUsage) {
      // Проверяем наличие импорта
      const hasImport = importPattern.test(content)
      
      if (!hasImport) {
        // Находим строку с использованием
        const lineIndex = lines.findIndex((line: string) => usage.test(line))
        if (lineIndex !== -1) {
          issues.push({ pattern: name, line: lineIndex + 1 })
        }
      }
    }
  })
  
  return issues
}

describe('Frontend Imports', () => {
  const componentFiles = getAllTsFiles(COMPONENTS_DIR)
  const hookFiles = getAllTsFiles(HOOKS_DIR)
  const utilFiles = getAllTsFiles(UTILS_DIR)
  const appFile = join(FRONTEND_SRC, 'App.tsx')
  
  const allFiles = [
    ...componentFiles,
    ...hookFiles,
    ...utilFiles,
    ...(existsSync(appFile) ? [appFile] : []),
  ]
  
  allFiles.forEach(filePath => {
    const relativePath = filePath.replace(FRONTEND_SRC + '/', '')
    
    it(`should have correct imports in ${relativePath}`, () => {
      const issues = checkFile(filePath)
      
      if (issues.length > 0) {
        const errorMessages = issues.map(
          ({ pattern, line }) => `  - ${pattern} используется без импорта (строка ${line})`
        )
        throw new Error(
          `Проблемы с импортами в ${relativePath}:\n${errorMessages.join('\n')}`
        )
      }
    })
  })
})
