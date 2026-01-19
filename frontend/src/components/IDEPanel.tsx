/**
 * Компонент IDEPanel - полноценная IDE для редактирования и выполнения кода
 * Поддерживает несколько файлов, выполнение кода и просмотр результатов
 */
import { useState, useEffect } from 'react'
import { Plus, X, FolderOpen, Database, RefreshCw, Loader2, CheckCircle2, XCircle, Play, Copy, Download, RotateCcw } from 'lucide-react'
import { CodeEditor } from './CodeEditor'

interface CodeFile {
  id: string
  name: string
  language: string
  content: string
  isNew?: boolean
}

interface IDEPanelProps {
  initialCode?: string
  onCodeChange?: (code: string) => void
  onExecute?: (code: string) => Promise<{ output: string; error?: string }>
  isExecuting?: boolean
  projectPath?: string
  fileExtensions?: string
  onProjectPathChange?: (path: string) => void
  onFileExtensionsChange?: (ext: string) => void
}

export function IDEPanel({
  initialCode = '',
  onCodeChange,
  onExecute,
  isExecuting = false,
  projectPath = '',
  fileExtensions = '.py',
  onProjectPathChange,
  onFileExtensionsChange
}: IDEPanelProps) {
  const [files, setFiles] = useState<CodeFile[]>([
    {
      id: '1',
      name: 'main.py',
      language: 'python',
      content: initialCode
    }
  ])
  const [activeFileId, setActiveFileId] = useState('1')
  const [showNewFileDialog, setShowNewFileDialog] = useState(false)
  const [newFileName, setNewFileName] = useState('script.py')
  
  // Состояние меню проекта
  const [showProjectMenu, setShowProjectMenu] = useState(false)
  const [showProjectModal, setShowProjectModal] = useState(false)
  const [tempPath, setTempPath] = useState(projectPath)
  const [tempExtensions, setTempExtensions] = useState(fileExtensions)
  const [isIndexing, setIsIndexing] = useState(false)
  const [indexStatus, setIndexStatus] = useState<'idle' | 'success' | 'error'>('idle')
  const [indexedFiles, setIndexedFiles] = useState(0)

  // Синхронизация с props
  useEffect(() => {
    setTempPath(projectPath)
  }, [projectPath])

  useEffect(() => {
    setTempExtensions(fileExtensions)
  }, [fileExtensions])

  // Загрузка из localStorage
  useEffect(() => {
    const savedPath = localStorage.getItem('projectPath')
    const savedExt = localStorage.getItem('fileExtensions')
    if (savedPath && !projectPath && onProjectPathChange) {
      onProjectPathChange(savedPath)
      setTempPath(savedPath)
    }
    if (savedExt && !fileExtensions && onFileExtensionsChange) {
      onFileExtensionsChange(savedExt)
      setTempExtensions(savedExt)
    }
  }, [])

  // Индексация проекта
  const handleIndex = async () => {
    if (!projectPath.trim()) {
      setShowProjectModal(true)
      setShowProjectMenu(false)
      return
    }

    setIsIndexing(true)
    setIndexStatus('idle')
    setShowProjectMenu(false)

    try {
      const response = await fetch('/api/index', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_path: projectPath,
          file_extensions: fileExtensions.split(',').map(e => e.trim())
        })
      })

      if (response.ok) {
        const data = await response.json()
        setIndexedFiles(data.indexed_files || 0)
        setIndexStatus('success')
      } else {
        setIndexStatus('error')
      }
    } catch (error) {
      console.error('Ошибка индексации:', error)
      setIndexStatus('error')
    } finally {
      setIsIndexing(false)
      setTimeout(() => setIndexStatus('idle'), 3000)
    }
  }

  // Сохранение настроек проекта
  const handleSaveProject = () => {
    onProjectPathChange?.(tempPath)
    onFileExtensionsChange?.(tempExtensions)
    setShowProjectModal(false)
    localStorage.setItem('projectPath', tempPath)
    localStorage.setItem('fileExtensions', tempExtensions)
  }

  const activeFile = files.find(f => f.id === activeFileId)

  // Копировать код
  const handleCopy = async () => {
    if (activeFile) {
      await navigator.clipboard.writeText(activeFile.content)
    }
  }

  // Скачать файл
  const handleDownload = () => {
    if (!activeFile) return
    const blob = new Blob([activeFile.content], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = activeFile.name
    a.click()
    URL.revokeObjectURL(url)
  }

  // Сбросить код
  const handleReset = () => {
    setFiles(files.map(f =>
      f.id === activeFileId ? { ...f, content: initialCode } : f
    ))
    onCodeChange?.(initialCode)
  }

  const handleAddFile = () => {
    const newFile: CodeFile = {
      id: Date.now().toString(),
      name: newFileName,
      language: newFileName.endsWith('.py') ? 'python' : 'javascript',
      content: '',
      isNew: true
    }
    setFiles([...files, newFile])
    setActiveFileId(newFile.id)
    setShowNewFileDialog(false)
    setNewFileName('script.py')
  }

  const handleDeleteFile = (id: string) => {
    if (files.length === 1) {
      alert('Нельзя удалить последний файл')
      return
    }
    const newFiles = files.filter(f => f.id !== id)
    setFiles(newFiles)
    if (activeFileId === id) {
      setActiveFileId(newFiles[0].id)
    }
  }

  const handleCodeChange = (newCode: string) => {
    setFiles(files.map(f =>
      f.id === activeFileId ? { ...f, content: newCode, isNew: false } : f
    ))
    onCodeChange?.(newCode)
  }

  const handleExecute = async (code: string) => {
    if (!onExecute) return
    try {
      const result = await onExecute(code)
      return result
    } catch (err) {
      throw err
    }
  }

  return (
    <div className="flex flex-col h-full bg-[#0a0a0f] rounded-lg overflow-hidden border border-white/5">
      {/* Compact Header: Project + Tabs */}
      <div className="flex items-center gap-0.5 px-1 py-0.5 bg-[#0d0d12] border-b border-white/5">
        {/* Project Menu Button */}
        <div className="relative flex-shrink-0">
          <button
            onClick={() => setShowProjectMenu(!showProjectMenu)}
            className={`flex items-center gap-1 p-1.5 rounded transition-colors ${
              showProjectMenu ? 'bg-white/10 text-white' : 'text-gray-500 hover:text-gray-300 hover:bg-white/5'
            }`}
            title={projectPath || 'Открыть проект'}
          >
            <FolderOpen className="w-3.5 h-3.5" />
            {isIndexing && <Loader2 className="w-3 h-3 animate-spin text-blue-400" />}
            {indexStatus === 'success' && <CheckCircle2 className="w-3 h-3 text-green-400" />}
            {indexStatus === 'error' && <XCircle className="w-3 h-3 text-red-400" />}
          </button>

          {/* Dropdown */}
          {showProjectMenu && (
            <div 
              className="absolute top-full left-0 mt-1 w-56 bg-[#1a1a24] border border-white/10 rounded-lg shadow-2xl overflow-hidden z-50"
              onMouseLeave={() => setShowProjectMenu(false)}
            >
              {projectPath && (
                <div className="px-3 py-2 border-b border-white/5">
                  <div className="text-[10px] text-gray-500 uppercase tracking-wide">Проект</div>
                  <div className="text-xs text-gray-300 truncate mt-0.5" title={projectPath}>{projectPath}</div>
                </div>
              )}

              <div className="py-0.5">
                <button
                  onClick={() => { setShowProjectModal(true); setShowProjectMenu(false) }}
                  className="w-full flex items-center gap-2 px-3 py-2 text-xs text-gray-300 hover:bg-white/5 hover:text-white transition-colors"
                >
                  <FolderOpen className="w-3.5 h-3.5 text-blue-400" />
                  Открыть папку...
                </button>

                <button
                  onClick={handleIndex}
                  disabled={isIndexing}
                  className="w-full flex items-center gap-2 px-3 py-2 text-xs text-gray-300 hover:bg-white/5 hover:text-white transition-colors disabled:opacity-50"
                >
                  <Database className="w-3.5 h-3.5 text-emerald-400" />
                  Индексировать
                  {isIndexing && <Loader2 className="w-3 h-3 animate-spin ml-auto" />}
                </button>

                <button
                  onClick={handleIndex}
                  disabled={isIndexing || !projectPath}
                  className="w-full flex items-center gap-2 px-3 py-2 text-xs text-gray-300 hover:bg-white/5 hover:text-white transition-colors disabled:opacity-50"
                >
                  <RefreshCw className={`w-3.5 h-3.5 text-amber-400 ${isIndexing ? 'animate-spin' : ''}`} />
                  Переиндексировать
                </button>
              </div>

              {fileExtensions && (
                <div className="px-3 py-2 border-t border-white/5">
                  <div className="flex flex-wrap gap-1">
                    {fileExtensions.split(',').map((ext, i) => (
                      <span key={i} className="px-1 py-0.5 text-[10px] bg-white/5 text-gray-500 rounded">
                        {ext.trim()}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* File Tabs */}
        <div className="flex-1 flex items-center gap-0.5 overflow-x-auto min-w-0 scrollbar-none">
          {files.map(file => (
            <div
              key={file.id}
              className={`group flex items-center gap-1 px-2 py-1 rounded text-[11px] cursor-pointer transition-colors flex-shrink-0 ${
                activeFileId === file.id
                  ? 'bg-white/10 text-gray-200'
                  : 'text-gray-500 hover:text-gray-300 hover:bg-white/5'
              }`}
              onClick={() => setActiveFileId(file.id)}
            >
              <span className="text-[10px] opacity-60">{file.language === 'python' ? '🐍' : '📜'}</span>
              <span>{file.name}</span>
              {file.isNew && <span className="w-1.5 h-1.5 bg-amber-400 rounded-full" />}
              {files.length > 1 && (
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    handleDeleteFile(file.id)
                  }}
                  className={`p-0.5 rounded transition-colors ${
                    activeFileId === file.id 
                      ? 'text-gray-500 hover:text-red-400 opacity-100' 
                      : 'opacity-0 group-hover:opacity-100 text-gray-600 hover:text-red-400'
                  }`}
                >
                  <X className="w-2.5 h-2.5" />
                </button>
              )}
            </div>
          ))}

          <button
            onClick={() => setShowNewFileDialog(true)}
            className="p-1 text-gray-600 hover:text-gray-400 hover:bg-white/5 rounded transition-colors flex-shrink-0"
            title="Новый файл"
          >
            <Plus className="w-3 h-3" />
          </button>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-0.5 flex-shrink-0 border-l border-white/5 pl-1 ml-1">
          {onExecute && (
            <button
              onClick={() => activeFile && handleExecute(activeFile.content)}
              disabled={isExecuting}
              className="flex items-center gap-1 px-2 py-1 text-[11px] text-emerald-400 hover:bg-emerald-500/10 rounded transition-colors disabled:opacity-50"
              title="Выполнить"
            >
              <Play className="w-3 h-3" />
              <span className="hidden lg:inline">Выполнить</span>
            </button>
          )}
          <button
            onClick={handleCopy}
            className="p-1 text-gray-500 hover:text-gray-300 hover:bg-white/5 rounded transition-colors"
            title="Копировать"
          >
            <Copy className="w-3 h-3" />
          </button>
          <button
            onClick={handleDownload}
            className="p-1 text-gray-500 hover:text-gray-300 hover:bg-white/5 rounded transition-colors"
            title="Скачать"
          >
            <Download className="w-3 h-3" />
          </button>
          <button
            onClick={handleReset}
            className="p-1 text-gray-500 hover:text-gray-300 hover:bg-white/5 rounded transition-colors"
            title="Сбросить"
          >
            <RotateCcw className="w-3 h-3" />
          </button>
        </div>
      </div>

      {/* Editor */}
      {activeFile && (
        <div className="flex-1 overflow-hidden">
          <CodeEditor
            key={activeFile.id}
            initialCode={activeFile.content}
            language={activeFile.language}
            onCodeChange={handleCodeChange}
            onExecute={handleExecute}
            isExecuting={isExecuting}
          />
        </div>
      )}

      {/* New File Dialog */}
      {showNewFileDialog && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-[#1a1a1f] border border-white/10 rounded-lg p-6 w-96">
            <h3 className="text-lg font-semibold text-white mb-4">Новый файл</h3>
            <input
              type="text"
              value={newFileName}
              onChange={(e) => setNewFileName(e.target.value)}
              placeholder="Название файла"
              className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded text-white placeholder-gray-500 focus:outline-none focus:border-blue-500/50 mb-4"
              autoFocus
            />
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => setShowNewFileDialog(false)}
                className="px-4 py-2 text-sm text-gray-400 hover:bg-white/10 rounded transition-colors"
              >
                Отмена
              </button>
              <button
                onClick={handleAddFile}
                className="px-4 py-2 text-sm bg-blue-600 text-white hover:bg-blue-700 rounded transition-colors"
              >
                Создать
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Project Settings Modal */}
      {showProjectModal && (
        <div 
          className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50"
          onClick={() => setShowProjectModal(false)}
        >
          <div 
            className="bg-[#16161e] border border-white/10 rounded-xl shadow-2xl w-full max-w-md mx-4 overflow-hidden"
            onClick={e => e.stopPropagation()}
          >
            <div className="px-5 py-4 border-b border-white/5">
              <h3 className="text-base font-semibold text-gray-100 flex items-center gap-2">
                <FolderOpen className="w-5 h-5 text-blue-400" />
                Открыть проект
              </h3>
            </div>

            <div className="p-5 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Путь к папке проекта
                </label>
                <input
                  type="text"
                  value={tempPath}
                  onChange={e => setTempPath(e.target.value)}
                  placeholder="/Users/you/projects/my-app"
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2.5 text-white placeholder-gray-500 focus:outline-none focus:border-blue-500/50"
                />
                <p className="text-xs text-gray-500 mt-1.5">
                  Абсолютный путь к корню проекта
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Расширения файлов
                </label>
                <input
                  type="text"
                  value={tempExtensions}
                  onChange={e => setTempExtensions(e.target.value)}
                  placeholder=".py,.js,.ts"
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2.5 text-white placeholder-gray-500 focus:outline-none focus:border-blue-500/50"
                />
                <p className="text-xs text-gray-500 mt-1.5">
                  Через запятую: .py,.js,.ts
                </p>
              </div>
            </div>

            <div className="px-5 py-4 bg-white/[0.02] border-t border-white/5 flex gap-3 justify-end">
              <button
                onClick={() => setShowProjectModal(false)}
                className="px-4 py-2 text-sm font-medium text-gray-300 hover:text-white bg-white/5 hover:bg-white/10 rounded-lg transition-colors"
              >
                Отмена
              </button>
              <button
                onClick={handleSaveProject}
                disabled={!tempPath.trim()}
                className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-500 rounded-lg transition-colors disabled:opacity-50 flex items-center gap-2"
              >
                <FolderOpen className="w-4 h-4" />
                Открыть
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
