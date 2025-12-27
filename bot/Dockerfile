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
COPY main.py .
COPY config.py .
COPY config.json .
COPY requirements.txt .
COPY api/ api/
COPY assets/ assets/
COPY cogs/ cogs/
COPY data/ data/
COPY handlers/ handlers/
COPY models/ models/
COPY scripts/ scripts/
COPY tasks/ tasks/
COPY utils/ utils/

# Create logs directory
RUN mkdir -p logs

# Add local Python packages to PATH
ENV PATH=/root/.local/bin:$PATH

# Run bot
CMD ["python", "main.py"]
