# Қақпан — банковский симулятор
Next.js App Router, React и TypeScript. В каталоге frontend выполните npm install и npm run dev. Откройте http://localhost:3000. Для production используйте npm run build и npm start.

Запустите FastAPI из корня Qaqpan командой python -m uvicorn backend.app.main:app после установки backend/requirements.txt. По умолчанию Next проксирует /api/v1 на http://127.0.0.1:8000. Для другого сервера задайте QAQPAN_API_ORIGIN до запуска или сборки. Для демо достаточно одного процесса FastAPI, SQLite и синтетических данных.

Маршруты /#client, /#trusted и /#analyst можно открыть в разных вкладках. В кабинете аналитика доступен учебный диалог, проверка реквизитов и сравнение стратегий на тестовом наборе. Состояние переводов определяет API. Переключатель ролей предназначен для локальной демонстрации.
