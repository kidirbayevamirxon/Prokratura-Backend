FROM python:3.12-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Copy dependency specifications first for layer caching
COPY pyproject.toml uv.lock* /app/

# Install the application dependencies
RUN uv sync --frozen --no-cache

# Copy the rest of the application code
COPY . /app

# Make entrypoint executable
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
