FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
WORKDIR /repo
COPY app/backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY model /repo/model
COPY data/submission /repo/data/submission
COPY app/SETTINGS.yaml /repo/app/SETTINGS.yaml
COPY app/backend /repo/app/backend
ENV PYTHONPATH=/repo/app/backend
WORKDIR /repo/app/backend
CMD ["sh", "-c", "alembic upgrade head && uvicorn npsdm_app.api:app --host 0.0.0.0 --port 8000"]
