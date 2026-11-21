# Қақпан
Учебный антифрод-сервис. FastAPI в `backend/`, Next.js в `frontend/`.
Требуются Python 3.10+, Node.js 20.9+, npm, make и lsof.
Бэкенд: `python3 -m venv backend/.venv && backend/.venv/bin/pip install -r backend/requirements.txt`.
Фронтенд: `npm ci --prefix frontend`.
Для другого API скопируйте `frontend/.env.example` в `frontend/.env.local` и задайте `NEXT_PUBLIC_API_URL`.
Запуск из корня: `make dev`. На пустой базе создаётся учебная операция. Ctrl+C останавливает оба сервера.
Клиент — [localhost:3000/client](http://localhost:3000/client)
Доверенное лицо — [localhost:3000/trusted](http://localhost:3000/trusted)
Аналитик — [localhost:3000/analyst](http://localhost:3000/analyst)
