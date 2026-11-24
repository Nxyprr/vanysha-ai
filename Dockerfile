
FROM python:3.12-slim

WORKDIR /srv

# Bibliotecas del sistema necesarias para OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxcb1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Dependencias de Python
COPY backend/requirements.txt backend/requirements.txt
COPY backend/requirements-yolo.txt backend/requirements-yolo.txt

RUN pip install --no-cache-dir -r backend/requirements.txt \
    && pip install --no-cache-dir -r backend/requirements-yolo.txt

# Aplicación y modelo
COPY backend backend
COPY frontend frontend

ENV VANYSHA_DATA_DIR=/data
ENV VANYSHA_DETECTOR=auto
ENV VANYSHA_MODEL=models/yolo11n_safety.pt
ENV OMP_NUM_THREADS=1
ENV MKL_NUM_THREADS=1

VOLUME /data

WORKDIR /srv/backend

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
