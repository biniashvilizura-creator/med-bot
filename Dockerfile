FROM python:3.10-slim
WORKDIR /app
# Устанавливаем библиотеки прямо при сборке
RUN pip install --no-cache-dir aiogram==3.10.0 openai
COPY . .
CMD ["python", "main.py"]
