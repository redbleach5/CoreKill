# Model Router - Абстракция для выбора моделей

## Текущая реализация

Система использует `ModelRouter` для выбора моделей. Текущая реализация (`SimpleModelRouter`) выбирает одну модель на основе типа задачи.

## Будущее расширение: Рое моделей

Архитектура поддерживает будущее расширение для роевого использования моделей без изменения существующего кода.

### Как добавить рое моделей:

1. **Создать новую реализацию ModelRouter:**

```python
class RosterModelRouter(ModelRouter):
    """Реализация с поддержкой роя моделей."""
    
    def select_model_roster(
        self,
        task_type: str,
        preferred_models: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[ModelRosterSelection]:
        # Реализация выбора роя моделей
        # Стратегии: "parallel", "cascade", "voting"
        return ModelRosterSelection(
            models=["model1", "model2", "model3"],
            strategy="parallel",
            metadata={...}
        )
```

2. **Включить в конфиге:**

```toml
[default]
enable_model_roster = true
```

3. **Использовать в агентах (опционально):**

```python
router = get_model_router()
roster = router.select_model_roster(task_type="coding")
if roster:
    # Использовать рое моделей
    results = [run_model(m) for m in roster.models]
    # Выбрать лучший результат или объединить
else:
    # Использовать одну модель (текущая реализация)
    model = router.select_model(task_type="coding")
```

### Преимущества архитектуры:

- ✅ **Dependency Inversion**: Агенты зависят от абстракции `ModelRouter`, а не от конкретной реализации
- ✅ **Отключаемость**: Рое моделей можно включить/выключить через конфиг
- ✅ **Обратная совместимость**: Текущий код работает без изменений
- ✅ **Расширяемость**: Легко добавить новые стратегии выбора моделей
