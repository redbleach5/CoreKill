# Персистентность задач (РЕАЛИЗОВАНО)

## Текущее поведение

**Задачи теперь сохраняются и могут быть восстановлены после перезапуска.**

### Как это работает:

1. **Backend Checkpoints:**
   - Состояние `AgentState` сохраняется в JSON после каждого этапа workflow
   - Хранится в директории `.task_checkpoints/{task_id}/`
   - Структура: `metadata.json` (метаданные) + `state.json` (полное состояние)
   - Автоматическая очистка checkpoint старше 24 часов

2. **Frontend localStorage:**
   - Сообщения чата сохраняются в `localStorage`
   - Этапы, результаты и метрики также сохраняются
   - Восстанавливается при обновлении страницы

3. **При перезапуске backend:**
   - Checkpoint сохраняются на диске
   - Задачи можно возобновить через API `/api/tasks/{id}/resume`
   - Frontend показывает список незавершенных задач

4. **При перезапуске frontend:**
   - Состояние восстанавливается из `localStorage`
   - Показывается баннер с предложением восстановить диалог
   - Можно восстановить или начать заново

## Архитектура

### Backend компоненты:

```
infrastructure/task_checkpointer.py
├── TaskCheckpointer          # Основной класс для работы с checkpoint
│   ├── save_checkpoint()     # Сохранение состояния
│   ├── load_checkpoint()     # Загрузка состояния
│   ├── list_active_tasks()   # Список незавершенных задач
│   ├── mark_completed()      # Пометить как завершенную
│   ├── mark_paused()         # Пометить как приостановленную
│   └── delete_checkpoint()   # Удалить checkpoint
└── get_task_checkpointer()   # Singleton getter
```

### API Endpoints:

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/api/tasks/active` | GET | Список незавершенных задач |
| `/api/tasks/history` | GET | История всех задач |
| `/api/tasks/{id}` | GET | Детали задачи |
| `/api/tasks/{id}/resume` | POST | Возобновить задачу (SSE) |
| `/api/tasks/{id}/cancel` | POST | Приостановить задачу |
| `/api/tasks/{id}` | DELETE | Удалить checkpoint |

### Frontend компоненты:

```
hooks/useTaskPersistence.ts
├── saveState()           # Сохранить в localStorage
├── loadState()           # Загрузить из localStorage
├── clearState()          # Очистить localStorage
├── fetchActiveTasks()    # Получить задачи с backend
├── resumeTask()          # Возобновить задачу
├── deleteTask()          # Удалить задачу
└── cancelTask()          # Отменить задачу
```

### UI (App.tsx):

- Recovery Banner при загрузке (если есть что восстановить)
- Кнопки "Восстановить" / "Начать заново" для localStorage
- Список незавершенных задач с backend с кнопками "Продолжить" / "Удалить"

## Конфигурация

```toml
# config.toml

[persistence]
# Включить систему checkpoint
enabled = true

# Директория для checkpoint
checkpoint_directory = ".task_checkpoints"

# Максимальный возраст checkpoint (часы)
max_checkpoint_age_hours = 24

# Автоматически приостанавливать при разрыве соединения
auto_pause_on_disconnect = true
```

## Структура checkpoint

```
.task_checkpoints/
└── {task_id}/
    ├── metadata.json     # Метаданные задачи
    │   ├── task_id
    │   ├── task_text
    │   ├── created_at
    │   ├── updated_at
    │   ├── last_stage
    │   ├── status        # running | paused | completed | failed
    │   ├── iteration
    │   └── model
    └── state.json        # Полный AgentState
        ├── task
        ├── intent_result
        ├── plan
        ├── context
        ├── tests
        ├── code
        ├── validation_results
        └── ...
```

## Поток данных

```
1. Пользователь отправляет задачу
   ↓
2. Backend создает task_id, сохраняет начальный checkpoint
   ↓
3. После каждого этапа (intent → planner → ... → critic):
   - workflow_nodes вызывает _save_checkpoint()
   - TaskCheckpointer сохраняет state.json + metadata.json
   ↓
4. Frontend получает SSE события, сохраняет в localStorage
   ↓
5. При падении/обновлении:
   - Backend: checkpoint на диске
   - Frontend: состояние в localStorage
   ↓
6. При восстановлении:
   - Frontend проверяет localStorage и /api/tasks/active
   - Показывает Recovery Banner
   - Пользователь выбирает: восстановить или начать заново
   ↓
7. При "Продолжить":
   - POST /api/tasks/{id}/resume
   - Backend загружает checkpoint, отправляет сохраненные результаты через SSE
   - Frontend отображает восстановленное состояние
```

## Рекомендации для пользователей

1. **Checkpoint автоматические** — не нужно ничего делать вручную
2. **При обновлении страницы** — появится баннер с предложением восстановить
3. **При падении backend** — задачи сохраняются на диске, можно продолжить после перезапуска
4. **Очистка** — старые checkpoint (>24ч) удаляются автоматически
5. **Отключение** — установите `persistence.enabled = false` в config.toml

## Ограничения

1. **Возобновление workflow** — пока возвращает только сохраненные результаты, не продолжает выполнение с последнего этапа (планируется в будущем)
2. **Большие контексты** — могут занимать место на диске
3. **Параллельные задачи** — каждая задача имеет свой checkpoint
