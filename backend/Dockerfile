FROM python:3.11-slim

# Create a non-root user group and user
RUN groupadd -r neurolab && useradd -r -g neurolab neurolabuser

WORKDIR /app

# Install system dependencies required for OpenCV
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
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
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]