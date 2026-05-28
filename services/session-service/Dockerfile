FROM python:3.11-slim

ARG PORT=8006

WORKDIR /app

COPY pyproject.toml .
RUN pip install uv && uv sync --frozen --no-dev

COPY src/ src/

EXPOSE ${PORT}

HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=10s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT}/health')"

CMD ["uv", "run", "python", "-m", "datapilot_session"]
