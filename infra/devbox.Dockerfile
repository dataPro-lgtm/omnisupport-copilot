FROM python:3.11-slim

WORKDIR /workspace

COPY pyproject.toml README.md ./
COPY contracts ./contracts
COPY data ./data
COPY pipelines ./pipelines
COPY services ./services
COPY tests ./tests

RUN pip install --no-cache-dir -e ".[dev]"

CMD ["sh"]
