/**
 * Компонент CodeEditor - встроенный редактор кода с подсветкой синтаксиса
 * Использует простую реализацию с textarea и подсветкой синтаксиса
 */
import { useState, useRef, useEffect } from 'react'
import { Play, Copy, Download, RotateCcw, Settings2 } from 'lucide-react'

interface CodeEditorProps {
  initialCode?: string
  language?: string
  readOnly?: boolean
  onCodeChange?: (code: string) => void
  onExecute?: (code: string) => Promise<void>
  isExecuting?: boolean
}

export function CodeEditor({
  initialCode = '',
  language = 'python',
  readOnly = false,
  onCodeChange,
  onExecute,
  isExecuting = false
}: CodeEditorProps) {
  const [code, setCode] = useState(initialCode)
  const [output, setOutput] = useState('')
  const [error, setError] = useState('')
  const [showOutput, setShowOutput] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const highlightRef = useRef<HTMLPreElement>(null)

  // Синхронизация высоты textarea с содержимым
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 600) + 'px'
    }
  }, [code])

  // Синхронизация скролла между textarea и highlight
  const handleScroll = (e: React.UIEvent<HTMLTextAreaElement>) => {
    if (highlightRef.current) {
      highlightRef.current.scrollLeft = e.currentTarget.scrollLeft
      highlightRef.current.scrollTop = e.currentTarget.scrollTop
    }
  }

  const handleCodeChange = (newCode: string) => {
    setCode(newCode)
    onCodeChange?.(newCode)
  }

  const handleExecute = async () => {
    if (!onExecute) return
    
    setError('')
    setOutput('')
    setShowOutput(true)

    try {
      await onExecute(code)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Неизвестная ошибка при выполнении')
    }
  }

  const handleCopy = async () => {
    await navigator.clipboard.writeText(code)
  }

  const handleDownload = () => {
    const element = document.createElement('a')
    const file = new Blob([code], { type: 'text/plain' })
    element.href = URL.createObjectURL(file)
    element.download = `code.${language === 'python' ? 'py' : 'js'}`
    document.body.appendChild(element)
    element.click()
    document.body.removeChild(element)
  }

  const handleReset = () => {
    setCode(initialCode)
    setOutput('')
    setError('')
  }

  // Простая подсветка синтаксиса для Python
  const highlightCode = (text: string): string => {
    if (language !== 'python') return text

    const keywords = [
      'def', 'class', 'if', 'else', 'elif', 'for', 'while', 'return', 'import',
      'from', 'as', 'try', 'except', 'finally', 'with', 'pass', 'break', 'continue',
      'True', 'False', 'None', 'and', 'or', 'not', 'in', 'is', 'lambda', 'yield'
    ]

    let highlighted = text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')

    // Подсветка строк
    highlighted = highlighted.replace(
      /(['"])(?:(?=(\\?))\2.)*?\1/g,
      '<span class="text-emerald-400">$&</span>'
    )

    // Подсветка комментариев
    highlighted = highlighted.replace(
      /#.*/g,
      '<span class="text-gray-500">$&</span>'
    )

    // Подсветка ключевых слов
    keywords.forEach(keyword => {
      const regex = new RegExp(`\\b${keyword}\\b`, 'g')
      highlighted = highlighted.replace(
        regex,
        `<span class="text-blue-400">${keyword}</span>`
      )
    })

    return highlighted
  }

  return (
    <div className="flex flex-col h-full bg-[#0d1117] border border-white/10 rounded-xl overflow-hidden">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 bg-white/5 border-b border-white/10">
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-400">{language.toUpperCase()}</span>
          <span className="text-xs text-gray-600">|</span>
          <span className="text-xs text-gray-500">{code.split('\n').length} строк</span>
        </div>
        <div className="flex items-center gap-1">
          {onExecute && (
            <button
              onClick={handleExecute}
              disabled={isExecuting || readOnly}
              className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium text-emerald-400 hover:bg-emerald-500/10 rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              title="Выполнить код (Ctrl+Enter)"
            >
              <Play className="w-3.5 h-3.5" />
              {isExecuting ? 'Выполнение...' : 'Выполнить'}
            </button>
          )}
          <button
            onClick={handleCopy}
            disabled={readOnly}
            className="p-1.5 text-gray-400 hover:text-white hover:bg-white/10 rounded transition-colors disabled:opacity-50"
            title="Копировать"
          >
            <Copy className="w-4 h-4" />
          </button>
          <button
            onClick={handleDownload}
            disabled={readOnly}
            className="p-1.5 text-gray-400 hover:text-white hover:bg-white/10 rounded transition-colors disabled:opacity-50"
            title="Скачать"
          >
            <Download className="w-4 h-4" />
          </button>
          <button
            onClick={handleReset}
            disabled={readOnly}
            className="p-1.5 text-gray-400 hover:text-white hover:bg-white/10 rounded transition-colors disabled:opacity-50"
            title="Сбросить"
          >
            <RotateCcw className="w-4 h-4" />
          </button>
          <button
            className="p-1.5 text-gray-400 hover:text-white hover:bg-white/10 rounded transition-colors"
            title="Настройки"
          >
            <Settings2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Editor Container */}
      <div className="flex-1 flex overflow-hidden">
        {/* Line numbers */}
        <div className="flex-shrink-0 bg-white/5 border-r border-white/10 px-3 py-4 text-right text-xs text-gray-600 overflow-hidden">
          {code.split('\n').map((_, i) => (
            <div key={i} className="h-6 leading-6">
              {i + 1}
            </div>
          ))}
        </div>

        {/* Code editor */}
        <div className="flex-1 relative overflow-hidden">
          {/* Highlight layer */}
          <pre
            ref={highlightRef}
            className="absolute inset-0 p-4 text-sm font-mono text-transparent bg-transparent pointer-events-none overflow-hidden"
            dangerouslySetInnerHTML={{ __html: highlightCode(code) }}
          />

          {/* Textarea */}
          <textarea
            ref={textareaRef}
            value={code}
            onChange={(e) => handleCodeChange(e.target.value)}
            onScroll={handleScroll}
            readOnly={readOnly}
            className="absolute inset-0 p-4 text-sm font-mono text-gray-300 bg-transparent resize-none outline-none caret-blue-400 overflow-hidden"
            spellCheck="false"
            autoCapitalize="off"
            autoCorrect="off"
          />
        </div>
      </div>

      {/* Output Panel */}
      {showOutput && (
        <div className="flex-shrink-0 border-t border-white/10 bg-white/5 max-h-48 overflow-hidden flex flex-col">
          <div className="flex items-center justify-between px-4 py-2 bg-white/5 border-b border-white/10">
            <span className="text-sm font-medium text-gray-300">Результат выполнения</span>
            <button
              onClick={() => setShowOutput(false)}
              className="text-xs text-gray-500 hover:text-gray-300"
            >
              ✕
            </button>
          </div>
          <div className="flex-1 overflow-auto p-4">
            {error ? (
              <div className="text-sm text-red-400 font-mono whitespace-pre-wrap">{error}</div>
            ) : (
              <div className="text-sm text-gray-300 font-mono whitespace-pre-wrap">{output}</div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
