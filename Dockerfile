FROM python:3.9-slim

WORKDIR /app

# Install dependencies first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code and data
COPY run.py .
COPY config.yaml .
COPY data.csv .

# Default command: run the pipeline with paths relative to /app,
# writing outputs into /app (no hard-coded absolute paths in run.py).
CMD ["python", "run.py", "--input", "data.csv", "--config", "config.yaml", "--output", "metrics.json", "--log-file", "run.log"]

