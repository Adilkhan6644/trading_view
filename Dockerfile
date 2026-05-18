FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DASHBOARD_HOST=0.0.0.0 \
    DASHBOARD_PORT=8000

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p logs data

EXPOSE 8000

CMD ["python", "main.py"]
