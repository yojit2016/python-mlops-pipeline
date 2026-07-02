#!/usr/bin/env python3
"""
run.py — Minimal MLOps-style batch job.

Loads a YAML config, reads an OHLCV CSV, computes a rolling mean on `close`,
derives a binary signal (close > rolling_mean), and writes structured
metrics (metrics.json) plus detailed logs (run.log).

Usage:
    python run.py --input data.csv --config config.yaml --output metrics.json --log-file run.log

Design notes (determinism & NaN handling):
  - numpy's RNG is seeded from config['seed'] for full reproducibility, even
    though this pipeline doesn't currently use randomness directly — this
    guarantees any future stochastic step is deterministic too.
  - Rolling mean uses pandas .rolling(window).mean() with the default
    min_periods=window, so the first (window - 1) rows have no rolling mean
    (NaN) because there isn't enough history yet.
  - For those leading NaN rows, the signal is deterministically set to 0
    (not "close > rolling_mean", since that comparison is undefined). This
    is applied consistently and is reflected in the logs.
  - rows_processed and signal_rate are computed over ALL rows (including the
    leading NaN-window rows), so re-running with the same input/config
    always yields the exact same rows_processed, signal_rate, and seed.
    latency_ms will naturally vary run to run since it measures wall-clock
    runtime, not the deterministic outputs.
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

REQUIRED_CONFIG_KEYS = ("seed", "window", "version")
REQUIRED_COLUMN = "close"


def parse_args():
    parser = argparse.ArgumentParser(description="Rolling-mean signal batch job")
    parser.add_argument("--input", required=True, help="Path to input OHLCV CSV")
    parser.add_argument("--config", required=True, help="Path to YAML config file")
    parser.add_argument("--output", required=True, help="Path to write metrics JSON")
    parser.add_argument("--log-file", required=True, help="Path to write log file")
    return parser.parse_args()


def setup_logging(log_file: str) -> logging.Logger:
    logger = logging.getLogger("mlops_task")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    file_handler = logging.FileHandler(log_file, mode="w")
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setFormatter(fmt)
    logger.addHandler(stream_handler)

    return logger


def write_metrics(output_path: str, payload: dict, logger: logging.Logger) -> None:
    with open(output_path, "w") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    logger.info(f"Metrics written to {output_path}")


def load_and_validate_config(config_path: str, logger: logging.Logger) -> dict:
    path = Path(config_path)
    if not path.exists():
        raise ValueError(f"Config file not found: {config_path}")
    if path.stat().st_size == 0:
        raise ValueError(f"Config file is empty: {config_path}")

    try:
        with open(path, "r") as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Config file is not valid YAML: {e}")

    if not isinstance(config, dict):
        raise ValueError("Config file must contain a top-level YAML mapping (key: value pairs)")

    missing = [k for k in REQUIRED_CONFIG_KEYS if k not in config]
    if missing:
        raise ValueError(f"Config is missing required field(s): {missing}")

    if not isinstance(config["seed"], int):
        raise ValueError(f"Config field 'seed' must be an integer, got {type(config['seed']).__name__}")
    if not isinstance(config["window"], int) or config["window"] < 1:
        raise ValueError(f"Config field 'window' must be a positive integer, got {config['window']!r}")
    if not isinstance(config["version"], str) or not config["version"]:
        raise ValueError(f"Config field 'version' must be a non-empty string, got {config['version']!r}")

    logger.info(
        f"Config loaded + validated: seed={config['seed']}, "
        f"window={config['window']}, version={config['version']}"
    )
    return config


def load_and_validate_dataset(input_path: str, logger: logging.Logger) -> pd.DataFrame:
    path = Path(input_path)
    if not path.exists():
        raise ValueError(f"Input file not found: {input_path}")
    if path.stat().st_size == 0:
        raise ValueError(f"Input file is empty: {input_path}")

    try:
        df = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        raise ValueError(f"Input file has no parseable data: {input_path}")
    except pd.errors.ParserError as e:
        raise ValueError(f"Input file is not a valid CSV: {e}")

    if df.empty:
        raise ValueError(f"Input file contains no data rows: {input_path}")

    if REQUIRED_COLUMN not in df.columns:
        raise ValueError(
            f"Input CSV is missing required column '{REQUIRED_COLUMN}'. "
            f"Found columns: {list(df.columns)}"
        )

    if not pd.api.types.is_numeric_dtype(df[REQUIRED_COLUMN]):
        df[REQUIRED_COLUMN] = pd.to_numeric(df[REQUIRED_COLUMN], errors="coerce")
        if df[REQUIRED_COLUMN].isna().all():
            raise ValueError(f"Column '{REQUIRED_COLUMN}' contains no valid numeric values")

    logger.info(f"Rows loaded: {len(df)} from {input_path}")
    return df


def compute_signal(df: pd.DataFrame, window: int, logger: logging.Logger) -> pd.DataFrame:
    df = df.copy()
    df["rolling_mean"] = df[REQUIRED_COLUMN].rolling(window=window, min_periods=window).mean()
    logger.info(f"Rolling mean computed on '{REQUIRED_COLUMN}' with window={window}")

    # Leading rows without enough history for a full window get signal = 0
    # (deterministic, documented convention — see module docstring).
    df["signal"] = np.where(df["rolling_mean"].notna() & (df[REQUIRED_COLUMN] > df["rolling_mean"]), 1, 0)
    n_leading_nan = int(df["rolling_mean"].isna().sum())
    logger.info(
        f"Signal generated: {int(df['signal'].sum())} positive signals out of {len(df)} rows "
        f"({n_leading_nan} leading rows had insufficient history for window={window} and were set to signal=0)"
    )
    return df


def main():
    args = parse_args()
    logger = setup_logging(args.log_file)
    start_time = time.perf_counter()
    version_for_error = "unknown"

    logger.info("=" * 60)
    logger.info("Job start")
    logger.info(
        f"Args: input={args.input}, config={args.config}, "
        f"output={args.output}, log_file={args.log_file}"
    )

    try:
        config = load_and_validate_config(args.config, logger)
        version_for_error = config.get("version", "unknown")

        np.random.seed(config["seed"])
        logger.info(f"Random seed set: {config['seed']}")

        df = load_and_validate_dataset(args.input, logger)
        df = compute_signal(df, config["window"], logger)

        rows_processed = int(len(df))
        signal_rate = float(df["signal"].mean())
        latency_ms = int(round((time.perf_counter() - start_time) * 1000))

        metrics = {
            "version": config["version"],
            "rows_processed": rows_processed,
            "metric": "signal_rate",
            "value": round(signal_rate, 4),
            "latency_ms": latency_ms,
            "seed": config["seed"],
            "status": "success",
        }

        logger.info(
            f"Metrics summary: rows_processed={rows_processed}, "
            f"signal_rate={metrics['value']}, latency_ms={latency_ms}"
        )
        write_metrics(args.output, metrics, logger)
        logger.info("Job end | status=success")
        print(json.dumps(metrics, indent=2))
        sys.exit(0)

    except Exception as e:
        latency_ms = int(round((time.perf_counter() - start_time) * 1000))
        error_metrics = {
            "version": version_for_error,
            "status": "error",
            "error_message": str(e),
        }
        logger.exception(f"Job failed: {e}")
        try:
            write_metrics(args.output, error_metrics, logger)
        except Exception as write_err:
            logger.error(f"Additionally failed to write metrics file: {write_err}")
        logger.info("Job end | status=error")
        print(json.dumps(error_metrics, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
