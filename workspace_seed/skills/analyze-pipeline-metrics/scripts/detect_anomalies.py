#!/usr/bin/env python3
"""Detect pipeline errors, latency spikes, tradeoffs, and small samples."""

import argparse
import json
import sys


def median(values):
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def find_latency_spikes(values, factor):
    numeric = [(index, float(value)) for index, value in enumerate(values or [])]
    if len(numeric) < 3:
        return []
    center = median([value for _, value in numeric])
    deviations = [abs(value - center) for _, value in numeric]
    mad = median(deviations)
    threshold = center + factor * mad if mad else center * factor
    return [{"index": index, "latency_ms": value, "threshold_ms": threshold}
            for index, value in numeric if value > threshold]


def detect(metrics, control_data=None, experiment_data=None, min_sample=10, spike_factor=3.0):
    control = metrics["control"]
    experiment = metrics["experiment"]
    control_errors = control.get("errors") or {}
    experiment_errors = experiment.get("errors") or {}

    has_429 = int(control_errors.get("429", 0)) > 0 or int(experiment_errors.get("429", 0)) > 0
    has_timeout = any(
        int(errors.get(key, 0)) > 0
        for errors in (control_errors, experiment_errors)
        for key in ("504", "timeout")
    )
    speed_change = (metrics.get("changes", {}).get("average_latency_ms") or {}).get("value")
    token_change = (metrics.get("changes", {}).get("average_tokens") or {}).get("value")
    speed_improved = speed_change is not None and speed_change < 0
    token_surge = token_change is not None and token_change >= 30
    errors_increased = int(experiment.get("total_errors", 0)) > int(control.get("total_errors", 0))

    sample_counts = {
        "control": int(control.get("total_count", 0)),
        "experiment": int(experiment.get("total_count", 0)),
    }
    low_sample_groups = [name for name, count in sample_counts.items() if count < min_sample]
    spike_results = {}
    if control_data is not None:
        spike_results["control"] = find_latency_spikes(control_data.get("latency_list", []), spike_factor)
    if experiment_data is not None:
        spike_results["experiment"] = find_latency_spikes(experiment_data.get("latency_list", []), spike_factor)

    result = {
        "rate_limit_warning": has_429,
        "timeout_warning": has_timeout,
        "critical_error_warning": has_429 or has_timeout,
        "latency_spike_warning": any(spike_results.values()),
        "latency_spikes": spike_results,
        "tradeoff_warning": speed_improved and (token_surge or errors_increased),
        "tradeoff_details": {
            "speed_improved": speed_improved,
            "average_tokens_increased_by_at_least_30_percent": token_surge,
            "errors_increased": errors_increased,
        },
        "low_sample_warning": bool(low_sample_groups),
        "sample_counts": sample_counts,
        "low_sample_groups": low_sample_groups,
        "minimum_sample_count": min_sample,
    }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metrics-json", help="계산 결과 JSON 문자열. 생략 시 stdin에서 읽음")
    parser.add_argument("--control-json", help="대조군 파싱 JSON 문자열 (지연 스파이크 검사)")
    parser.add_argument("--experiment-json", help="실험군 파싱 JSON 문자열 (지연 스파이크 검사)")
    parser.add_argument("--min-sample", type=int, default=10)
    parser.add_argument("--spike-factor", type=float, default=3.0)
    args = parser.parse_args()
    metrics = json.loads(args.metrics_json) if args.metrics_json is not None else json.load(sys.stdin)
    control_data = json.loads(args.control_json) if args.control_json is not None else None
    experiment_data = json.loads(args.experiment_json) if args.experiment_json is not None else None
    if (control_data is None) != (experiment_data is None):
        parser.error("지연 스파이크 검사를 위해서는 두 파싱 JSON을 모두 전달해야 합니다.")
    result = detect(metrics, control_data, experiment_data, args.min_sample, args.spike_factor)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()