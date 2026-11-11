FROM ghcr.io/astral-sh/uv:0.13.5-python3.14-trixie-slim
WORKDIR /app
COPY . .
RUN uv sync --locked --no-dev 
CMD ["uv", "run", "--no-sync", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]