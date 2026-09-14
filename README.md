# TaskFlow

Небольшой менеджер задач на [Flet](https://flet.dev) (Python + Flutter UI).

## Возможности

- Добавление задач с приоритетом (Low / Medium / High)
- Отметка задач как выполненных
- Фильтры: All / Active / Done
- Удаление отдельных задач и очистка выполненных одним нажатием
- Светлая/тёмная тема с сохранением выбора
- Данные и настройки сохраняются локально в `~/.taskflow/` (JSON), приложение не требует базы данных или сервера

## Структура проекта

```
flet-app/
├── main.py              # точка входа
├── taskflow/
│   ├── models.py         # модель Task/Priority
│   ├── storage.py        # чтение/запись JSON (задачи, настройки)
│   └── ui.py              # весь UI и логика приложения
├── requirements.txt
└── .gitignore
```

## Запуск

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python main.py
```

По умолчанию Flet открывает приложение в собственном окне (desktop view). Чтобы запустить в браузере вместо этого:

```bash
flet run --web main.py
```

## Требования

- Python 3.10+
- Flet 0.86.x
