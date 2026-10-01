#!/usr/bin/env python3
"""Parse pasted pipeline logs or Grafana TSV/CSV into normalized JSON."""

import argparse
import csv
import io
import json
import re
import sys


NUMBER = r"(?:\d[\d,]*(?:\.\d+)?|\.\d+)"
LATENCY_PATTERN = re.compile(
    rf"(?:execution\s*time|latency|duration)\s*[=:]?\s*({NUMBER})\s*(ms|msec|milliseconds?|s|sec|seconds?)?\b",
    re.IGNORECASE,
)
TOKEN_PATTERN = re.compile(rf"(?:total\s+)?tokens?\s*[=:]?\s*({NUMBER})\b", re.IGNORECASE)
STATUS_PATTERN = re.compile(r"\bstatus\s*[=:]?\s*(\d{3})(?:\s+([^\r\n,]+))?", re.IGNORECASE)
HTTP_PATTERN = re.compile(r"\bHTTP\s+(\d{3})\b(?:\s+([^\r\n,]+))?", re.IGNORECASE)
ERROR_CODE_PATTERN = re.compile(r"\b(?:error\s*code|error_code)\s*[=:]\s*(\d{3})\b", re.IGNORECASE)
TIMEOUT_PATTERN = re.compile(r"\btime(?:d\s*out|out)\b|\btimeout\b", re.IGNORECASE)

LATENCY_HEADERS = {"latency", "latencyms", "duration", "executiontime"}
TOKEN_HEADERS = {"token", "tokens", "tokencount", "totaltokens"}
STATUS_HEADERS = {"status", "httpstatus", "statuscode"}
ERROR_RATE_HEADERS = {"errorrate", "errorsrate"}


def number_value(value):
    match = re.search(NUMBER, str(value))
    return float(match.group(0).replace(",", "")) if match else None


def latency_ms(value, default_unit="ms"):
    match = re.search(rf"({NUMBER})\s*(ms|msec|milliseconds?|s|sec|seconds?)?\b", str(value), re.IGNORECASE)
    if not match:
        return None
    amount = float(match.group(1).replace(",", ""))
    unit = (match.group(2) or default_unit).lower()
    return amount * 1000 if unit.startswith("s") else amount


def header_kind(header):
    normalized = re.sub(r"[^a-z0-9]", "", header.lower())
    if normalized in LATENCY_HEADERS:
        return "latency"
    if normalized in TOKEN_HEADERS:
        return "tokens"
    if normalized in STATUS_HEADERS:
        return "status"
    if normalized in ERROR_RATE_HEADERS:
        return "error_rate"
    if normalized == "time":
        return "time"
    return None


def empty_result():
    return {
        "latency_list": [],
        "token_list": [],
        "total_count": 0,
        "errors": {"429": 0, "504": 0, "timeout": 0, "other": 0},
        "successful_count": 0,
        "failed_count": 0,
        "error_rate_list": [],
        "time_list": [],
        "parsed_count": 0,
        "skipped_count": 0,
    }


def add_status(result, status_code, text=""):
    if status_code is None:
        return
    code = int(status_code)
    if 200 <= code < 300:
        result["successful_count"] += 1
    elif code >= 400:
        result["failed_count"] += 1
    if code == 429:
        result["errors"]["429"] += 1
    elif code == 504:
        result["errors"]["504"] += 1
        result["errors"]["timeout"] += 1
    elif code >= 400:
        result["errors"]["other"] += 1
    elif TIMEOUT_PATTERN.search(text):
        result["errors"]["timeout"] += 1
        result["failed_count"] += 1


def parse_log(text):
    result = empty_result()
    for line in text.splitlines():
        if not line.strip():
            continue
        found = False
        latency_match = LATENCY_PATTERN.search(line)
        if latency_match:
            value = latency_ms(latency_match.group(0), default_unit="ms")
            if value is not None:
                result["latency_list"].append(value)
                found = True
        token_match = TOKEN_PATTERN.search(line)
        if token_match:
            result["token_list"].append(float(token_match.group(1).replace(",", "")))
            found = True

        status_match = STATUS_PATTERN.search(line) or HTTP_PATTERN.search(line) or ERROR_CODE_PATTERN.search(line)
        if status_match:
            add_status(result, status_match.group(1), status_match.group(2) if status_match.lastindex and status_match.lastindex >= 2 else line)
            found = True
        elif TIMEOUT_PATTERN.search(line):
            result["errors"]["timeout"] += 1
            result["failed_count"] += 1
            found = True
        elif re.search(r"\berror\b|\bexception\b|\bfail(?:ed|ure)?\b", line, re.IGNORECASE):
            result["errors"]["other"] += 1
            result["failed_count"] += 1
            found = True

        if found:
            result["parsed_count"] += 1
        else:
            result["skipped_count"] += 1
    result["total_count"] = result["parsed_count"]
    return result


def parse_delimited(text, delimiter):
    result = empty_result()
    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    rows = [row for row in rows if any(cell.strip() for cell in row)]
    if not rows:
        return result

    kinds = [header_kind(cell.strip()) for cell in rows[0]]
    has_header = any(kind is not None for kind in kinds)
    data_rows = rows[1:] if has_header else rows
    if not has_header:
        result["skipped_count"] += 1
        return result

    for row in data_rows:
        record = False
        for index, kind in enumerate(kinds):
            if kind is None or index >= len(row):
                continue
            value = row[index].strip()
            if not value:
                continue
            if kind == "latency":
                parsed = latency_ms(value)
                if parsed is not None:
                    result["latency_list"].append(parsed)
                    record = True
            elif kind == "tokens":
                parsed = number_value(value)
                if parsed is not None:
                    result["token_list"].append(parsed)
                    record = True
            elif kind == "error_rate":
                parsed = number_value(value)
                if parsed is not None:
                    result["error_rate_list"].append(parsed)
                    record = True
            elif kind == "time":
                result["time_list"].append(value)
                record = True
            elif kind == "status":
                status_match = re.search(r"\b(\d{3})\b", value)
                if status_match:
                    add_status(result, status_match.group(1), value)
                    record = True
                elif re.search(r"\bsuccess\b|\bok\b", value, re.IGNORECASE):
                    result["successful_count"] += 1
                    record = True
                elif re.search(r"\berror\b|\bfail|\btimeout\b", value, re.IGNORECASE):
                    result["failed_count"] += 1
                    result["errors"]["timeout" if TIMEOUT_PATTERN.search(value) else "other"] += 1
                    record = True
        if record:
            result["parsed_count"] += 1
        else:
            result["skipped_count"] += 1

    result["total_count"] = result["parsed_count"]
    return result


def parse_text(text):
    first_line = next((line for line in text.splitlines() if line.strip()), "")
    delimiter = "\t" if "\t" in first_line else "," if "," in first_line else None
    if delimiter:
        parsed = parse_delimited(text, delimiter)
        if parsed["parsed_count"] or parsed["skipped_count"]:
            return parsed
    return parse_log(text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", help="원문 텍스트. 생략하면 stdin에서 읽습니다.")
    args = parser.parse_args()
    text = args.text if args.text is not None else sys.stdin.read()
    result = parse_text(text)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()