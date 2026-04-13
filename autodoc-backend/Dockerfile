FROM python:3.13-slim

WORKDIR /app

# Install git (required for repo cloning)
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

# Copy project metadata first for layer caching
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install the package and its dependencies
RUN pip install --no-cache-dir -e .

EXPOSE 8080

CMD ["autodoc-server"]
