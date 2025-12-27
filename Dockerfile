# ============================================
# Institutional Trading Bot - Production Dockerfile
# Optimized for Coolify Deployment
# ============================================

FROM python:3.11-slim

# Labels for Coolify
LABEL org.opencontainers.image.title="Institutional Trading Bot"
LABEL org.opencontainers.image.description="Automated crypto trading bot"

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=UTF-8 \
    TZ=UTC

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY *.py ./

# Create data directory for persistence
RUN mkdir -p /app/data

# Default command - run the live bot
CMD ["python", "-u", "live_bot.py"]
