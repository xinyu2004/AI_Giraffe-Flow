# Batch run results (written only by `run_cases.py`)

Single-case scripts (e.g. `python3 cases/longitudinal/acc.py`) do **not** write here.

## Layout

```text
results/
  latest.json                 # pointer + last batch summary
  runs/
    <YYYYMMDD_HHMMSS>/
      summary.json            # suite totals + case list
      cases/
        <case_id>.json        # per-case exit / elapsed / keyword
```

## Fields (summary.json)

| Field | Meaning |
|-------|---------|
| `passed` / `failed` | case id lists |
| `duration_s` | per-case duration budget from env/CLI |
| `stop_on_fail` | whether suite aborted early |
| `cases[]` | same rows as `cases/*.json` |

Per-case JSON includes: `id`, `keyword`, `script`, `exit`, `passed`, `elapsed_s`, `index`, `total`.
