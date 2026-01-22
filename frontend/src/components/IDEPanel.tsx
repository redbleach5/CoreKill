/**
 * Компонент IDEPanel - полноценная IDE для редактирования и выполнения кода
 * С боковой панелью файлов как в настоящих IDE (VS Code, PyCharm)
 */
import { useState, useEffect, useCallback, useRef } from 'react'
import { 
  Plus, X, FolderOpen, Database, RefreshCw, Loader2, CheckCircle2,
  Play, Copy, Download, RotateCcw, FileCode, FileText, ChevronRight, ChevronDown, 
  File, Folder, PanelLeftClose, PanelLeft
} from 'lucide-react'
import { CodeEditor } from './CodeEditor'
import { IndexProjectResponse, ProjectFilesResponse, FileContentResponse, BrowseFolderResponse } from '../types/api'
import { extractErrorMessage } from '../utils/apiErrorHandler'
import { api } from '../services/apiClient'
import { useLocalStorage, useLocalStorageString } from '../hooks/useLocalStorage'

// ============================================================================
// Types
// ============================================================================

interface CodeFile {
  id: string
  name: string
  path?: string
  language: string
  content: string
  isNew?: boolean
  isModified?: boolean
}

interface FileTreeNode {
  name: string
  path: string
  type: 'file' | 'directory'
  extension?: string
  size?: number
  children?: FileTreeNode[]
  truncated?: boolean
  error?: string
}

interface ProjectFilesResponse {
  tree: FileTreeNode
  stats: {
    total_files: number
    total_directories: number
    root_path: string
  }
  error?: string
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

// ============================================================================
// File Tree Item Component
// ============================================================================

interface FileTreeItemProps {
  node: FileTreeNode
  depth?: number
  expandedDirs: Set<string>
  onToggleDir: (path: string) => void
  onFileClick: (node: FileTreeNode) => void
  selectedFile?: string
}

function FileTreeItem({ 
  node, 
  depth = 0, 
  expandedDirs, 
  onToggleDir, 
  onFileClick,
  selectedFile 
}: FileTreeItemProps) {
  const isExpanded = expandedDirs.has(node.path)
  const isSelected = selectedFile === node.path
  const paddingLeft = depth * 12 + 8
  
  // Иконка по расширению
  const getFileIcon = (ext: string) => {
    const cls = "w-4 h-4 flex-shrink-0"
    switch (ext) {
      case '.py': return <FileCode className={`${cls} text-yellow-400`} />
      case '.js': case '.jsx': return <FileCode className={`${cls} text-yellow-300`} />
      case '.ts': case '.tsx': return <FileCode className={`${cls} text-blue-400`} />
      case '.json': return <FileCode className={`${cls} text-amber-500`} />
      case '.md': return <FileText className={`${cls} text-gray-400`} />
      case '.html': return <FileCode className={`${cls} text-orange-400`} />
      case '.css': case '.scss': return <FileCode className={`${cls} text-pink-400`} />
      case '.sql': return <FileCode className={`${cls} text-blue-300`} />
      case '.yml': case '.yaml': return <FileCode className={`${cls} text-red-400`} />
      case '.toml': return <FileCode className={`${cls} text-orange-300`} />
      default: return <File className={`${cls} text-gray-500`} />
    }
  }
  
  if (node.type === 'directory') {
    const hasChildren = node.children && node.children.length > 0
    
    return (
      <div>
        <div
          className="flex items-center gap-1 py-0.5 px-1 hover:bg-white/5 cursor-pointer text-[13px] text-gray-300 hover:text-white transition-colors group"
          style={{ paddingLeft }}
          onClick={() => onToggleDir(node.path)}
        >
          <span className="w-4 h-4 flex items-center justify-center flex-shrink-0">
            {hasChildren ? (
              isExpanded ? (
                <ChevronDown className="w-3.5 h-3.5 text-gray-500" />
              ) : (
                <ChevronRight className="w-3.5 h-3.5 text-gray-500" />
              )
            ) : null}
          </span>
          <Folder className={`w-4 h-4 flex-shrink-0 ${isExpanded ? 'text-blue-400' : 'text-amber-500/80'}`} />
          <span className="truncate flex-1">{node.name}</span>
        </div>
        {isExpanded && hasChildren && (
          <div>
            {node.children!.map((child, idx) => (
              <FileTreeItem 
                key={child.path || idx} 
                node={child} 
                depth={depth + 1}
                expandedDirs={expandedDirs}
                onToggleDir={onToggleDir}
                onFileClick={onFileClick}
                selectedFile={selectedFile}
              />
            ))}
          </div>
        )}
        {node.truncated && isExpanded && (
          <div 
            className="text-[11px] text-gray-600 italic py-0.5 px-1"
            style={{ paddingLeft: paddingLeft + 20 }}
          >
            ・・・
          </div>
        )}
      </div>
    )
  }
  
  // Файл
  return (
    <div
      className={`flex items-center gap-1 py-0.5 px-1 cursor-pointer text-[13px] transition-colors ${
        isSelected 
          ? 'bg-blue-500/20 text-white' 
          : 'text-gray-400 hover:bg-white/5 hover:text-gray-200'
      }`}
      style={{ paddingLeft: paddingLeft + 16 }}
      onClick={() => onFileClick(node)}
      title={node.path}
    >
      {getFileIcon(node.extension || '')}
      <span className="truncate flex-1">{node.name}</span>
      {node.size !== undefined && node.size > 0 && (
        <span className="text-[10px] text-gray-600 flex-shrink-0">
          {node.size < 1024 
            ? `${node.size}B` 
            : node.size < 1024 * 1024 
              ? `${Math.round(node.size / 1024)}K`
              : `${(node.size / 1024 / 1024).toFixed(1)}M`
          }
        </span>
      )}
    </div>
  )
}

// ============================================================================
// Main Component
// ============================================================================

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
  // Editor files state
  const [files, setFiles] = useState<CodeFile[]>([
    { id: '1', name: 'main.py', language: 'python', content: initialCode }
  ])
  const [activeFileId, setActiveFileId] = useState('1')
  
  // UI state
  const [showNewFileDialog, setShowNewFileDialog] = useState(false)
  const [newFileName, setNewFileName] = useState('script.py')
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [sidebarWidth, setSidebarWidth] = useState(240)
  const [isResizing, setIsResizing] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  
  // Resize constraints
  const MIN_SIDEBAR_WIDTH = 150
  const MAX_SIDEBAR_WIDTH = 500
  
  // Project state
  const [showProjectModal, setShowProjectModal] = useState(false)
  const [tempPath, setTempPath] = useState(projectPath)
  const [tempExtensions, setTempExtensions] = useState(fileExtensions)
  const [isIndexing, setIsIndexing] = useState(false)
  const [indexStatus, setIndexStatus] = useState<'idle' | 'success' | 'error'>('idle')
  const [isBrowsing, setIsBrowsing] = useState(false)
  
  // File tree state
  const [fileTree, setFileTree] = useState<FileTreeNode | null>(null)
  const [isLoadingTree, setIsLoadingTree] = useState(false)
  const [expandedDirs, setExpandedDirs] = useState<Set<string>>(new Set())
  const [fileTreeStats, setFileTreeStats] = useState<{ total_files: number; total_directories: number } | null>(null)
  const [selectedFilePath, setSelectedFilePath] = useState<string | undefined>()
  const [isLoadingFile, setIsLoadingFile] = useState(false)

  // ============================================================================
  // Effects
  // ============================================================================

  // Sync with props
  useEffect(() => { setTempPath(projectPath) }, [projectPath])
  useEffect(() => { setTempExtensions(fileExtensions) }, [fileExtensions])

  // Load from localStorage using hooks
  const [savedProjectPath, setSavedProjectPath] = useLocalStorageString('projectPath', '')
  const [savedFileExtensions, setSavedFileExtensions] = useLocalStorageString('fileExtensions', '')
  const [savedSidebarOpen, setSavedSidebarOpen] = useLocalStorage<boolean>('ideSidebarOpen', true)
  const [savedSidebarWidth, setSavedSidebarWidth] = useLocalStorage<number>('ideSidebarWidth', DEFAULT_SIDEBAR_WIDTH)
  
  // Sync with props and localStorage
  useEffect(() => {
    if (savedProjectPath && !projectPath && onProjectPathChange) {
      onProjectPathChange(savedProjectPath)
      setTempPath(savedProjectPath)
    }
    if (savedFileExtensions && !fileExtensions && onFileExtensionsChange) {
      onFileExtensionsChange(savedFileExtensions)
      setTempExtensions(savedFileExtensions)
    }
    setSidebarOpen(savedSidebarOpen)
    if (savedSidebarWidth >= MIN_SIDEBAR_WIDTH && savedSidebarWidth <= MAX_SIDEBAR_WIDTH) {
      setSidebarWidth(savedSidebarWidth)
    }
  }, [savedProjectPath, savedFileExtensions, savedSidebarOpen, savedSidebarWidth, projectPath, fileExtensions, onProjectPathChange, onFileExtensionsChange])
  
  // Save to localStorage when changed
  useEffect(() => {
    if (projectPath) {
      setSavedProjectPath(projectPath)
    }
  }, [projectPath, setSavedProjectPath])
  
  useEffect(() => {
    if (fileExtensions) {
      setSavedFileExtensions(fileExtensions)
    }
  }, [fileExtensions, setSavedFileExtensions])
  
  useEffect(() => {
    setSavedSidebarOpen(sidebarOpen)
  }, [sidebarOpen, setSavedSidebarOpen])
  
  useEffect(() => {
    setSavedSidebarWidth(sidebarWidth)
  }, [sidebarWidth, setSavedSidebarWidth])

  // Resize handlers
  const handleResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    setIsResizing(true)
  }, [])

  const handleResizeMove = useCallback((e: MouseEvent) => {
    if (!isResizing || !containerRef.current) return
    
    const containerRect = containerRef.current.getBoundingClientRect()
    const newWidth = e.clientX - containerRect.left
    
    // Clamp to min/max
    const clampedWidth = Math.min(MAX_SIDEBAR_WIDTH, Math.max(MIN_SIDEBAR_WIDTH, newWidth))
    setSidebarWidth(clampedWidth)
  }, [isResizing])

  const handleResizeEnd = useCallback(() => {
    if (isResizing) {
      setIsResizing(false)
      // Сохранение происходит автоматически через хук useLocalStorage
    }
  }, [isResizing, sidebarWidth])

  // Attach global mouse events for resize
  useEffect(() => {
    if (isResizing) {
      document.addEventListener('mousemove', handleResizeMove)
      document.addEventListener('mouseup', handleResizeEnd)
      document.body.style.cursor = 'col-resize'
      document.body.style.userSelect = 'none'
    }
    
    return () => {
      document.removeEventListener('mousemove', handleResizeMove)
      document.removeEventListener('mouseup', handleResizeEnd)
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }
  }, [isResizing, handleResizeMove, handleResizeEnd])

  // Load file tree when project path changes
  const loadFileTree = useCallback(async (path: string, extensions?: string) => {
    if (!path.trim()) {
      setFileTree(null)
      setFileTreeStats(null)
      return
    }
    
    setIsLoadingTree(true)
    try {
      const data = await api.projects.getFiles(path, extensions)
      if (data.error) {
        console.error('Ошибка загрузки файлов:', data.error)
        setFileTree(null)
      } else {
        setFileTree(data.tree)
        setFileTreeStats(data.stats)
        // Expand root by default
        setExpandedDirs(new Set([data.tree.path]))
      }
    } catch (error) {
      console.error('Ошибка загрузки дерева файлов:', extractErrorMessage(error))
      setFileTree(null)
    } finally {
      setIsLoadingTree(false)
    }
  }, [])

  useEffect(() => {
    if (projectPath) {
      loadFileTree(projectPath, fileExtensions)
    }
  }, [projectPath, loadFileTree])

  // ============================================================================
  // Handlers
  // ============================================================================

  const toggleDirectory = (path: string) => {
    setExpandedDirs(prev => {
      const next = new Set(prev)
      if (next.has(path)) next.delete(path)
      else next.add(path)
      return next
    })
  }

  const toggleSidebar = () => {
    const newValue = !sidebarOpen
    setSidebarOpen(newValue)
    // Сохранение происходит автоматически через хук useLocalStorage
  }

  const handleFileClick = async (node: FileTreeNode) => {
    if (node.type !== 'file') return
    
    setSelectedFilePath(node.path)
    
    // Check if already open
    const existing = files.find(f => f.path === node.path)
    if (existing) {
      setActiveFileId(existing.id)
      return
    }
    
    // Load file content
    setIsLoadingFile(true)
    try {
      const data = await api.projects.getFileContent(node.path)
      if (data.error) {
        console.error('Ошибка чтения файла:', data.error)
        return
      }
      
      const lang = getLanguageFromExtension(node.extension || '')
      const newFile: CodeFile = {
        id: Date.now().toString(),
        name: node.name,
        path: node.path,
        language: lang,
        content: data.content,
      }
      setFiles(prev => [...prev, newFile])
      setActiveFileId(newFile.id)
    } catch (error) {
      console.error('Ошибка загрузки файла:', extractErrorMessage(error))
    } finally {
      setIsLoadingFile(false)
    }
  }

  const getLanguageFromExtension = (ext: string): string => {
    const map: Record<string, string> = {
      '.py': 'python',
      '.js': 'javascript',
      '.jsx': 'javascript',
      '.ts': 'typescript',
      '.tsx': 'typescript',
      '.json': 'json',
      '.html': 'html',
      '.css': 'css',
      '.scss': 'scss',
      '.md': 'markdown',
      '.sql': 'sql',
      '.yml': 'yaml',
      '.yaml': 'yaml',
      '.toml': 'toml',
    }
    return map[ext] || 'plaintext'
  }

  const handleIndex = async () => {
    if (!projectPath.trim()) {
      setShowProjectModal(true)
      return
    }

    setIsIndexing(true)
    setIndexStatus('idle')

    try {
      const result = await api.projects.index({
        project_path: projectPath,
        file_extensions: fileExtensions.split(',').map(e => e.trim()).filter(e => e)
      })
      
      if (result.status === 'success') {
        setIndexStatus('success')
        // Refresh file tree after indexing
        loadFileTree(projectPath, fileExtensions)
      } else {
        setIndexStatus('error')
      }
    } catch (error) {
      console.error('Ошибка индексации:', extractErrorMessage(error))
      setIndexStatus('error')
    } finally {
      setIsIndexing(false)
      setTimeout(() => setIndexStatus('idle'), 3000)
    }
  }

  const handleSaveProject = () => {
    onProjectPathChange?.(tempPath)
    onFileExtensionsChange?.(tempExtensions)
    setShowProjectModal(false)
    setSavedProjectPath(tempPath)
    setSavedFileExtensions(tempExtensions)
    // Load tree for new project
    loadFileTree(tempPath, tempExtensions)
  }

  const handleBrowseFolder = async () => {
    setIsBrowsing(true)
    try {
      const data = await api.projects.browseFolder(tempPath)
      if (data.path && data.exists) {
        setTempPath(data.path)
        setSavedProjectPath(data.path)
      }
    } catch (error) {
      console.error('Ошибка выбора папки:', extractErrorMessage(error))
    } finally {
      setIsBrowsing(false)
    }
  }

  const activeFile = files.find(f => f.id === activeFileId)

  const handleCopy = async () => {
    if (activeFile) {
      await navigator.clipboard.writeText(activeFile.content)
    }
  }

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

  const handleReset = () => {
    setFiles(files.map(f =>
      f.id === activeFileId ? { ...f, content: initialCode, isModified: false } : f
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
    if (files.length === 1) return
    const newFiles = files.filter(f => f.id !== id)
    setFiles(newFiles)
    if (activeFileId === id) {
      setActiveFileId(newFiles[0].id)
    }
  }

  const handleCodeChange = (newCode: string) => {
    setFiles(files.map(f =>
      f.id === activeFileId ? { ...f, content: newCode, isNew: false, isModified: true } : f
    ))
    onCodeChange?.(newCode)
  }

  const handleExecute = async (code: string) => {
    if (!onExecute) return
    return await onExecute(code)
  }

  // ============================================================================
  // Render
  // ============================================================================

  return (
    <div 
      ref={containerRef}
      className={`flex h-full bg-[#0a0a0f] rounded-lg overflow-hidden border border-white/5 ${isResizing ? 'select-none' : ''}`}
    >
      {/* Sidebar */}
      {sidebarOpen && (
        <div 
          className="flex flex-col bg-[#0d0d12] flex-shrink-0"
          style={{ width: sidebarWidth }}
        >
          {/* Sidebar Header */}
          <div className="flex items-center justify-between px-3 py-2 border-b border-white/5">
            <span className="text-[11px] font-medium text-gray-400 uppercase tracking-wider">
              Проводник
            </span>
            <div className="flex items-center gap-1">
              <button
                onClick={() => loadFileTree(projectPath, fileExtensions)}
                disabled={isLoadingTree || !projectPath}
                className="p-1 text-gray-500 hover:text-gray-300 hover:bg-white/5 rounded transition-colors disabled:opacity-50"
                title="Обновить"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isLoadingTree ? 'animate-spin' : ''}`} />
              </button>
              <button
                onClick={() => setShowProjectModal(true)}
                className="p-1 text-gray-500 hover:text-gray-300 hover:bg-white/5 rounded transition-colors"
                title="Открыть папку"
              >
                <FolderOpen className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          {/* Project Name */}
          {projectPath && (
            <div 
              className="flex items-center gap-2 px-3 py-1.5 bg-white/[0.02] border-b border-white/5 cursor-pointer hover:bg-white/5"
              onClick={() => setShowProjectModal(true)}
              title={projectPath}
            >
              <Folder className="w-4 h-4 text-blue-400 flex-shrink-0" />
              <span className="text-[12px] text-gray-300 font-medium truncate">
                {projectPath.split('/').pop()}
              </span>
              {isIndexing && <Loader2 className="w-3 h-3 animate-spin text-blue-400 ml-auto" />}
              {indexStatus === 'success' && <CheckCircle2 className="w-3 h-3 text-green-400 ml-auto" />}
            </div>
          )}

          {/* File Tree */}
          <div className="flex-1 overflow-y-auto overflow-x-hidden">
            {!projectPath ? (
              <div className="flex flex-col items-center justify-center h-full px-4 text-center">
                <FolderOpen className="w-10 h-10 text-gray-600 mb-3" />
                <p className="text-[12px] text-gray-500 mb-3">
                  Проект не выбран
                </p>
                <button
                  onClick={() => setShowProjectModal(true)}
                  className="px-3 py-1.5 text-[12px] text-blue-400 hover:text-blue-300 bg-blue-500/10 hover:bg-blue-500/20 rounded-lg transition-colors"
                >
                  Открыть папку
                </button>
              </div>
            ) : isLoadingTree ? (
              <div className="flex items-center justify-center h-32 text-gray-500">
                <Loader2 className="w-5 h-5 animate-spin mr-2" />
                <span className="text-[12px]">Загрузка...</span>
              </div>
            ) : fileTree ? (
              <div className="py-1">
                {fileTree.children?.map((child, idx) => (
                  <FileTreeItem
                    key={child.path || idx}
                    node={child}
                    depth={0}
                    expandedDirs={expandedDirs}
                    onToggleDir={toggleDirectory}
                    onFileClick={handleFileClick}
                    selectedFile={selectedFilePath}
                  />
                ))}
              </div>
            ) : (
              <div className="flex items-center justify-center h-32 text-[12px] text-gray-500">
                Нет файлов
              </div>
            )}
          </div>

          {/* Sidebar Footer */}
          {fileTreeStats && projectPath && (
            <div className="px-3 py-2 border-t border-white/5 bg-[#0a0a0f]">
              <div className="flex items-center justify-between text-[10px] text-gray-600">
                <span>{fileTreeStats.total_files} файлов</span>
                <span>{fileTreeStats.total_directories} папок</span>
              </div>
              {fileExtensions && (
                <div className="flex flex-wrap gap-1 mt-1.5">
                  {fileExtensions.split(',').slice(0, 4).map((ext, i) => (
                    <span key={i} className="px-1.5 py-0.5 text-[9px] bg-white/5 text-gray-500 rounded">
                      {ext.trim()}
                    </span>
                  ))}
                  {fileExtensions.split(',').length > 4 && (
                    <span className="px-1.5 py-0.5 text-[9px] bg-white/5 text-gray-500 rounded">
                      +{fileExtensions.split(',').length - 4}
                    </span>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Quick Actions */}
          <div className="px-2 py-2 border-t border-white/5 flex gap-1">
            <button
              onClick={handleIndex}
              disabled={isIndexing || !projectPath}
              className="flex-1 flex items-center justify-center gap-1.5 px-2 py-1.5 text-[11px] text-gray-400 hover:text-white bg-white/5 hover:bg-white/10 rounded transition-colors disabled:opacity-50"
              title="Индексировать проект"
            >
              <Database className="w-3.5 h-3.5" />
              Индекс
            </button>
            <button
              onClick={() => setShowNewFileDialog(true)}
              className="flex-1 flex items-center justify-center gap-1.5 px-2 py-1.5 text-[11px] text-gray-400 hover:text-white bg-white/5 hover:bg-white/10 rounded transition-colors"
              title="Новый файл"
            >
              <Plus className="w-3.5 h-3.5" />
              Файл
            </button>
          </div>
        </div>
      )}

      {/* Resize Handle */}
      {sidebarOpen && (
        <div
          className={`w-1 cursor-col-resize flex-shrink-0 group relative ${
            isResizing ? 'bg-blue-500' : 'bg-transparent hover:bg-blue-500/50'
          }`}
          onMouseDown={handleResizeStart}
        >
          {/* Visual indicator line */}
          <div className={`absolute inset-y-0 left-0 w-px ${
            isResizing ? 'bg-blue-500' : 'bg-white/5 group-hover:bg-blue-500/50'
          }`} />
        </div>
      )}

      {/* Main Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Tab Bar */}
        <div className="flex items-center gap-0.5 px-1 py-0.5 bg-[#0d0d12] border-b border-white/5">
          {/* Toggle Sidebar */}
          <button
            onClick={toggleSidebar}
            className="p-1.5 text-gray-500 hover:text-gray-300 hover:bg-white/5 rounded transition-colors flex-shrink-0"
            title={sidebarOpen ? 'Скрыть панель' : 'Показать панель'}
          >
            {sidebarOpen ? <PanelLeftClose className="w-3.5 h-3.5" /> : <PanelLeft className="w-3.5 h-3.5" />}
          </button>

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
                onClick={() => {
                  setActiveFileId(file.id)
                  if (file.path) setSelectedFilePath(file.path)
                }}
              >
                {file.language === 'python' 
                  ? <FileCode className="w-3 h-3 text-yellow-400/70" />
                  : <FileText className="w-3 h-3 text-gray-400/70" />
                }
                <span className="max-w-[100px] truncate">{file.name}</span>
                {file.isModified && <span className="w-1.5 h-1.5 bg-amber-400 rounded-full" />}
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
                {isExecuting ? <Loader2 className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
                <span className="hidden lg:inline">Выполнить</span>
              </button>
            )}
            <button onClick={handleCopy} className="p-1 text-gray-500 hover:text-gray-300 hover:bg-white/5 rounded transition-colors" title="Копировать">
              <Copy className="w-3 h-3" />
            </button>
            <button onClick={handleDownload} className="p-1 text-gray-500 hover:text-gray-300 hover:bg-white/5 rounded transition-colors" title="Скачать">
              <Download className="w-3 h-3" />
            </button>
            <button onClick={handleReset} className="p-1 text-gray-500 hover:text-gray-300 hover:bg-white/5 rounded transition-colors" title="Сбросить">
              <RotateCcw className="w-3 h-3" />
            </button>
          </div>
        </div>

        {/* Editor */}
        <div className="flex-1 overflow-hidden relative">
          {isLoadingFile && (
            <div className="absolute inset-0 bg-black/50 flex items-center justify-center z-10">
              <Loader2 className="w-6 h-6 animate-spin text-blue-400" />
            </div>
          )}
          {activeFile && (
            <CodeEditor
              key={activeFile.id}
              initialCode={activeFile.content}
              language={activeFile.language}
              onCodeChange={handleCodeChange}
              onExecute={handleExecute}
              isExecuting={isExecuting}
            />
          )}
        </div>
      </div>

      {/* Modals */}
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
              onKeyDown={(e) => e.key === 'Enter' && handleAddFile()}
            />
            <div className="flex gap-2 justify-end">
              <button onClick={() => setShowNewFileDialog(false)} className="px-4 py-2 text-sm text-gray-400 hover:bg-white/10 rounded transition-colors">
                Отмена
              </button>
              <button onClick={handleAddFile} className="px-4 py-2 text-sm bg-blue-600 text-white hover:bg-blue-700 rounded transition-colors">
                Создать
              </button>
            </div>
          </div>
        </div>
      )}

      {showProjectModal && (
        <div 
          className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50"
          onClick={() => !isBrowsing && setShowProjectModal(false)}
        >
          <div className="bg-[#16161e] border border-white/10 rounded-xl shadow-2xl w-full max-w-md mx-4 overflow-hidden" onClick={e => e.stopPropagation()}>
            <div className="px-5 py-4 border-b border-white/5">
              <h3 className="text-base font-semibold text-gray-100 flex items-center gap-2">
                <FolderOpen className="w-5 h-5 text-blue-400" />
                Открыть проект
              </h3>
            </div>

            <div className="p-5 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Путь к папке проекта</label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={tempPath}
                    onChange={e => setTempPath(e.target.value)}
                    placeholder="/Users/you/projects/my-app"
                    className="flex-1 bg-white/5 border border-white/10 rounded-lg px-3 py-2.5 text-white placeholder-gray-500 focus:outline-none focus:border-blue-500/50"
                  />
                  <button
                    onClick={handleBrowseFolder}
                    disabled={isBrowsing}
                    className="px-3 py-2.5 text-sm font-medium text-gray-300 hover:text-white bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg transition-colors disabled:opacity-50 flex items-center gap-2"
                  >
                    {isBrowsing ? <Loader2 className="w-4 h-4 animate-spin" /> : <FolderOpen className="w-4 h-4" />}
                    Обзор
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Расширения файлов</label>
                <input
                  type="text"
                  value={tempExtensions}
                  onChange={e => setTempExtensions(e.target.value)}
                  placeholder=".py,.js,.ts"
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2.5 text-white placeholder-gray-500 focus:outline-none focus:border-blue-500/50"
                />
                <p className="text-xs text-gray-500 mt-1.5">Через запятую: .py,.js,.ts</p>
              </div>
            </div>

            <div className="px-5 py-4 bg-white/[0.02] border-t border-white/5 flex gap-3 justify-end">
              <button onClick={() => setShowProjectModal(false)} className="px-4 py-2 text-sm font-medium text-gray-300 hover:text-white bg-white/5 hover:bg-white/10 rounded-lg transition-colors">
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
