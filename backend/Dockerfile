FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --default-timeout=120 --retries 10 -r requirements.txt
COPY . .
RUN useradd -m appuser
USER appuser