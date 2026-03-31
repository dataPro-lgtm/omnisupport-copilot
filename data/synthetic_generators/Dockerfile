FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ticket_simulator.py .

CMD ["python", "ticket_simulator.py", "--count", "500", "--output", "/data/tickets-seed-batch-001.jsonl"]
