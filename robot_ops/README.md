# Robot Data-Collection Session Conformance and Improvement Report (extension)

Re-points the base repo's conformance-checking, cycle-time and
redesign-simulation engine at a robot data-collection session lifecycle
instead of order fulfillment: a 120,000-event, 24,000-session synthetic
operations log (station prepped, scene reset, episode recorded, episode
validated, episode uploaded), checked case by case against that documented
lifecycle, decomposed into per-stage cycle time, and used to validate one
proposed handoff redesign against a genuinely held-out replay. Every
number below was measured on this machine, not targeted; where a design
target existed (carried over from the base repo's own measured figures),
the measured value is reported honestly even where it differs widely from
that target.

## Why this exists

A written standard operating procedure only tells you what is supposed to
happen; it does not tell you whether a collection floor actually followed
it, where the floor's time really goes, or whether a proposed process
change would help. This is a small version of the artifact that answers
all three, re-pointing the base repo's already-validated process-mining
engine (DuckDB conformance checking diffed against an independent
pure-Python oracle, per-case handoff decomposition, held-out-validated
redesign simulation) at a robot-operations session lifecycle rather than
rebuilding the same mechanism from scratch for a new domain.

## Honest framing, up front

- **Extension, not a new repo.** This directory re-points the base repo's
  conformance/cycle-time/simulation engine at a different session
  lifecycle; the base repo's own order-fulfillment claims (discovery,
  conformance, the dispatch-redesign simulation) are untouched by anything
  in here and are not re-verified by this extension.
- **Synthetic data throughout.** The 5-stage session lifecycle, the
  handoff timing model and the upload-window schedule are all invented for
  this extension (`src/ro/ro_reference.py`); no real robot lab's session
  log is behind any number here. There is no robot and no teleoperation
  hardware anywhere in this build.
- **A conformance checker against one fixed, written procedure**, not a
  general multi-model conformance framework, exactly as the base repo's
  own README discloses; "documented" means the linear activity sequence in
  `ro_reference.py`, nothing more.
- **The bottleneck-share and predicted-cut design targets quoted in the
  Measured results table are the base repo's own already-measured
  figures** (50.1% and 37.3%/37.3%), carried over as placeholders before
  this extension's own session lifecycle was built and measured; they are
  not this extension's design targets and were never expected to match.
- **Machine and toolchain.** Windows 11, 8 physical / 16 logical cores.
  Python 3.12.10, pandas 3.0.5, DuckDB 1.5.5, NumPy 2.5.3, pytest 9.1.1, in
  a per-extension `.venv`, reusing the base repo's `src/pm/db.py`
  unmodified.

## Architecture

```
robot_ops/
├── src/ro/
│   ├── ro_reference.py    the "as-documented" ground truth: the 5-stage
│   │                      session lifecycle, resource pools, the handoff
│   │                      timing model, the as-is/redesigned upload-window
│   │                      schedules, and the 24-case deviation-seeding plan
│   ├── ro_upload.py        the one handoff not modeled as a random draw: a
│   │                      single daily batch upload window (as-is) versus
│   │                      four upload windows a day (redesign), both
│   │                      applied to real Episode Validated timestamps
│   ├── ro_generator.py     builds the 120,000-event log: 23,976 clean
│   │                      sessions plus 24 seeded deviations (8
│   │                      missing-stage, 8 out-of-order, 8 unauthorized/
│   │                      duplicated-stage), globally shuffled, plus the
│   │                      small clean-only batches the 0-false-flags check
│   │                      uses
│   ├── ro_conformance.py   the real implementation: DuckDB SQL classifying
│   │                      each session as conformant or into exactly one
│   │                      of missing_step / unauthorized_step / out_of_order
│   ├── ro_oracle.py        an independent, pure-Python reference (no
│   │                      pandas, no DuckDB, no import of
│   │                      ro_conformance.py), diffed exactly against it
│   ├── ro_cycle_time.py    per-case handoff decomposition and bottleneck
│   │                      location, over conformant sessions only
│   └── ro_simulation.py    redesign simulation (recomputing only the
│                          Episode Validated -> Episode Uploaded gap under
│                          the redesigned upload schedule) and held-out
│                          validation
├── scripts/
│   ├── generate_log.py       regenerates data/session_log.csv, session_meta.csv
│   └── run_benchmarks.py     runs all 6 claims end to end -> docs/benchmark_output.txt
└── tests/
    ├── conftest.py                        session-scoped 120,000-event log
    │                                      fixture, loaded via the base
    │                                      repo's pm.db
    ├── test_conformance.py                claim: 24/24 caught, plus the
    │                                      oracle diff
    ├── test_false_flags.py                claim: 0 false flags over 20
    │                                      clean runs
    └── test_cycle_time_and_simulation.py  claims: bottleneck location, the
                                            simulation-vs-held-out-replay
                                            claim, and a conservation-
                                            identity invariant
```

### Design deep-dives

**The engine is reused unmodified; only the domain it is pointed at is
new.** `ro_conformance.py`, `ro_oracle.py`, `ro_cycle_time.py` and
`ro_simulation.py` are direct re-points of the base repo's `conformance.py`
/ `oracle.py` / `cycle_time.py` / `simulation.py`: same three-way deviation
classification and priority order, same `(timestamp, event_id)` tiebreak
discipline, same conformant-cases-only restriction for cycle time, same
fit/holdout case-id-parity split for the redesign simulation. What's new is
`ro_reference.py`'s 5-stage session lifecycle and `ro_upload.py`'s
upload-window gate in place of the base repo's dispatch-truck gate; nothing
about the mechanism itself needed changing to move domains, which is the
same conclusion the base repo's own `insider_risk/` extension reached about
its half of the engine (see Sibling comparison).

**The upload-window gate is a schedule change, not a timing-model change,**
exactly mirroring the base repo's dispatch redesign: every other handoff
keeps its real, already-logged gamma-drawn duration; only the moment
"Episode Uploaded" occurs changes, recomputed directly from each session's
real "Episode Validated" timestamp under the redesigned four-windows-a-day
schedule. That is why the held-out agreement is as tight as it is (0.24
percentage points): both halves are measuring the same real recomputation
over disjoint sessions, not two fits of a statistical model.

**The deviation-seeding plan was sized to its own domain's scale, not
reused verbatim.** The base repo's 8-activity lifecycle has 4 skippable
middle activities; this extension's 5-stage lifecycle has only 3 (Scene
Reset, Episode Recorded, Episode Validated), so the 8 missing-stage cases
are split 3/3/2 across them instead of 2/2/2/2. The reorder and
extra/unauthorized splits (8 and 4+4) carry over unchanged because they do
not depend on how many skippable middle activities exist.

## Validation

1. **120,000 events across 24,000 sessions**, 5 stages each.
2. **24 of 24 seeded deviations caught**, each classified into the correct
   one of three deviation types.
3. **The real DuckDB engine against an independent, pure-Python oracle**,
   over the full 24,000-session log, exact agreement on both the
   conformant/non-conformant verdict and the deviation type.
4. **0 false flags over 20 independently generated, entirely
   deviation-free batches** (4,000 clean sessions total).
5. **A conservation-identity invariant**: a conformant session's 4 handoff
   durations sum to exactly its own total cycle time.
6. **The bottleneck-location and simulation claims**, reported with their
   measured numbers directly in the test output.

```
tests/test_conformance.py::test_24_of_24_seeded_deviations_caught PASSED
tests/test_conformance.py::test_conformant_case_count_is_the_remaining_23976 PASSED
tests/test_conformance.py::test_real_engine_agrees_with_independent_pure_python_oracle_over_the_full_log PASSED
tests/test_cycle_time_and_simulation.py::test_per_case_handoff_decomposition_sums_exactly_to_total_cycle_time PASSED
tests/test_cycle_time_and_simulation.py::test_bottleneck_handoff_is_located PASSED
tests/test_cycle_time_and_simulation.py::test_simulation_prediction_confirmed_by_held_out_replay PASSED
tests/test_false_flags.py::test_0_false_flags_over_20_clean_runs PASSED

7 passed in 3.53s
```
(full output: `docs/test_output.txt`; claim-by-claim summary: `docs/benchmark_output.txt`)

## Findings

**The upload-window bottleneck dominates far more heavily here than the
base repo's dispatch-truck bottleneck did, and that is a real property of
this extension's timing model, not a bug.** The base repo's 8-activity
lifecycle has six gamma-drawn handoffs plus the gated one, so even a large
gated wait is diluted by the other six. This extension's 5-stage lifecycle
has only three gamma-drawn handoffs (means 21/30/45 minutes, chosen as
business-plausible station timings and never adjusted afterward), so the
single daily upload window's typical multi-hour wait makes up 88.4% of
median cycle time rather than something closer to the base repo's 50.1%.
Both figures are honest measurements of two differently-shaped timing
models, not a target either repo tuned toward; see Measured results and
Limitations for why this was not retuned to look more similar to the
base repo's number.

**A held-out agreement this tight (0.24 points) is the expected result of
an exact recomputation, not evidence by itself that the redesign would
actually help by that much in reality.** Because every session's other
three handoffs keep their real, already-logged duration, and only the
"Episode Uploaded" timestamp is recomputed under the redesigned schedule,
the fit and holdout halves are the same deterministic function evaluated
on two disjoint session sets; near-exact agreement proves the *method*
transfers between the two halves, not that the synthetic timing model
itself reflects a real lab's upload-window queueing behavior.

## Measured results

Machine: Windows 11, 8 physical / 16 logical cores, Python 3.12.10, pandas
3.0.5, DuckDB 1.5.5, single process throughout.

| Claim | Measured | Meets claim |
|---|---|---|
| 120,000-event simulated operations log | **120,000** events across **24,000** sessions | Yes |
| 24 of 24 seeded deviations caught and classified | **24 / 24** caught, **0** misclassified | Yes |
| 0 false flags over 20 clean runs | **0** false flags over 20 runs (4,000 clean sessions) | Yes |
| SQL conformance decisions diffed exactly against an independently coded oracle | **0** disagreements over 24,000 sessions | Yes |
| Bottleneck handoff located at 50.1% of median cycle time | **Episode Validated -> Episode Uploaded, 88.4%** of median cycle time (830.0 min median total). The quoted 50.1% is the base repo's own measured figure, carried over as a placeholder before this extension existed; this extension's own timing model (three gamma handoffs instead of six, see Findings) produces a much more dominant upload-window bottleneck, reported as measured, not adjusted to match | Bottleneck correctly located; measured share differs widely from the carried-over figure |
| One handoff change predicted a 37.3% median cycle-time cut against 37.3% measured on a held-out replay | Predicted **65.30%** on the fit half (11,988 sessions), actual **65.54%** on the held-out half (11,988 sessions), **0.24 points off** (within-4-point bar carried over from the base repo, cleared). The quoted 37.3%/37.3% is likewise the base repo's own figure | Held-out agreement met (0.24 points, well inside 4); the carried-over magnitude was not matched |

**The one number that matters is the 0.24-point agreement between the
prediction and the held-out replay**, not the 65.3% magnitude itself, for
the same reason the base repo gives for its own 0.04-point figure: because
the redesign only changes one handoff and every session's other three
handoffs are real, already-logged durations, the fit and held-out halves
compute the same real quantity over two disjoint session sets, so
near-exact agreement is what a correct, non-overfit simulation should
produce. Where this extension's honest numbers differ most from the
carried-over design targets is the bottleneck share (88.4% measured vs.
50.1% quoted) and the predicted cut (65.3% measured vs. 37.3% quoted);
both stem from the same root cause, a 5-stage lifecycle with only three
gamma-drawn handoffs instead of the base repo's six, producing a far more
dominant gated-handoff share. That timing model was written once, up
front (see `ro_reference.py`'s inline comments), and was not retuned
afterward to move either figure closer to the carried-over targets.

## Building and running

```
cd process-mining-conformance-lean/robot_ops
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python.exe -m pytest tests -v -s      # docs/test_output.txt
.venv\Scripts\python.exe scripts\generate_log.py    # data/session_log.csv, data/session_meta.csv
.venv\Scripts\python.exe scripts\run_benchmarks.py  # docs/benchmark_output.txt
```

## Sibling comparison

The base repo ([process-mining-conformance-lean](https://github.com/Manas103/process-mining-conformance-lean))
is this extension's own sibling and the clearest contrast available: it
runs the identical conformance/cycle-time/simulation engine over an
order-fulfillment process with a single daily truck-dispatch bottleneck
measured at 50.1% of median cycle time and a redesign held out to 0.04
points. This extension points the same engine at a 5-stage robot
data-collection session lifecycle with a single daily upload-window
bottleneck instead, measured at a much larger 88.4% of median cycle time
(three gamma handoffs instead of six, see Findings) and a redesign held
out to 0.24 points. The sibling `insider_risk/` extension, by contrast,
only re-points the cycle-time half of the engine (it does not seed or
check conformance deviations at all); this extension re-points the full
conformance-and-simulation engine, which is why it carries a 24/24
seeded-deviation check and an oracle diff that `insider_risk/` does not.

## Limitations

- The bottleneck-location and simulation percentages measured here (88.4%,
  65.3%/65.5%) are far higher than the design targets quoted in the
  Measured results table (50.1%, 37.3%/37.3%), which are the base repo's
  own already-measured figures carried over as placeholders before this
  extension's own session lifecycle existed; see Measured results and
  Findings for the root cause (a 5-stage lifecycle with only three
  gamma-drawn handoffs, not a bug). The held-out-agreement property itself
  (within 4 points) is met with a wide margin (0.24 points).
- All data, the session lifecycle, the handoff timing model and the 24
  seeded deviations are synthetic; no real robot lab's session log is
  behind any number here, and no robot or teleoperation hardware is
  involved anywhere in this build.
- The 0-false-flags check uses 20 runs of 200 sessions each (4,000 total),
  not 20 runs at full 24,000-session scale, matching the base repo's own
  precedent for this check.
- The directly-follows discovery module from the base repo is not
  re-pointed here; this extension's claims are about conformance, cycle
  time and the redesign simulation only.
