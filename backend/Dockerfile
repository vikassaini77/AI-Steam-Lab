FROM python:3.11-slim

# Create a non-root user group and user with a home directory
RUN groupadd -r neurolab && useradd -m -r -g neurolab neurolabuser

WORKDIR /app

# Install system dependencies required for OpenCV
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Change ownership of the app directory to the non-root user
RUN chown -R neurolabuser:neurolab /app

# Switch to the non-root user
USER neurolabuser

ENV PYTHONPATH=/app
ENV OMP_NUM_THREADS=1
ENV MKL_NUM_THREADS=1
ENV OPENBLAS_NUM_THREADS=1
ENV YOLO_CONFIG_DIR=/tmp/Ultralytics
ENV ENABLE_YOLO=false
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
