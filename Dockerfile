FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Install dependencies before application code to maximize Docker layer caching.
COPY requirements.txt ./
RUN python -m venv "$VIRTUAL_ENV" \
    && pip install --upgrade pip \
    && pip install --requirement requirements.txt

# Run as an unprivileged user instead of root inside the container.
RUN addgroup --system app && adduser --system --ingroup app app

COPY app ./app
COPY main.py ./main.py
RUN chown --recursive app:app /app

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
