FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including fonts for subtitles and edge-tts support
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    curl \
    espeak \
    espeak-data \
    libespeak-dev \
    fontconfig \
    fonts-dejavu-core \
    fonts-noto-cjk \
    && fc-cache -fv \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
# First install torch CPU (from PyTorch index) - needed for faster-whisper and demucs
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p temp output cookies

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]