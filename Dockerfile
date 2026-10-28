# Dockerfile for running the BrandVerity backend as a standalone container
# (used for no-card hosting, e.g. a Hugging Face Docker Space).
# The container listens on port 7860 and seeds the demo data on startup
# (seed.py is idempotent), so Northpeak, its 6 rules, and the demo users
# (password demo123) exist even on a fresh container.
FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
EXPOSE 7860
CMD python seed.py && uvicorn app.main:app --host 0.0.0.0 --port 7860
