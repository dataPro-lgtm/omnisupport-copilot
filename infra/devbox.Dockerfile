FROM python:3.11-slim

WORKDIR /workspace

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY services/rag_api/requirements.txt /tmp/rag_api_requirements.txt
COPY services/tool_api/requirements.txt /tmp/tool_api_requirements.txt
COPY contracts ./contracts
COPY data ./data
COPY analytics ./analytics
COPY pipelines ./pipelines
COPY services ./services
COPY tests ./tests

RUN pip install --no-cache-dir \
    -r /tmp/rag_api_requirements.txt \
    -r /tmp/tool_api_requirements.txt \
    -e ".[dev]"

CMD ["sh"]
