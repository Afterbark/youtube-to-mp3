# Use a lightweight Python base image
FROM python:3.10-slim

# 1. Install system dependencies (FFmpeg is required for format conversion)
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# 2. Set the working directory inside the container
WORKDIR /app

# 3. Copy the requirements file and install Python libraries
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copy the rest of the application code
COPY . .

# 5. Create the downloads folder inside the container
RUN mkdir -p downloads

# 6. Command to run the app using Gunicorn
# "app:app" means: look in app.py for the variable named 'app'
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "app:app"]