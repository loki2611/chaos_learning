# Stage 1 — Install dependencies
FROM python:3.12-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2 — Runtime image (Python only)
FROM python:3.12-slim
WORKDIR /app

COPY --from=builder /install /usr/local
COPY . .

# Create non-root user (security best practice)
RUN addgroup --system appgroup && \
    adduser --system --ingroup appgroup appuser && \
    chown -R appuser:appgroup /app

USER appuser
EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health/live')"

CMD ["python", "run.py"]
