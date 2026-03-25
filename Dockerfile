FROM python:3.12-slim

# Prevent Python from writing pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install production dependencies only
RUN pip install --no-cache-dir \
    fastapi>=0.104.0 \
    uvicorn>=0.24.0 \
    jinja2>=3.1.0 \
    python-multipart>=0.0.6 \
    python-dotenv>=1.0.0 \
    cryptography>=42.0.0 \
    httpx>=0.27.0

# Copy application code
COPY src/ ./src/
COPY templates/ ./templates/
COPY static/ ./static/

# Create data directory
RUN mkdir -p /app/data

EXPOSE 8086

CMD ["python", "-m", "src.api"]
