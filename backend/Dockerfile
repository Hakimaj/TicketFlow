# TicketFlow API — production-shaped image.
#
#   docker build -t ticketflow-api ./backend
#
# The image contains no configuration and no secrets: every value is read from
# the environment at run time (see backend/.env.example). Migrations are not
# run on import; the compose stack runs `alembic upgrade head` before serving.

FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Runtime dependencies are declared in pyproject.toml (no dev extras).
COPY pyproject.toml ./
COPY app ./app
RUN python -m pip install --upgrade pip && python -m pip install .

# Migration tooling and the operational scripts.
COPY alembic.ini ./
COPY alembic ./alembic
COPY scripts ./scripts

# Never run as root.
RUN useradd --create-home --uid 10001 ticketflow \
    && chown -R ticketflow:ticketflow /app
USER ticketflow

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
