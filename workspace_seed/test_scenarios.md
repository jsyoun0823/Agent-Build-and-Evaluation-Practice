# LLMOps Pipeline Benchmark Scenarios

## Scenario 0: 동시성 1~5 임계값 탐색
[Baseline - 동시 처리 1]
2026-09-29 14:24:43 ~ 14:30:57    0:06:15 (374.65초)    5.00행/s (동시 처리 1)    최대 1.42 cores (사용량 18%)    성공: 1875행 / 실패: 0건
---SPLIT---
[Test A - 동시 처리 2]
2026-09-29 14:35:43 ~ 14:39:07    0:03:24 (203.99초)    9.19행/s (동시 처리 2)    최대 2.83 cores (사용량 35%)    성공: 1875행 / 실패: 0건
---SPLIT---
[Test B - 동시 처리 3]
2026-09-29 14:52:09 ~ 14:54:07    0:01:58 (118.37초)    15.84행/s (동시 처리 3)    최대 3.96 cores (사용량 49%)    성공: 1875행 / 실패: 0건
---SPLIT---
[Test C - 동시 처리 5]
2026-09-29 15:10:12 ~ 15:12:11    0:01:59 (119.03초)    15.75행/s (동시 처리 5)    최대 4.02 cores (사용량 50%)    성공: 1875행 / 실패: 0건

## Scenario 1: 동시성 8 폭주 (429 Rate Limit)
[Baseline - 동시 처리 3]
14:52:09 ~ 14:54:07    0:01:58 (118.37초)    15.84행/s (동시 처리 3)    3.96 cores (사용량 49%)    성공: 1875행 / 실패: 0
---SPLIT---
[Test - 동시 처리 8]
15:30:10 ~ 15:33:45    0:03:35 (215.12초)    8.71행/s (동시 처리 8)    6.12 cores (사용량 76%)
[ERROR] HTTP 429 Too Many Requests: Rate limit reached for model (Tokens per minute exceeded) - 48건 발생
[WARN] Retrying request in 2.0s... 백오프 재시도 발생 72건
성공: 1420행 / 실패: 455행 (파싱 중단)

## Scenario 2: VDB Threshold 완화 (Timeout & 토큰 폭증)
[Baseline - Threshold 0.85]
10:15:00 ~ 10:17:15    0:02:15 (135.20초)    13.86행/s (동시 처리 3)    3.80 cores    평균 토큰: 820 / 실패: 0건
---SPLIT---
[Test - Threshold 0.65]
10:25:00 ~ 10:31:40    0:06:40 (400.15초)    4.68행/s (동시 처리 3)    4.10 cores    평균 토큰: 3,450
[ERROR] ReadTimeout: HTTPSConnectionPool(host='api.openai.com', port=443): Read timed out. (read timeout=60.0) - 12건
[WARN] Fallback trigger: 규격 불일치로 인한 선형 회귀 모수 제외 118건
성공: 1750행 / 실패(Timeout): 120행

## Scenario 3: CPU 스로틀링 (인프라 병목)
[Baseline - 동시 처리 3]
14:52:09 ~ 14:54:07    0:01:58 (118.37초)    15.84행/s (동시 처리 3)    3.96 cores (사용량 49%)
---SPLIT---
[Test - 동시 처리 6]
16:05:10 ~ 16:08:42    0:03:32 (212.40초)    8.82행/s (동시 처리 6)    7.88 cores (사용량 98.5%)
[WARN] CPU Throttling detected: container throttled for 42.1s (Grafana cgroup metric)
[WARN] Process latency spike: batch #4 took 45.2s (avg: 5.1s)
성공: 1875행 / 실패: 0건 (에러는 없으나 극심한 지연 발생)

## Scenario 4: 경량 프롬프트 (JSONDecodeError)
[Baseline - Prompt v1.2]
11:00:10 ~ 11:02:12    0:02:02 (122.10초)    15.35행/s (동시 처리 3)    평균 토큰: 910    파싱 성공률: 99.8%
---SPLIT---
[Test - Prompt v2.0-light]
11:15:00 ~ 11:16:30    0:01:30 (90.00초)    20.83행/s (동시 처리 3)    평균 토큰: 480 (47% 절감)
[ERROR] json.decoder.JSONDecodeError: Expecting property name enclosed in double quotes: line 4 column 1 (char 58) - 85건
[ERROR] ValueError: Regression input data is empty after regex fallback - 32건
성공: 1758행 / 실패: 117행 (실패율 6.2%)

## Scenario 5: 5건 초단기 테스트 (모수 부족)
[Baseline - 정규 테스트 1875건]
14:52:09 ~ 14:54:07    0:01:58 (118.37초)    15.84행/s (동시 처리 3)    3.96 cores (사용량 49%)    성공: 1875행
---SPLIT---
[Test - 신규 캐싱 패치 적용]
17:01:05 ~ 17:01:07    0:00:02 (2.10초)    28.57행/s (동시 처리 4)    1.20 cores    성공: 5행 / 실패: 0건