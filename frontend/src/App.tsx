import { useState } from 'react'
import { useAgentStream } from './hooks/useAgentStream'
import { TaskInput } from './components/TaskInput'
import { SidebarOptions, TaskOptions } from './components/SidebarOptions'
import { ProgressSteps } from './components/ProgressSteps'
import { ResultDisplay } from './components/ResultDisplay'

function App() {
  const { stages, results, metrics, isRunning, error, startTask, stopTask } = useAgentStream()
  const [options, setOptions] = useState<TaskOptions>({
    model: '',
    temperature: 0.25,
    disableWebSearch: false,
    maxIterations: 1
  })

  const [currentTask, setCurrentTask] = useState<string>('')

  const handleStartTask = (task: string) => {
    setCurrentTask(task)
    startTask(task, options)
  }

  const handleFeedback = async (feedback: 'positive' | 'negative') => {
    try {
      const response = await fetch('/api/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          task: currentTask,
          feedback
        })
      })
      if (response.ok) {
        alert(feedback === 'positive' ? 'Спасибо за положительный отзыв! 👍' : 'Спасибо за отзыв, учтём! 👎')
      }
    } catch (error) {
      console.error('Ошибка отправки feedback:', error)
    }
  }

  const hasResults = results.task || results.code

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <h1 className="text-2xl font-bold text-gray-900">Cursor Killer - Генерация кода</h1>
        <p className="text-sm text-gray-600 mt-1">Локальная многоагентная система</p>
        <div className="mt-2 text-xs text-gray-500">
          ⚠️ Задачи выполняются в памяти и не сохраняются при перезапуске сервисов
        </div>
      </header>

      <div className="flex">
        {/* Sidebar */}
        <aside className="w-64 bg-white border-r border-gray-200 min-h-screen">
          <SidebarOptions options={options} onChange={setOptions} />
        </aside>

        {/* Main content */}
        <main className="flex-1 p-6 space-y-6">
          {/* Информационное сообщение о персистентности задач */}
          {isRunning && (
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 text-yellow-800">
              <div className="flex items-start">
                <span className="text-xl mr-2">⚠️</span>
                <div>
                  <strong>Важно:</strong> Задача выполняется в памяти. При перезапуске backend или frontend выполнение будет прервано и результаты не сохранятся. 
                  Дождитесь завершения задачи перед перезапуском сервисов.
                </div>
              </div>
            </div>
          )}

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-800">
              <strong>Ошибка:</strong> {error}
            </div>
          )}

          {!hasResults && (
            <div className="bg-white rounded-lg shadow-sm p-6">
              <TaskInput onStart={handleStartTask} isRunning={isRunning} />
            </div>
          )}

          {isRunning && (
            <div className="bg-white rounded-lg shadow-sm p-6">
              <ProgressSteps stages={stages} />
            </div>
          )}

          {hasResults && (
            <div className="bg-white rounded-lg shadow-sm p-6">
              <ResultDisplay 
                results={results} 
                metrics={metrics} 
                task={currentTask}
                onFeedback={handleFeedback}
              />
            </div>
          )}

          {isRunning && (
            <div className="flex justify-center">
              <button
                onClick={stopTask}
                className="px-6 py-3 bg-red-600 text-white rounded-lg hover:bg-red-700"
              >
                Остановить
              </button>
            </div>
          )}
        </main>
      </div>
    </div>
  )
}

export default App
