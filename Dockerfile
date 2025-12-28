# ============================================
# Institutional Trading Bot - Production Dockerfile
# Optimized for Coolify Deployment
# ============================================

# Build stage - install dependencies
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ============================================
# Production stage - minimal runtime image
# ============================================
FROM python:3.11-slim AS production

# Labels for Coolify & OCI compliance
LABEL org.opencontainers.image.title="Institutional Trading Bot"
LABEL org.opencontainers.image.description="Automated crypto trading bot with signal-based entries"
LABEL org.opencontainers.image.vendor="TradingBot"
LABEL org.opencontainers.image.version="1.0.0"
LABEL coolify.managed="true"

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=UTF-8 \
    PYTHONFAULTHANDLER=1 \
    TZ=UTC \
    PATH="/opt/venv/bin:$PATH"

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tini \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN groupadd --gid 1000 botuser && \
    useradd --uid 1000 --gid 1000 --shell /bin/bash --create-home botuser

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application code
COPY --chown=botuser:botuser *.py ./

# Create data directory for persistence
RUN mkdir -p /app/data && chown -R botuser:botuser /app/data

# Health check - verifies the process is running
# For trading bots, we check if the Python process is alive
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD pgrep -f "python.*live_bot.py" > /dev/null || exit 1

# Switch to non-root user
USER botuser

# Volume for persistent data
VOLUME ["/app/data"]

# Use tini as init system for proper signal handling
ENTRYPOINT ["/usr/bin/tini", "--"]

# Default command - run the live bot
CMD ["python", "-u", "live_bot.py"]
