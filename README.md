# Python MLOps Batch Pipeline

![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## Overview

A minimal batch processing pipeline that loads OHLCV financial time-series data, computes rolling mean statistics, generates binary trading signals, and emits structured metrics with comprehensive observability. Designed as a reference implementation for batch job best practices: deterministic execution, robust validation, structured logging, and containerized deployment.

## Quick Start

```bash
# Clone and setup
git clone https://github.com/yojit2016/python-mlops-pipeline
cd python-mlops-pipeline
python -m venv venv

# Activate (Windows)
venv\Scripts\activate
# Activate (macOS/Linux)
source venv/bin/activate

# Install and run
pip install -r requirements.txt
python run.py \
  --input data.csv \
  --config config.yaml \
  --output metrics.json \
  --log-file run.log
```

**Expected output**: `metrics.json` and `run.log` written to the current directory.

## Features

- **Configuration-driven execution** — All parameters externalized to YAML (seed, window size, version)
- **Deterministic runs** — Seed-based RNG ensures identical results across executions
- **Comprehensive validation** — File existence checks, CSV parsing, schema validation, type coercion
- **Rolling mean computation** — Efficient pandas-based windowed statistics
- **Binary signal generation** — Close > rolling_mean classification with deterministic NaN handling
- **Structured metrics** — Machine-readable JSON output with signal rate, latency, seed tracking
- **Dual-channel logging** — Timestamped logs written to file and stderr simultaneously
- **Graceful error handling** — Detailed error messages written to metrics.json even on failure
- **Dockerized execution** — Self-contained image with pinned dependencies for reproducible deployment
- **No hard-coded paths** — All file locations passed via CLI arguments

## Repository Structure

```
python-mlops-pipeline/
├── run.py                 # Pipeline entry point
├── config.yaml           # Configuration (seed, window, version)
├── data.csv              # Sample OHLCV dataset
├── requirements.txt      # Python dependencies
├── Dockerfile            # Container definition
├── gen_sample_data.py    # Sample data generation utility
├── metrics.json          # Example output (metrics)
├── run.log              # Example output (logs)
└── README.md            # This file
```

| File | Purpose |
|---|---|
| `run.py` | Pipeline orchestrator; loads config + data, validates, computes signals, writes output |
| `config.yaml` | YAML configuration with `seed`, `window`, `version` fields |
| `data.csv` | Input OHLCV dataset (7 columns: timestamp, open, high, low, close, volume_btc, volume_usd) |
| `requirements.txt` | Python dependencies: pandas ≥2.2.3, numpy ≥2.0, PyYAML ≥6.0.2 |
| `Dockerfile` | Multi-layer Docker build (python:3.9-slim base, optimized for layer caching) |
| `gen_sample_data.py` | Development utility to regenerate sample data with deterministic RNG |

## Architecture

```
CSV + YAML
    │
    ▼
Configuration Validation
    │
    ▼
Dataset Validation
    │
    ▼
Rolling Mean
    │
    ▼
Signal Generation
    │
    ▼
Metrics + Logging
    │
    ▼
JSON Output
```

## Installation

### Requirements

- Python 3.9 or later
- pip

### Setup

```bash
# Clone the repository
git clone <repository-url>
cd python-mlops-pipeline

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Configuration

Configuration is externalized to `config.yaml` for reproducibility and flexibility:

```yaml
seed: 42          # Random seed for deterministic execution
window: 5         # Rolling window size (rows for mean calculation)
version: "v1"     # Config/output version identifier
```

### Configuration Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `seed` | integer | Yes | Random seed for numpy; enables deterministic execution |
| `window` | integer (≥1) | Yes | Rolling window size; determines history length for mean |
| `version` | string | Yes | Version identifier; included in metrics and errors |

**Validation**: The pipeline validates that:
- Config file exists and is not empty
- Config is valid YAML and contains a top-level mapping
- All required fields are present
- Types match: `seed` is int, `window` is positive int, `version` is non-empty string

## Running Locally

### Basic Usage

```bash
python run.py \
  --input data.csv \
  --config config.yaml \
  --output metrics.json \
  --log-file run.log
```

### CLI Arguments

| Argument | Required | Description |
|---|---|---|
| `--input` | Yes | Path to input OHLCV CSV file |
| `--config` | Yes | Path to YAML configuration file |
| `--output` | Yes | Path to write metrics JSON |
| `--log-file` | Yes | Path to write human-readable logs |

All paths are relative to the current working directory. The script can be run from any directory with any file names.

### Example

```bash
# Process sample data with default config
python run.py --input data.csv --config config.yaml --output metrics.json --log-file run.log

# Process with custom paths
python run.py \
  --input /path/to/ohlcv_data.csv \
  --config /path/to/config.yaml \
  --output /tmp/results.json \
  --log-file /tmp/execution.log
```

## Docker

### Building

```bash
docker build -t mlops-task .
```

The image is based on `python:3.9-slim` and includes:
- All Python dependencies from `requirements.txt`
- Pipeline code (`run.py`)
- Configuration (`config.yaml`)
- Sample dataset (`data.csv`)

Layer caching optimization: dependencies are installed before application code, so code changes do not invalidate the dependency layer.

### Running

```bash
docker run --rm mlops-task
```

This:
1. Starts a container from the `mlops-task` image
2. Executes the pipeline with default paths: `--input data.csv --config config.yaml --output metrics.json --log-file run.log`
3. Prints metrics JSON to stdout
4. Writes `metrics.json` and `run.log` to `/app` inside the container
5. Removes the container after exit (`--rm`)

### Extracting Output Files

To retrieve output files from the container after a run:

```bash
# Create a stopped container (preserves files)
docker create --name mlops-task-tmp mlops-task

# Copy files from container to host
docker cp mlops-task-tmp:/app/metrics.json .
docker cp mlops-task-tmp:/app/run.log .

# Clean up
docker rm mlops-task-tmp
```

### Exit Codes

- **0**: Pipeline completed successfully
- **Non-zero**: Validation or execution error

## Output

### metrics.json (Success)

Machine-readable metrics in JSON format:

```json
{
  "version": "v1",
  "rows_processed": 10000,
  "metric": "signal_rate",
  "value": 0.4989,
  "latency_ms": 87,
  "seed": 42,
  "status": "success"
}
```

| Field | Type | Description |
|---|---|---|
| `version` | string | Configuration version from `config.yaml` |
| `rows_processed` | integer | Total input rows (including leading NaN rows) |
| `metric` | string | Metric name identifier ("signal_rate") |
| `value` | float | Signal rate: proportion of rows with signal=1 |
| `latency_ms` | integer | Wall-clock execution time in milliseconds |
| `seed` | integer | Random seed used (for reproducibility tracking) |
| `status` | string | "success" on normal completion |

### metrics.json (Error)

Errors are written to the same file with `status="error"`:

```json
{
  "version": "v1",
  "status": "error",
  "error_message": "Input CSV is missing required column 'close'. Found columns: ['timestamp', 'open', 'high', 'low', 'volume_btc', 'volume_usd']"
}
```

### run.log

Human-readable timestamped logs for debugging and compliance:

```
2026-07-02 21:30:05 | INFO     | ============================================================
2026-07-02 21:30:05 | INFO     | Job start
2026-07-02 21:30:05 | INFO     | Args: input=data.csv, config=config.yaml, output=metrics.json, log_file=run.log
2026-07-02 21:30:05 | INFO     | Config loaded + validated: seed=42, window=5, version=v1
2026-07-02 21:30:05 | INFO     | Random seed set: 42
2026-07-02 21:30:05 | INFO     | Rows loaded: 10000 from data.csv
2026-07-02 21:30:05 | INFO     | Rolling mean computed on 'close' with window=5
2026-07-02 21:30:05 | INFO     | Signal generated: 4989 positive signals out of 10000 rows (4 leading rows had insufficient history for window=5 and were set to signal=0)
2026-07-02 21:30:05 | INFO     | Metrics summary: rows_processed=10000, signal_rate=0.4989, latency_ms=87
2026-07-02 21:30:05 | INFO     | Metrics written to metrics.json
2026-07-02 21:30:05 | INFO     | Job end | status=success
```

Logs are written to both file (persistent) and stderr (real-time observation).

## Error Handling

### Validation Strategy

The pipeline uses fail-fast validation to catch errors before expensive computation:

**Configuration Validation**
- File existence and non-empty check
- Valid YAML syntax
- Top-level structure is a mapping (dict)
- All required fields present: `seed`, `window`, `version`
- Type validation: `seed` is int, `window` is positive int, `version` is non-empty string

**Data Validation**
- File existence and non-empty check
- Valid CSV format
- Contains required `close` column
- `close` column is numeric (with automatic coercion via `pd.to_numeric()`)
- At least one data row present

### Error Output

**All errors are written to `metrics.json`** with `status="error"` and an actionable `error_message`. This ensures that orchestration systems always have structured output to parse, even in failure cases.

**Example errors**:
```json
{
  "version": "v1",
  "status": "error",
  "error_message": "Config file not found: config.yaml"
}
```

```json
{
  "version": "unknown",
  "status": "error",
  "error_message": "Input file is empty: data.csv"
}
```

The pipeline logs the full error to stderr (for immediate visibility) and exits with a non-zero code.

## Technical Decisions

### Why YAML for Configuration?

YAML is human-readable, version-controllable, and simple for basic key-value pairs. It avoids hard-coding parameters in source code and allows configuration to live alongside data in version control.

### Why pandas `rolling(window).mean()`?

Pandas rolling operations are:
- **Vectorized**: O(n) performance via C-level optimizations
- **Tested**: Used in production systems across industry
- **Flexible**: Easy to swap for other window functions (std, min, max)
- **Clear semantics**: `min_periods=window` explicitly handles edge cases

### Why Deterministic Seed?

Setting `np.random.seed(config['seed'])` ensures:
- **Reproducibility**: Identical results across runs (critical for debugging, auditing, testing)
- **Future-proof**: Any future stochastic step (sampling, augmentation) will be deterministic
- **Compliance**: Required for some regulated use cases (finance, healthcare)

The seed is included in metrics output, making it trivial to re-run with the same seed if needed.

### Why Structured JSON Metrics?

Machine-readable output enables:
- **Programmatic parsing** by orchestration systems (Airflow, Step Functions, etc.)
- **Monitoring integration** with Prometheus, DataDog, CloudWatch
- **Consistent schema** for success and error cases
- **Latency tracking** and performance analytics

### Why Dual-Channel Logging?

Logging to both file and stderr provides:
- **Real-time visibility** (stderr, viewable during execution)
- **Persistent audit trail** (file, retained after execution)
- **Observability** at different phases: development (stderr), production (file + centralized logging)

### Why python:3.9-slim?

Trade-offs:
- **Slim variant**: ~165MB (vs. ~900MB for full image) — faster pulls, smaller deployments
- **Python 3.9**: Stable, widely supported, sufficient for data engineering workloads
- **Debian-based**: Standard system utilities available if needed

### Why No Hard-Coded Paths?

All paths passed via CLI arguments allows:
- **Flexibility**: Script works from any working directory
- **Testability**: Easy to run with different input/output paths
- **Containerization**: Same script works in Docker, CI/CD, cloud environments

### Why NaN Handling as Signal=0?

Rolling mean produces NaN for the first (window-1) rows (insufficient history). Rather than skip these rows or propagate NaN, we deterministically set signal=0:
- **Consistency**: Leading rows are included in metrics (rows_processed includes them)
- **Predictability**: Same config + data always yields same signal_rate
- **Documentation**: Behavior is logged and explained in code comments

## Tech Stack

| Technology | Version | Purpose |
|---|---|---|
| Python | 3.9+ | Language |
| pandas | ≥2.2.3 | DataFrame operations, CSV parsing, rolling window |
| numpy | ≥2.0 | RNG, array operations |
| PyYAML | ≥6.0.2 | YAML parsing |
| Docker | latest | Containerization |
| Logging | stdlib | Structured logging |
| JSON | stdlib | Metrics serialization |

## Future Improvements

These enhancements are realistic and additive:

- **Unit tests** — Pytest suite covering config validation, data loading, signal generation, error cases
- **CI/CD** — GitHub Actions or similar for test automation, Docker image building
- **Configurable signal strategies** — Pluggable signal generators (multiple moving averages, momentum, volatility)
- **Multiple indicators** — Compute additional metrics (Sharpe ratio, max drawdown, volatility)
- **Cloud object storage** — S3/GCS integration for input/output
- **Orchestration templates** — Example Airflow DAG, Step Functions definition
- **Streaming support** — Adapter for Kafka/Kinesis for real-time signal generation
- **Benchmarking** — Performance tracking across dataset sizes and window configurations

## License

MIT
