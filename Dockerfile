FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN addgroup --system hussam && adduser --system --ingroup hussam hussam

COPY pyproject.toml requirements.lock README.md ./
RUN python -m pip install --no-cache-dir -r requirements.lock \
    && python -m pip install --no-cache-dir .

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY docs ./docs
COPY scripts ./scripts
COPY .env.example SECURITY.md CONTRIBUTING.md LICENSE CHANGELOG.md ./

RUN chown -R hussam:hussam /app
USER hussam

EXPOSE 8000

# Database migrations are a separate deployment step; the container only starts the API.
CMD ["/app/scripts/render_start.sh"]
