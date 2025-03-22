FROM python:3.9-slim-buster

WORKDIR /app

# Устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY . .

# Создаем папку для базы данных и загрузок
RUN mkdir -p /app/static/uploads && \
    touch /app/database.db && \
    chmod 666 /app/database.db

# Запуск приложения
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]