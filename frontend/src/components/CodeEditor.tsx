/**
 * Компонент CodeEditor - компактный редактор кода с подсветкой синтаксиса
 */
import { useState, useRef } from 'react'
import { Terminal, X } from 'lucide-react'

interface CodeEditorProps {
  initialCode?: string
  language?: string
  readOnly?: boolean
  onCodeChange?: (code: string) => void
  onExecute?: (code: string) => Promise<{ output: string; error?: string } | void>
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

  // Синхронизация скролла
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

  // Подсветка синтаксиса Python
  const highlightCode = (text: string): string => {
    if (language !== 'python') return text.replace(/</g, '&lt;').replace(/>/g, '&gt;')

    const keywords = [
      'def', 'class', 'if', 'else', 'elif', 'for', 'while', 'return', 'import',
      'from', 'as', 'try', 'except', 'finally', 'with', 'pass', 'break', 'continue',
      'True', 'False', 'None', 'and', 'or', 'not', 'in', 'is', 'lambda', 'yield', 'async', 'await'
    ]

    let highlighted = text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')

    // Строки
    highlighted = highlighted.replace(
      /(['"])(?:(?=(\\?))\2.)*?\1/g,
      '<span class="text-emerald-400">$&</span>'
    )

    // Комментарии
    highlighted = highlighted.replace(
      /#.*/g,
      '<span class="text-gray-500">$&</span>'
    )

    // Ключевые слова
    keywords.forEach(keyword => {
      highlighted = highlighted.replace(
        new RegExp(`\\b${keyword}\\b`, 'g'),
        `<span class="text-blue-400">${keyword}</span>`
      )
    })

    // Числа
    highlighted = highlighted.replace(
      /\b(\d+\.?\d*)\b/g,
      '<span class="text-amber-400">$1</span>'
    )

    return highlighted
  }

  const lineCount = code.split('\n').length

  return (
    <div className="flex flex-col h-full bg-[#0d1117] overflow-hidden">
      {/* Editor */}
      <div className="flex-1 flex overflow-hidden min-h-0">
        {/* Line numbers */}
        <div className="flex-shrink-0 bg-[#0a0a0f] px-2 py-2 text-right select-none overflow-hidden">
          {Array.from({ length: lineCount }, (_, i) => (
            <div key={i} className="h-5 text-[11px] leading-5 text-gray-600">
              {i + 1}
            </div>
          ))}
        </div>

        {/* Code area */}
        <div className="flex-1 relative overflow-auto">
          {/* Highlight layer */}
          <pre
            ref={highlightRef}
            className="absolute inset-0 p-2 text-[13px] leading-5 font-mono text-gray-300 pointer-events-none whitespace-pre"
            style={{ tabSize: 4 }}
            dangerouslySetInnerHTML={{ __html: highlightCode(code) + '\n' }}
          />

          {/* Textarea */}
          <textarea
            ref={textareaRef}
            value={code}
            onChange={(e) => handleCodeChange(e.target.value)}
            onScroll={handleScroll}
            readOnly={readOnly}
            className="absolute inset-0 p-2 text-[13px] leading-5 font-mono text-transparent bg-transparent resize-none outline-none caret-blue-400 whitespace-pre"
            style={{ tabSize: 4 }}
            spellCheck="false"
            autoCapitalize="off"
            autoCorrect="off"
          />
        </div>
      </div>

      {/* Output Panel - Compact */}
      {showOutput && (
        <div className="flex-shrink-0 border-t border-white/10 bg-[#0a0a0f] max-h-32">
          <div className="flex items-center justify-between px-2 py-1 border-b border-white/5">
            <div className="flex items-center gap-1.5 text-xs text-gray-400">
              <Terminal className="w-3 h-3" />
              <span>Вывод</span>
            </div>
            <button
              onClick={() => setShowOutput(false)}
              className="p-0.5 text-gray-500 hover:text-gray-300 rounded"
            >
              <X className="w-3 h-3" />
            </button>
          </div>
          <div className="p-2 overflow-auto max-h-24">
            {error ? (
              <pre className="text-xs text-red-400 font-mono">{error}</pre>
            ) : output ? (
              <pre className="text-xs text-gray-300 font-mono">{output}</pre>
            ) : isExecuting ? (
              <span className="text-xs text-gray-500">Выполнение...</span>
            ) : (
              <span className="text-xs text-gray-600">Нет вывода</span>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
