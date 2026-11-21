Внутренний регламент хакатона, актуальная структура см. README.

# 🛡️ ҚАҚПАН (Qaqpan) — Smart Anti-Fraud Guardian

> **Проект для хакатона Банка ЦентрКредит (BCC)**\
> Адаптивная многоуровневая система защиты транзакций от социальной инженерии и телефонного мошенничества с сохранением автономии клиента.

---

## ⚡ Организация работы: ПРЯМО В `main` (Без отдельных веток)

Для максимальной скорости на хакатоне **мы НЕ создаем отдельные ветки**.\
Все работают прямо в `main`. Чтобы никто не затирал чужой код и не было конфликтов, действует **жесткое разделение по файлам**:

### 📂 Кто за какие файлы отвечает (Матрица владения):

| Участник | Роль | Файлы, которые разрешено редактировать |
| :--- | :--- | :--- |
| **Backend 1** | FSM, API, DB & SSE Lead | `backend/app/main.py`<br>`backend/app/db.py`<br>`backend/app/api/transfers.py`<br>`backend/app/api/trusted.py`<br>`backend/app/api/analyst.py`<br>`backend/app/core/state_machine.py`<br>`backend/app/models/schemas.py` |
| **Backend 2** | AI, Rules Engine & Robot | `backend/app/core/rules_engine.py`<br>`backend/app/core/ai_parser.py`<br>`backend/app/core/fallback_rules.py`<br>`backend/app/benchmark/`<br>`backend/app/api/benchmark.py` |
| **Frontend Lead** | Frontend SPA | Папка `frontend/` целиком (экраны бабушки, дочери, аналитика и симулятор) |
| **Backend 3** | QA, Code Review & Polish *(подключается позже)* | `backend/tests/`, аудит граничных случаев, устранение багов, оптимизация правил |

### 🚀 Единая команда для отправки кода:
Каждый работает в своем файле и перед отправкой пишет:
```bash
git pull --rebase origin main && git push origin main
```
Конфликтов не будет, потому что разные люди физически пишут в разные файлы.

---


---

## 🏗️ Архитектура проекта

```
Qaqpan/
├── backend/                  # FastAPI сервис
│   ├── app/
│   │   ├── main.py           # Запуск FastAPI, CORS, подключение роутеров (Backend 1)
│   │   ├── db.py             # Хранилище сессий и состояние транзакций (Backend 1)
│   │   ├── models/
│   │   │   └── schemas.py    # Pydantic модели запросов/ответов (Backend 1)
│   │   ├── api/
│   │   │   ├── transfers.py  # Эндпоинты бабушки (Backend 1)
│   │   │   ├── trusted.py    # Эндпоинты дочери (Backend 1)
│   │   │   ├── analyst.py    # Эндпоинты аналитика (Backend 1)
│   │   │   └── benchmark.py  # Эндпоинт запуска симулятора (Backend 2)
│   │   ├── core/
│   │   │   ├── state_machine.py # Автомат состояний (Backend 1)
│   │   │   ├── rules_engine.py  # Скоринг по порогам (Backend 2)
│   │   │   ├── ai_parser.py     # LLM парсер на RU/KZ (Backend 2)
│   │   │   └── fallback_rules.py# Локальный regex-парсер (Backend 2)
│   │   └── benchmark/
│   │       ├── adversarial_robot.py # Генератор атак (Backend 2)
│   │       ├── dataset_generator.py # Базовые датасеты (Backend 2)
│   │       └── evaluator.py         # Расчет Confusion Matrix (Backend 2)
│   ├── requirements.txt
│   └── tests/
├── frontend/                 # React (Vite + Tailwind) SPA
│   ├── src/
│   │   ├── components/
│   │   │   ├── ClientView.jsx    # Экран бабушки (перевод, вопрос, отмена)
│   │   │   ├── TrustedView.jsx   # Экран дочери (пуш, карточка, решение)
│   │   │   └── AnalystView.jsx   # Дашборд банка + запуск симулятора
│   │   └── App.jsx
│   └── package.json
└── README.md
```
