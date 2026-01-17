import { useState } from 'react'

interface TaskInputProps {
  onStart: (task: string) => void
  isRunning: boolean
}

export function TaskInput({ onStart, isRunning }: TaskInputProps) {
  const [task, setTask] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (task.trim() && !isRunning) {
      onStart(task.trim())
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label htmlFor="task" className="block text-sm font-medium mb-2">
          Введите задачу:
        </label>
        <textarea
          id="task"
          value={task}
          onChange={(e) => setTask(e.target.value)}
          placeholder="Например: Создать класс для работы с конфигурацией из TOML файла"
          className="w-full min-h-[120px] px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-y"
          disabled={isRunning}
        />
      </div>
      <button
        type="submit"
        disabled={!task.trim() || isRunning}
        className="w-full px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
      >
        {isRunning ? 'Выполняется...' : 'Запустить'}
      </button>
    </form>
  )
}
