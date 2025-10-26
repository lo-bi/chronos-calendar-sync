# Multi-stage build for Raspberry Pi (ARM)
FROM python:3.14-slim

WORKDIR /app

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (Chromium only to save space)
RUN playwright install --with-deps chromium

# Copy application code
COPY . .

# Create directory for data persistence
RUN mkdir -p /app/data

# Expose port 8000
EXPOSE 8000

# Run the application
CMD ["python", "-u", "main.py"]
