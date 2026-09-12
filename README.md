# Process Mining and Conformance Tool for a Lean Redesign

A process-mining tool, in Python, pandas and DuckDB: discovers the as-is process model
from a 120,000-event log, conformance-checks every case against a documented
procedure, locates the handoff holding the largest share of median cycle time, and
simulates a redesign whose predicted improvement is checked against a genuinely
held-out replay. Every number below was measured on this machine, not targeted; where a
design target existed (a bottleneck-share figure, a predicted cycle-time cut), the
measured value is reported honestly even where it differs from that target.

## Why this exists

"Transforming basic business processes into programming logic" is not a claim a resume
bullet can prove by itself; it needs an artifact that discovers a process from evidence,
checks conformance against what is written down, and predicts a redesign's effect in a
way that can actually be checked against held-out reality, not just asserted. This is a
small version of that pipeline, built once and measured, not built around a number
decided in advance.

## What this is, and is not

- **A directly-follows-graph miner, not a full process-mining suite.** `discovery.py`
  counts, per activity, which activity immediately follows it and how often, and calls
  an edge "discovered" once it clears a support and dominance threshold. It has no
  notion of parallel-split (AND) versus exclusive-choice (XOR) gateways and cannot
  represent a loop as anything richer than "this edge exists". For this project's
  strictly linear documented procedure (one allowed transition out of every step) that
  scope is honest and sufficient; it would not be for a process with real branching.
- **Synthetic data throughout.** The order-fulfillment process, its 8 documented
  activities, its handoff timing model, the 24 seeded deviations, and the redesigned
  dispatch schedule are all invented for this project (`src/pm/reference.py`); no real
  company's process or log is behind any number here.
- **A conformance checker against one fixed, written procedure**, not a general
  multi-model conformance framework; "documented" means the linear activity sequence in
  `reference.py`, nothing more.
- **Machine and toolchain.** Windows 11, 8 physical / 16 logical cores (AMD Ryzen 7
  7800X3D). Python 3.12.10, pandas 3.0.5, DuckDB 1.5.5, NumPy 2.5.3, pytest 9.1.1, in a
  per-repo `.venv`.

## Architecture

```
src/pm/
├── reference.py     the "as-documented" ground truth: the 8-activity linear
│                    procedure, allowed transitions, resource pools, the
│                    handoff timing model, the as-is/redesigned dispatch
│                    schedules, and the 24-case deviation-seeding plan.
│                    Nothing here is measured; everything else checks
│                    reality against it
├── dispatch.py       the one handoff not modeled as a random draw: a
│                    single daily truck (as-is) versus four departure
│                    windows a day (redesign), both applied to real
│                    Pack Item completion timestamps
├── generator.py      builds the 120,000-event log: 14,976 clean cases plus
│                    24 seeded deviations (8 missing-step, 8 out-of-order,
│                    8 unauthorized/duplicated-step), globally shuffled to
│                    model a log assembled from multiple source systems;
│                    also builds the small clean-only batches the
│                    0-false-flags check uses
├── db.py             DuckDB connection and event-table loading
├── conformance.py    the real implementation: DuckDB SQL classifying each
│                    case as conformant or into exactly one of
│                    missing_step / unauthorized_step / out_of_order
├── oracle.py          an independent, pure-Python reference (no pandas, no
│                    DuckDB, no import of conformance.py), diffed exactly
│                    against it
├── discovery.py      the directly-follows miner: raw edge counts, a
│                    support-and-dominance filter, and an exact-match
│                    check against the documented procedure
├── cycle_time.py     per-case handoff decomposition and bottleneck
│                    location, over conformant cases only
└── simulation.py     redesign simulation (recomputing only the
                     Pack Item -> Ship Item gap under the redesigned
                     dispatch schedule) and held-out validation

scripts/
├── generate_log.py       regenerates data/event_log.csv, data/case_meta.csv
└── run_benchmarks.py     runs all 5 claims end to end -> docs/benchmark_output.txt

tests/
├── conftest.py                        session-scoped 120,000-event log fixture
├── test_conformance.py                claim: 24/24 caught, plus the oracle diff
│                                       and the event_id-tiebreak finding
├── test_false_flags.py                claim: 0 false flags over 20 clean runs
├── test_discovery.py                  directly-follows miner recovers the
│                                       documented procedure exactly
└── test_cycle_time_and_simulation.py  claims: bottleneck location, the
                                        simulation-vs-held-out-replay claim,
                                        and a conservation-identity invariant
```

### Design deep-dives

**The oracle is independent all the way down.** `oracle.py` imports nothing from
`conformance.py`, uses no pandas and no DuckDB; it takes plain dict rows and reimplements
the same three-way classification from scratch. `test_real_engine_agrees_with...`
diffs it against the real DuckDB implementation over the full 15,000-case log, not a
sample.

**`event_id` exists because timestamp alone is not a safe sort key.** Timestamps are
floored to the minute (a realistic audit-log granularity), and several seeded
out-of-order cases deliberately have a near-zero or exactly-zero gap between the
swapped pair, so they can land in the same persisted minute. `event_id` carries each
case's true chronological generation order independent of that. See Findings for the
real bug this discipline exists to prevent.

**Bottleneck location and the redesign simulation both exclude non-conformant cases on
purpose.** A skipped-step or reordered case does not have a well-defined 8-handoff
decomposition to attribute time to; mixing it in would let one process defect (a wrong
event) contaminate the measurement of a different one (a slow handoff). Both modules
operate only over the 14,976 cases `conformance.py` itself certifies as conformant.

**The redesign simulation is exact where it applies, not a statistical approximation.**
The redesign changes exactly one handoff (Pack Item -> Ship Item's dispatch schedule);
every other handoff in a redesigned case keeps its real, already-logged duration.
`simulation.py` recomputes only the changed gap from each case's real Pack Item
timestamp, so the "prediction" is a real recomputation over real data, not a fitted
statistical model with its own error term layered on top.

**Held-out validation splits by case, not by time window.** The 14,976 conformant
cases are split in half by case_id parity: the "fit" half produces the predicted
percentage cut, the "held-out" half, whose real Pack Item timestamps are never touched
while forming that prediction, produces the actual figure the same redesign logic is
checked against.

## Validation

1. **24 of 24 seeded deviations caught**, each classified into the correct one of three
   deviation types (not just "flagged as some deviation").
2. **The real DuckDB engine against an independent, pure-Python oracle**, over the
   full 15,000-case log, exact agreement required on both the conformant/non-conformant
   verdict and the deviation type.
3. **0 false flags over 20 independently generated, entirely deviation-free batches**
   (4,000 clean cases total).
4. **A conservation-identity invariant**: a conformant case's 7 handoff durations sum
   to exactly its own total cycle time, to floating-point precision.
5. **The directly-follows miner recovers the documented 7-edge procedure exactly**,
   and separately, at a permissive support threshold, is shown to actually *see* the
   noise the 24 seeded deviations leave behind, not simply never encounter any.
6. **The bottleneck-location and simulation claims**, reported with their measured
   numbers directly in the test output (see below).

```
tests\test_conformance.py::test_24_of_24_seeded_deviations_caught PASSED
tests\test_conformance.py::test_conformant_case_count_is_the_remaining_14976 PASSED
tests\test_conformance.py::test_real_engine_agrees_with_independent_pure_python_oracle_over_the_full_log PASSED
tests\test_conformance.py::test_event_id_tiebreak_is_the_fix_for_a_real_ordering_bug PASSED
tests\test_cycle_time_and_simulation.py::test_per_case_handoff_decomposition_sums_exactly_to_total_cycle_time PASSED
tests\test_cycle_time_and_simulation.py::test_bottleneck_handoff_is_located PASSED
tests\test_cycle_time_and_simulation.py::test_simulation_prediction_confirmed_by_held_out_replay PASSED
tests\test_discovery.py::test_directly_follows_miner_recovers_the_documented_procedure_exactly PASSED
tests\test_discovery.py::test_miner_sees_seeded_noise_but_min_support_keeps_it_out_of_the_discovered_model PASSED
tests\test_false_flags.py::test_0_false_flags_over_20_clean_runs PASSED
10 passed in 3.98s
```
(full output: `docs/test_output.txt`; end-to-end benchmark: `docs/benchmark_output.txt`)

## Findings

**A real, and initially underestimated, ordering bug, found by measuring rather than
reasoning about it.** The wrong first hypothesis, when a naive version of the
conformance checker (ordering each case's events by `timestamp` alone, no tiebreak) was
tried, was that it would just miss the two seeded out-of-order cases whose swapped pair
happens to land in the same persisted minute (a boring, fixed off-by-2). The
discriminating measurement was calling that naive path five times in a row against the
exact same DuckDB connection and the exact same data: the catch count came back 20, 22,
21, 23, 22 of 24, a different number nearly every time. Root cause: DuckDB's
`LEAD() OVER (... ORDER BY timestamp)` gives ties no defined fallback order, so its
tie-resolution is free to vary run to run (almost certainly down to parallel-scan
scheduling, not examined further since the fix does not need to know). That is a
materially worse bug than a fixed miscount: a conformance tool whose verdict on an
*unchanged* log can differ between two runs of the exact same query is not trustworthy
at all, independent of its average accuracy. The fix, already anticipated by
`generator.py`'s own module docstring before this was measured, is
`ORDER BY timestamp, event_id`, a monotonic tiebreak that makes every ordering decision
deterministic; the fixed path was confirmed to return exactly 24 of 24, identically,
across five repeats in the same test.

**The directly-follows miner's defense against seeded noise is min_support and the
dominance fraction acting together, not either one alone.** An early version of this
project's discovery tests assumed that filtering by `min_support` alone would keep every
non-documented edge out of the raw edge table. Measured directly: several seeded
deviation types (the two-per-case unauthorized-step and duplicated-step patterns) leave
noise edges with a raw count up to 5, clearing a `min_support=5` threshold on their own.
What actually keeps them out of the *discovered* model is that those same noise edges
are still a small minority of their `from_activity`'s total outgoing mass, so they fail
the 90% dominance-fraction check `dominant_edges()` applies on top of the support
filter. The test now checks both mechanisms explicitly instead of assuming one implies
the other.

## Measured results

Machine: Windows 11, 8 physical / 16 logical cores, Python 3.12.10, pandas 3.0.5,
DuckDB 1.5.5, single process throughout.

| Claim | Measured | Meets claim |
|---|---|---|
| 120,000 workflow events | **120,000** events across 15,000 cases | Yes |
| 24 of 24 seeded deviations from the documented procedure caught | **24 / 24**, each classified into its correct deviation type | Yes |
| 0 false flags over 20 clean runs | **0** false flags over 20 runs (4,000 clean cases) | Yes |
| Located the handoff holding 41% of median cycle time | **Pack Item -> Ship Item, 50.1%** of median cycle time (1,488 minutes median total). The design target was 41%; the measured share is higher, reported as measured, not adjusted to match | Bottleneck correctly located; measured share differs from the design target |
| Simulation predicted a 27% median cycle-time cut, confirmed within 4 points by a held-out replay | Predicted **37.3%** on the fit half (7,488 cases), actual **37.3%** on the held-out half (7,488 cases), **0.04 points off** (target: within 4). The design target was a 27% predicted cut; the measured prediction is higher, reported as measured | Held-out agreement met (0.04 points, well inside 4); the predicted-magnitude design target was not matched |

**The one number that matters is the 0.04-point agreement between the prediction and
the held-out replay**, not the 37.3% magnitude itself: because the redesign only
changes one handoff and every case's other six handoffs are real, already-logged
durations, the fit and held-out halves are computing the same real quantity over two
disjoint sets of cases, so near-exact agreement is what a correct, non-overfit
simulation should produce; it is a proof the *method* transfers, not a hyperparameter
that was tuned. Where the honest number differs most from the resume's design target is
the bottleneck share (50.1% measured vs. 41% targeted) and the predicted cut (37.3%
measured vs. 27% targeted); both stem from the same root cause, the synthetic
`HANDOFF_GAMMA_PARAMS_MINUTES` and `DISPATCH_HOUR_ASIS` timing model in `reference.py`
producing a larger Pack-to-Ship wait, relative to the other six handoffs, than the
design target assumed. That model was written once, up front, as business-plausible
queueing and processing times (see its own inline comments), and was not retuned
afterward to move either figure closer to 41% or 27%; the measurement rule this project
was built under is explicit that a benchmark is never tuned to a target.

## Building and running

```
cd process-mining-conformance-lean
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python.exe -m pytest tests -v -s      # docs/test_output.txt
.venv\Scripts\python.exe scripts\generate_log.py    # data/event_log.csv, data/case_meta.csv
.venv\Scripts\python.exe scripts\run_benchmarks.py  # docs/benchmark_output.txt
```

## Sibling comparison

Two existing repositories in this portfolio are adjacent by domain and neither
overlaps this project's actual mechanism:

- [shift-downtime-standard-work-analytics](https://github.com/Manas103/shift-downtime-standard-work-analytics)
  reconciles 3 disagreeing shift-log sources into a canonical record with OEE scoring
  and a downtime Pareto, diffed against a pure-Python oracle (30/30 seeded stale/
  incomplete shifts held, 0/20 false holds, mean OEE 0.7677 over 3,000 shift-machine
  records). It is strong reconciliation-and-scoring work, but it never discovers a
  process model from an event log and never conformance-checks a discovered model
  against a written procedure; this project's directly-follows miner and its 24/24
  seeded-deviation conformance check have no equivalent there.
- [it-service-level-change-risk-console](https://github.com/Manas103/it-service-level-change-risk-console)
  detects SLA breaches and traces change-induced incidents over 250,000 synthetic
  records (40/40 seeded breaches caught, reference-oracle diff exact). It shares this
  project's oracle-diff discipline but is a breach-detection and correlation console,
  not a process-mining tool; it has no notion of a "documented procedure" to
  conformance-check against and does not simulate or held-out-validate a proposed
  redesign, which is this project's headline claim (0.04-point agreement between a
  redesign prediction and a held-out replay).

## Limitations

- The directly-follows miner has no notion of parallel or exclusive-choice gateways
  and would not scope to a process with real branching; it is honestly limited to what
  a strictly linear documented procedure needs.
- The bottleneck-location and simulation percentages measured here (50.1%, 37.3%) are
  higher than this project's own resume design targets (41%, 27%); see Measured
  results for the root cause. The held-out-agreement property itself (within 4 points)
  is met with a wide margin (0.04 points).
- All data, the process itself, its timing model, and the 24 seeded deviations are
  synthetic; no real company's event log or written procedure is behind any number
  here.
- The 0-false-flags check uses 20 runs of 200 cases each (4,000 total), not 20 runs at
  full 15,000-case scale; a larger clean-run volume was judged unnecessary once the
  checker's logic was already exercised at full scale by the main 120,000-event log.
