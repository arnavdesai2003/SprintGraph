# Measured local demo evaluation

On 2026-10-11, a user-run evaluation processed 400 synthetic events through the Docker/PostgreSQL demo stack. The evaluator used deterministic demo adapters and a mock LLM. These are observed local measurements, not production LLM performance or historical productivity savings.

| Measurement | Result |
| --- | ---: |
| Events | 400 |
| Successful / failed / unfinished | 400 / 0 / 0 |
| Execution attempts | 400 |
| Each of the four workflows | 100 successful events |
| Wall duration | 2.565 seconds |
| Throughput | 155.97 events/second |
| P50 end-to-end latency | 1,264.806 ms |
| P95 end-to-end latency | 2,240.853 ms |

Run ID: `evaluation-1b4a3454-c554-4572-8860-d0eefc8f106a`. Runtime: Python 3.12.15, Linux aarch64. Fixture reference date: 2026-10-11. The local `evaluation-report.json` contains source SHA-256 hashes, non-secret scoring configuration and metric definitions; its hashes were verified against the current source files after the run.

Latency is ingestion to final completion, including queue wait and retries. Percentiles use nearest rank. Throughput divides all terminal events by wall time from enqueue start to completion. One worker processes the batch; the ordinary background worker is paused and restarted by the wrapper. All fixtures use automated handling. A successful automation fraction of 1.0 means all synthetic automated events succeeded; no manually handled baseline or engineering time saving was measured.

The database contains previous demonstration records, so this is a measured run on the existing local demo database, not an isolated load test. Do not extrapolate this throughput to live providers, different hardware, large payloads or concurrent workers. No claim of 41% automation across 537+ historical events is established.

## Repeat

```sh
python3 scripts/run_evaluation.py --events 400
```

The script saves the new measured report to `evaluation-report.json`, adding a new batch without consuming unrelated pending events. For comparisons, retain each report under a distinct filename with `--output`, record the database state and hardware, and compare source hashes/configuration. Synthetic source fixtures and deterministic model outputs are versioned in the repository. Provider behavior, database state and environment changes affect timings.
