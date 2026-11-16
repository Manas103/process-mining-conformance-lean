# Insider Risk Program Reporting: Workload, Cycle Time, Detection Performance (extension)

Re-points the base repo's per-case stage-decomposition engine at an
insider-risk case lifecycle instead of order fulfillment: a 120,000-event,
20,000-case synthetic insider-risk log, decomposed into per-stage cycle time
from intake (Referral Received) to disposition (Disposition Decided), scored
per detection rule, and served only as small-cell-suppressed aggregates. Every
number below was measured on this machine, not targeted; where a design
target existed (the bottleneck's share of median cycle time), the measured
value is reported honestly even where it differs from that target.

## Why this exists

A program report built once from a spreadsheet goes stale the moment the
case mix shifts; this is a small version of the alternative, a reporting
layer computed directly from the case log, re-pointing the base repo's
already-validated stage-decomposition engine at a different domain rather
than rebuilding the same mechanism from scratch for a new one. The engine
(DuckDB per-case decomposition, diffed exactly against an independent
pure-Python oracle) is the base repo's own methodology; what's new here is
the insider-risk case lifecycle it's applied to, per-rule detection
performance scoring, and a reporting layer that never returns a count small
enough to re-identify a case.

## Honest framing, up front

- **Extension, not a new repo.** This directory re-points the base repo's
  stage-decomposition engine at a different case lifecycle; the base repo's
  own order-fulfillment claims (discovery, conformance, the dispatch-redesign
  simulation) are untouched by anything in here and are not re-verified by
  this extension.
- **Synthetic data throughout.** The 6-stage case lifecycle, the 6 detection
  rules and their substantiation rates, the 20-analyst pool and the handoff
  timing model are all invented for this extension
  (`insider_risk/src/ir/ir_reference.py`); no real insider-risk program's case
  log is behind any number here.
- **A directly-follows stage model, not a conformance checker.** Every
  synthetic case here walks the same 6-stage sequence exactly; unlike the base
  repo, this extension does not seed or detect process deviations, because
  its claims are about cycle time, detection performance and privacy-
  preserving reporting, not conformance.
- **The suppression and re-identification-blocking claims are about
  aggregate counts, not row-level access control.** `ir_reporting.py` never
  exposes an individual case; the only thing it can leak is a count, and the
  one property measured here is that a count small enough to narrow a cell
  down toward a single case is never returned.
- **Grafana is a committed dashboard JSON, not a running Grafana instance.**
  `grafana/insider_risk_dashboard.json` documents the 4 panels this reporting
  layer would back; it is not deployed or screenshotted against a live
  datasource.
- **Machine and toolchain.** Windows 11, 8 physical / 16 logical cores.
  Python 3.12.10, pandas 3.0.5, DuckDB 1.5.5, NumPy 2.5.3, pytest 9.1.1, in a
  per-extension `.venv`, reusing the base repo's `src/pm/db.py` unmodified.

## Architecture

```
insider_risk/
├── src/ir/
│   ├── ir_reference.py   the case lifecycle (6 stages), the 6 detection
│   │                     rules and their substantiation rates, the
│   │                     20-analyst pool, the handoff timing model (the
│   │                     Triage Completed -> Investigation Opened backlog
│   │                     is the seeded bottleneck), SUPPRESSION_THRESHOLD
│   ├── ir_generator.py    builds the 120,000-event log: 20,000 cases x 6
│   │                     stages, each case tagged with a detection rule,
│   │                     an analyst, a ground-truth substantiation outcome
│   │                     and a referral date
│   ├── ir_cycle_time.py   per-case handoff decomposition (reuses the base
│   │                     repo's pm.db unmodified; stage order here is
│   │                     looked up by activity name, not by timestamp
│   │                     order, see Findings) and bottleneck location
│   ├── ir_oracle.py       an independent, pure-Python reference for the
│   │                     same decomposition, diffed exactly against it
│   ├── ir_detection.py    per-rule fired / substantiated / substantiation
│   │                     rate
│   └── ir_reporting.py    aggregate_count (suppresses any cell under
│                         SUPPRESSION_THRESHOLD=5 cases) and
│                         seed_reidentification_queries (picks real,
│                         genuinely small (rule, analyst, day) cells to
│                         attack)
├── scripts/
│   ├── generate_log.py       regenerates data/case_log.csv, case_meta.csv
│   └── run_benchmarks.py     runs all 5 claims end to end ->
│                             docs/benchmark_output.txt
├── tests/
│   ├── conftest.py                session-scoped 120,000-event case log,
│   │                             loaded into DuckDB via the base repo's
│   │                             pm.db
│   ├── test_cycle_time.py         claims: 120,000 events decomposed, the
│   │                             conservation identity, the oracle diff,
│   │                             the bottleneck location
│   ├── test_detection.py          claim: all 6 rules scored
│   └── test_reporting.py          claims: small-cell suppression, 40/40
│                                 re-identification queries blocked
└── grafana/insider_risk_dashboard.json   4 panels this layer backs
```

### Design deep-dives

**Stage order is looked up by activity name, not by timestamp order.**
The base repo's own `conformance.py` sorts each case's events by
`(timestamp, event_id)` because it has to tolerate seeded deviations where
the true activity order isn't known in advance. Every case in this extension
follows the documented 6-stage sequence exactly (no deviations are seeded
here), so `ir_cycle_time.decompose` pivots on activity name directly
(`MAX(CASE WHEN activity = '<stage>' THEN timestamp END)`), which sidesteps
the base repo's own timestamp-tie-break finding by construction rather than
by reproducing its fix. See Findings for why this distinction mattered while
writing this extension's tests.

**The bottleneck is sized as a mean, not post-hoc tuned to a share.**
`HANDOFF_GAMMA_PARAMS_MINUTES` sets the Triage Completed -> Investigation
Opened backlog's mean to equal the sum of the other 4 handoffs' means, a
50% design target for its share of total mean cycle time, written once before
any measurement. The measured share of *median* cycle time (47.9%, see
Measured results) differs from that target because gamma-distributed waits
are right-skewed, so summing 5 of them shifts the total's median away from
the sum of the individual medians; the model was not retuned after this was
observed.

**Re-identification queries are real small cells, not synthetic edge
cases.** `seed_reidentification_queries` draws its 40 queries from
`all_cells`, the actual (detection_rule, analyst, referral_date) combinations
present in the generated log that happen to cover 1 to 4 real cases, not from
a separately constructed adversarial list. A query that this reporting layer
failed to recognize as small would be a real information leak in this
dataset, not a contrived one.

## Validation

1. **120,000 events across 20,000 cases**, 6 stages each.
2. **The per-case handoff decomposition sums exactly to total cycle time**
   (a conservation identity, to floating-point precision).
3. **The real DuckDB engine against an independent, pure-Python oracle**,
   over the full 20,000-case population, exact agreement on all 5 handoffs
   and the total.
4. **The bottleneck handoff is located** (Triage Completed -> Investigation
   Opened) and its measured share of median cycle time reported.
5. **All 6 detection rules scored** with a non-degenerate substantiation
   rate.
6. **Every cell under 5 cases suppressed, every cell at or above 5 cases
   served with its real count** (13,049 and 62 cells respectively,
   measured over the full (detection_rule, analyst, referral_date) grouping).
7. **40 of 40 real, seeded re-identification queries blocked.**

```
tests/test_cycle_time.py::test_120000_events_across_20000_cases PASSED
tests/test_cycle_time.py::test_per_case_decomposition_sums_exactly_to_total_cycle_time PASSED
tests/test_cycle_time.py::test_real_engine_agrees_with_independent_pure_python_oracle PASSED
tests/test_cycle_time.py::test_bottleneck_handoff_is_located PASSED
tests/test_detection.py::test_all_6_rules_scored PASSED
tests/test_reporting.py::test_all_small_cells_suppressed_and_large_cells_not PASSED
tests/test_reporting.py::test_40_of_40_reidentification_queries_blocked PASSED

7 passed in 43.37s
```
(full output: `docs/test_output.txt`; claim-by-claim summary: `docs/benchmark_output.txt`)

## Findings

**The base repo's event-ordering discipline turned out not to be needed
here, and confirming that took an actual check, not an assumption.** The
base repo's `conformance.py` exists because its seeded deviations mean a
case's true activity order can't be assumed from the data. This extension's
first draft of `ir_cycle_time.py` initially sorted by `(timestamp, event_id)`
out of habit, copying the base repo's pattern. Measured directly: every one
of the 20,000 generated cases' 6 stages has a strictly increasing `event_id`
and a strictly increasing timestamp in CASE_SEQUENCE order already, because
`ir_generator.py` never seeds a deviation, so the sort was dead code adding a
dependency on `event_id` this extension's own data never needs. It was
removed in favor of the conditional-aggregation pivot shown in the
Architecture section, which is both simpler and does not silently inherit a
tie-break assumption from a different problem.

## Measured results

Machine: Windows 11, 8 physical / 16 logical cores, Python 3.12.10, pandas
3.0.5, DuckDB 1.5.5, single process throughout.

| Claim | Measured | Meets claim |
|---|---|---|
| Decomposed a 120,000-event synthetic case log into per-stage cycle time from intake to disposition | **120,000** events across **20,000** cases; conservation identity max abs error **0.0** minutes; independent oracle cross-check **0** mismatches over 20,000 cases x 6 columns | Yes |
| Per-rule detection performance | **6 / 6** rules scored: DLP-BulkExfil 34.98% substantiated (5,963 fired), DLP-OffHoursUpload 19.71% (4,956), HR-Referral 57.28% (1,662), Anonymous-Tip 14.85% (970), Manager-Report 46.50% (1,314), Access-Anomaly 25.43% (5,135) | Yes |
| Located the slowest handoff at 50% of median cycle time | **Triage Completed -> Investigation Opened**, median 345.0 min, **47.9%** of median total cycle time. The design target was 50%; the measured share is close but not identical, reported as measured, not adjusted to match (see Findings/Design deep-dives for why gamma-distributed medians don't sum the way means do) | Bottleneck correctly located; measured share close to but not exactly the design target |
| Served only aggregates, suppressing cells under 5 cases | **13,049 of 13,049** cells under 5 cases suppressed; **62 of 62** cells at or above 5 cases served with their real count | Yes |
| Blocked 40 of 40 re-identification queries | **40 / 40** real, seeded small-cell queries blocked | Yes |

**The one number that matters is 13,049 of 13,049 paired with 62 of 62, not
either alone**: a reporting layer that suppressed everything would trivially
score 13,049/13,049 while being useless, and one that only checked the 40
seeded attack queries without also confirming every genuinely small cell in
the full population is caught would be a narrower claim than "served only
aggregates". Both were measured over the same exhaustive grouping
(`all_cells`), which is what makes the pairing meaningful.

## Building and running

```
cd process-mining-conformance-lean/insider_risk
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python.exe -m pytest tests -v -s      # docs/test_output.txt
.venv\Scripts\python.exe scripts\generate_log.py    # data/case_log.csv, data/case_meta.csv
.venv\Scripts\python.exe scripts\run_benchmarks.py  # docs/benchmark_output.txt
```

## Sibling comparison

The base repo ([process-mining-conformance-lean](https://github.com/Manas103/process-mining-conformance-lean))
is this extension's own sibling and the clearest contrast available: it
decomposes the same kind of per-case handoff cycle time, but over an
order-fulfillment process with 24 seeded conformance deviations it must
detect (24/24 caught) and a dispatch-redesign simulation validated against a
held-out replay (0.04 points off a within-4-point target). This extension
carries neither a conformance checker (see Design deep-dives for why its
case model doesn't need one) nor a redesign simulation; what it adds instead,
with no equivalent in the base repo, is per-rule detection-performance
scoring and a small-cell-suppressing reporting layer with a measured
re-identification-blocking guarantee (40/40).

## Limitations

- No process deviations are seeded or detected in this extension's case
  log; every one of the 20,000 cases follows the 6-stage sequence exactly.
  A program whose real case data has skipped or reordered stages would need
  the base repo's conformance-checking approach layered back in.
- The bottleneck-location percentage measured here (47.9%) is close to but
  not identical to this extension's own design target (50%); see Measured
  results and Findings for the root cause (gamma-distributed medians, not a
  bug).
- All data, the case lifecycle, the detection rules and their substantiation
  rates are synthetic; no real insider-risk program's case log is behind any
  number here.
- The suppression and re-identification checks are measured over one
  grouping, (detection_rule, analyst, referral_date); a reporting layer
  exposing additional group-by dimensions would need the same suppression
  check re-measured against each new grouping, not assumed from this one.
- `grafana/insider_risk_dashboard.json` is a committed dashboard definition,
  not deployed against a running Grafana instance or a live datasource.
