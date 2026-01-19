/**
 * Компонент IDEPanel - полноценная IDE для редактирования и выполнения кода
 * Поддерживает несколько файлов, выполнение кода и просмотр результатов
 */
import { useState } from 'react'
import { Plus, X, Trash2, Save } from 'lucide-react'
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
}

export function IDEPanel({
  initialCode = '',
  onCodeChange,
  onExecute,
  isExecuting = false
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

  const activeFile = files.find(f => f.id === activeFileId)

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

  const handleRenameFile = (id: string, newName: string) => {
    setFiles(files.map(f =>
      f.id === id ? { ...f, name: newName } : f
    ))
  }

  return (
    <div className="flex flex-col h-full bg-[#0a0a0f] rounded-xl overflow-hidden border border-white/10">
      {/* Tabs */}
      <div className="flex items-center gap-1 px-2 py-2 bg-white/5 border-b border-white/10 overflow-x-auto">
        {files.map(file => (
          <div
            key={file.id}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-sm cursor-pointer transition-colors ${
              activeFileId === file.id
                ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                : 'bg-white/5 text-gray-400 hover:bg-white/10'
            }`}
            onClick={() => setActiveFileId(file.id)}
          >
            <span className="text-xs">{file.language === 'python' ? '🐍' : '📜'}</span>
            <span className="flex-1">{file.name}</span>
            {file.isNew && <span className="text-xs text-amber-400">●</span>}
            {files.length > 1 && (
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  handleDeleteFile(file.id)
                }}
                className="p-0.5 text-gray-500 hover:text-red-400 rounded transition-colors"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        ))}

        {/* Add file button */}
        <button
          onClick={() => setShowNewFileDialog(true)}
          className="flex items-center gap-1 px-2 py-1.5 text-xs text-gray-500 hover:text-gray-300 hover:bg-white/10 rounded transition-colors"
          title="Добавить файл"
        >
          <Plus className="w-3.5 h-3.5" />
        </button>
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
    </div>
  )
}
