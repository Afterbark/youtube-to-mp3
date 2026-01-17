FROM python:3.10-slim

# Install system dependencies (FFmpeg is required)
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p downloads

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "app:app"]