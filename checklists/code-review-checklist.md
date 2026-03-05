# Code Review Checklist

## Run before any analysis on real data

### Automated (Claude Code runs these)
[ ] `ruff check src/` — zero errors
[ ] `pytest tests/ -v` — all pass
[ ] `python tests/make_synthetic.py && pytest tests/` — fixtures fresh and tests pass

### Logical review (paste code into Claude chat)
[ ] Merge keys confirmed — no unintended row multiplication
[ ] Date arithmetic checked — durations in correct units, no off-by-one
[ ] Censoring encoding confirmed — 1=event, 0=censored, matches lifelines convention
[ ] Null handling explicit — no silent drops or fills
[ ] Group-by / aggregation level correct — member vs. encounter vs. claim level

### Analytic review (researcher + statistician)
[ ] Covariate list reviewed against protocol
[ ] PH assumption checked (Schoenfeld residuals or log-log plot)
[ ] Exclusions match IRB-approved criteria
[ ] Sample sizes match expected cohort
[ ] Direction of HRs makes clinical sense