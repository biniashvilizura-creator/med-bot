FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Важно: Render слушает 10000
EXPOSE 10000
CMD ["python", "main.py"]
