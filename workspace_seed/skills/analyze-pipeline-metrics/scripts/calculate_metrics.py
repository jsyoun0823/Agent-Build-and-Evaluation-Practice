#!/usr/bin/env python3
"""Aggregate parsed pipeline metrics and calculate A/B percentage changes."""

import argparse
import json
import math
import sys


def as_numbers(values):
    numbers = []
    for value in values or []:
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            numbers.append(number)
    return numbers


def percentile(values, quantile):
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def aggregate(data):
    latencies = as_numbers(data.get("latency_list"))
    tokens = as_numbers(data.get("token_list"))
    errors = data.get("errors") or {}
    total_errors = int(errors.get("429", 0)) + int(errors.get("timeout", 0)) + int(errors.get("other", 0))
    success_count = int(data.get("successful_count", 0))
    failed_count = int(data.get("failed_count", 0))
    status_count = success_count + failed_count
    return {
        "total_count": int(data.get("total_count", 0)),
        "average_latency_ms": sum(latencies) / len(latencies) if latencies else None,
        "p95_latency_ms": percentile(latencies, 0.95),
        "average_tokens": sum(tokens) / len(tokens) if tokens else None,
        "total_tokens": sum(tokens) if tokens else None,
        "success_rate_percent": success_count * 100 / status_count if status_count else None,
        "successful_count": success_count,
        "failed_count": failed_count,
        "total_errors": total_errors,
        "errors": errors,
        "latency_sample_count": len(latencies),
        "token_sample_count": len(tokens),
    }


def percentage_change(baseline, experiment):
    if baseline is None or experiment is None or baseline == 0:
        return {"value": None, "formatted": "N/A"}
    value = (experiment - baseline) / baseline * 100
    return {"value": value, "formatted": f"{value:+.1f}%"}


def calculate(control, experiment):
    control_metrics = aggregate(control)
    experiment_metrics = aggregate(experiment)
    comparable_metrics = (
        "average_latency_ms",
        "p95_latency_ms",
        "average_tokens",
        "total_tokens",
        "success_rate_percent",
    )
    changes = {
        key: percentage_change(control_metrics[key], experiment_metrics[key])
        for key in comparable_metrics
    }
    return {"control": control_metrics, "experiment": experiment_metrics, "changes": changes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control-json", help="대조군 파싱 JSON 문자열")
    parser.add_argument("--experiment-json", help="실험군 파싱 JSON 문자열")
    args = parser.parse_args()
    if args.control_json is not None or args.experiment_json is not None:
        if args.control_json is None or args.experiment_json is None:
            parser.error("--control-json과 --experiment-json을 함께 지정해야 합니다.")
        payload = {"control": json.loads(args.control_json), "experiment": json.loads(args.experiment_json)}
    else:
        payload = json.load(sys.stdin)
    result = calculate(payload["control"], payload["experiment"])
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()