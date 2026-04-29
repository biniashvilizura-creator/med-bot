FROM python:3.10-slim
WORKDIR /app
# Эта строчка установит всё необходимое
RUN pip install --no-cache-dir aiogram openai
COPY . .
CMD ["python", "main.py"]
