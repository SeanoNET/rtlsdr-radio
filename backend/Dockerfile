# RTL-SDR Radio Backend Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for rtl_fm
RUN apt-get update && apt-get install -y --no-install-recommends \
    rtl-sdr \
    librtlsdr0 \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install welle-cli build dependencies and build from source
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    cmake \
    librtlsdr-dev \
    libfftw3-dev \
    libfaad-dev \
    libmpg123-dev \
    && git clone --depth 1 https://github.com/AlbrechtL/welle.io.git /tmp/welle.io \
    && cd /tmp/welle.io \
    && mkdir build && cd build \
    && cmake .. -DRTLSDR=ON -DBUILD_WELLE_IO=OFF -DBUILD_WELLE_CLI=ON \
    && make -j$(nproc) \
    && cp welle-cli /usr/local/bin/ \
    && cd / && rm -rf /tmp/welle.io \
    && apt-get purge -y git build-essential cmake \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

ENV PYTHONUNBUFFERED=1

# Expose API port, FM stream port, and DAB+ welle-cli port
EXPOSE 8000 8088 8089

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/tuner/status || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
