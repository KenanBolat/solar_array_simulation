# Backend image. The same image runs the API (uvicorn) and the instrument
# worker; docker-compose overrides the command per service.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps: build tools for asyncpg/psycopg wheels are usually unneeded
# (binary wheels), but libpq is handy for psycopg[binary] runtime.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Non-root runtime user.
RUN useradd --create-home --uid 10001 appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

# Default command runs the API. The worker service overrides this.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
