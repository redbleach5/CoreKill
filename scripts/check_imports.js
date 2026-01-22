#!/usr/bin/env node
/**
 * Скрипт для проверки импортов в frontend компонентах.
 * 
 * Проверяет:
 * - Использование api без импорта
 * - Использование useLocalStorage без импорта
 * - Использование useModels без импорта
 * - Использование useApi без импорта
 * 
 * Запуск: node scripts/check_imports.js
 */

const fs = require('fs');
const path = require('path');

const FRONTEND_DIR = path.join(__dirname, '..', 'frontend', 'src');
const COMPONENTS_DIR = path.join(FRONTEND_DIR, 'components');
const HOOKS_DIR = path.join(FRONTEND_DIR, 'hooks');
const UTILS_DIR = path.join(FRONTEND_DIR, 'utils');

const ISSUES = [];

// Паттерны для поиска использования без импорта
const PATTERNS = [
  { name: 'api', pattern: /\bapi\.(models|conversations|projects|metrics|code|settings|tasks|databases|stream)\s*\(/g, importPattern: /import\s+.*\bapi\b.*from\s+['"]\.\.\/services\/apiClient['"]/ },
  { name: 'useLocalStorage', pattern: /\buseLocalStorage\s*\(/g, importPattern: /import\s+.*\buseLocalStorage\b.*from\s+['"]\.\.\/hooks\/useLocalStorage['"]/ },
  { name: 'useLocalStorageString', pattern: /\buseLocalStorageString\s*\(/g, importPattern: /import\s+.*\buseLocalStorageString\b.*from\s+['"]\.\.\/hooks\/useLocalStorage['"]/ },
  { name: 'useModels', pattern: /\buseModels\s*\(/g, importPattern: /import\s+.*\buseModels\b.*from\s+['"]\.\.\/hooks\/useModels['"]/ },
  { name: 'useApi', pattern: /\buseApi\s*\(/g, importPattern: /import\s+.*\buseApi\b.*from\s+['"]\.\.\/hooks\/useApi['"]/ },
];

function checkFile(filePath) {
  const content = fs.readFileSync(filePath, 'utf-8');
  const relativePath = path.relative(FRONTEND_DIR, filePath);
  
  // Пропускаем файлы, которые определяют эти функции
  if (filePath.includes('apiClient.ts') || 
      filePath.includes('useLocalStorage.ts') || 
      filePath.includes('useModels.ts') || 
      filePath.includes('useApi.ts')) {
    return;
  }
  
  PATTERNS.forEach(({ name, pattern, importPattern }) => {
    const matches = content.match(pattern);
    if (matches && matches.length > 0) {
      // Проверяем наличие импорта
      if (!importPattern.test(content)) {
        ISSUES.push({
          file: relativePath,
          issue: `Используется ${name} без импорта`,
          line: content.split('\n').findIndex(line => pattern.test(line)) + 1
        });
      }
    }
  });
}

function walkDir(dir, callback) {
  const files = fs.readdirSync(dir);
  
  files.forEach(file => {
    const filePath = path.join(dir, file);
    const stat = fs.statSync(filePath);
    
    if (stat.isDirectory()) {
      walkDir(filePath, callback);
    } else if (file.endsWith('.ts') || file.endsWith('.tsx')) {
      callback(filePath);
    }
  });
}

// Проверяем компоненты
walkDir(COMPONENTS_DIR, checkFile);

// Проверяем хуки
walkDir(HOOKS_DIR, checkFile);

// Проверяем утилиты
walkDir(UTILS_DIR, checkFile);

// Проверяем App.tsx
const appPath = path.join(FRONTEND_DIR, 'App.tsx');
if (fs.existsSync(appPath)) {
  checkFile(appPath);
}

// Выводим результаты
if (ISSUES.length === 0) {
  console.log('✅ Все импорты корректны!');
  process.exit(0);
} else {
  console.error('❌ Найдены проблемы с импортами:\n');
  ISSUES.forEach(({ file, issue, line }) => {
    console.error(`  ${file}:${line} - ${issue}`);
  });
  process.exit(1);
}
