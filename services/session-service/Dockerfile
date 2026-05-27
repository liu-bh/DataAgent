FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install uv && uv sync --frozen --no-dev

COPY src/ src/

EXPOSE 8006

CMD ["uv", "run", "python", "-m", "datapilot_session"]
