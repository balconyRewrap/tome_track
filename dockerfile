FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements/requirements.txt requirements.txt
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir --requirement requirements.txt

# create non-root user for runtime
RUN addgroup --system app && adduser --system --ingroup app app

# prepare directories and set ownership to non-root user
RUN mkdir -p /log /app/staticfiles /app/media /dist
COPY --chown=app:app . .
RUN chown -R app:app /app /log /app/staticfiles /app/media /dist

USER app

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]