# ==============================================
# Afroo Exchange AI Bot - Dockerfile
# ==============================================

# ==============================================
# Stage 1: Builder - Install dependencies
# ==============================================
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# ==============================================
# Stage 2: Runtime - Lightweight final image
# ==============================================
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local

# Copy application code
COPY afroo_ai_bot.py .

# Create log directory
RUN mkdir -p /app/logs

# Add local Python packages to PATH
ENV PATH=/root/.local/bin:$PATH

# Run the bot with unbuffered output (-u flag)
CMD ["python", "-u", "afroo_ai_bot.py"]
