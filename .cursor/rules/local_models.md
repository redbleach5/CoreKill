Модели (Ollama):
• Основная кодогенерация: codellama:13b-instruct-q4_0   (или 7b если памяти мало)
• Классификация/планирование:   tinyllama:1.1b или phi-3:mini
• Embeddings (RAG):             nomic-embed-text

Настройки:
• temperature: 0.15–0.35
• top_p: 0.9
• timeout: 300 сек
• retry: 2–3 попытки при ошибке