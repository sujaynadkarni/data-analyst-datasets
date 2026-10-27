---
name: messy-data-generator
description: >-
  Generate a realistic, messy, multi-table practice dataset for data-analyst
  training. Produces a star schema (fact + dimension tables) for a chosen
  industry with intentional data-quality issues (missing values, duplicates,
  inconsistent formatting, outliers), join traps (key-name mismatches, orphaned
  FKs, fanout, many-to-many bridge, stale dimensions), and business-rule
  violations -- plus an analyst exercise list and data dictionary. Use this
  skill whenever the user wants to CREATE or GENERATE sample/mock/fake/synthetic
  data for practicing data cleaning, ETL, joins, SQL, pandas, or dashboard
  building; mentions a "messy dataset", "dirty data", "data to clean", "practice
  dataset", "star schema sample", "data analyst exercise data", or asks for a
  large CSV (e.g. a million rows) to analyze. Trigger it even if the user only
  names an industry (retail, healthcare, finance, SaaS, logistics, etc.) and
  asks for "analyst practice data" without saying "messy".
---

# Messy Multi-Table Dataset Generator

This skill generates a complete, deliberately-flawed relational dataset that a
data analyst can practice the full workflow on: raw ingestion → profiling →
cleaning → joining → transformation → validation → aggregation → visualization.

The hard, repetitive mechanics (volume up to millions of rows, injecting
duplicates/nulls/outliers, building the join traps) live in a deterministic
Python script so output is reproducible and anyone can run it with only Python 3
(standard library — no `pip install`). The script's job is mechanics; your job
is to pick the right **industry vocabulary**.

## What it produces

Running the generator writes to an output folder:

- **`fact_<...>.csv`** — the fact table (default 1,000,000 rows; tunable), with FKs to every dimension, numeric measures, and a date spanning ~30 months.
- **4 dimension/lookup CSVs** — customers/patients/accounts (~1,000 rows), products/services (~200), locations (~100), and a reps/agents/providers lookup (~75).
- **`bridge_<...>.csv`** — a many-to-many bridge linking the entity dimension to the reps lookup (two-step join).
- **`wide_monthly_targets.csv`** — a wide-format table for unpivot practice.
- **`ENTITY_RELATIONSHIP_SUMMARY.md`** — how the tables relate, the correct join keys, and the known traps.
- **`DATA_DICTIONARY.md`** — every column's type, description, and the specific injected issue.
- **`ANALYST_EXERCISES.md`** — the 10-task exercise list the user wants as the "exercises file".

All injected issues (orphan rate, mixed date/currency/phone formats, structured
missingness, duplicates, outliers, region mismatches, end-before-start,
age<18, stale dimensions, fanout) are produced by the script — you do not
hand-author them.

## Workflow

### 1. Get the industry

If the user already named an industry, use it. If not, ask one short question:
*"Which industry should the dataset model?"* Mention that there are built-in
presets but anything works.

Built-in presets (run `python scripts/generate_dataset.py --list` to confirm):
`retail`, `healthcare`, `finance`, `manufacturing`, `logistics`, `realestate`,
`hr`, `edtech`, `saas`, `hospitality`. The `--industry` flag matches loosely, so
"Retail & E-Commerce", "retail", or "ecommerce" all resolve to the retail preset.

### 2. Decide: preset or custom config?

- **Industry maps to a preset** → just pass `--industry "<name>"`. Done.
- **Industry is NOT in the preset list** (e.g. "insurance", "telecom", "agriculture", "government permits", "nonprofit donations") → you build a small **config JSON** that supplies that industry's vocabulary, then pass `--config`. This is how the skill handles any industry.

  Read **`references/industry-profiles.md`** for the exact JSON shape and a
  filled example. The mechanics are identical across industries — you are only
  choosing names: what the fact table and its records are called, the entity /
  product / rep table names and ID prefixes, realistic segments and statuses,
  and 3 product categories with subcategories. Write the JSON to the output
  folder (or scratch), then run with `--config path.json`.

  Keep it realistic: an insurance config would use `fact_claims`, a `dim_policyholders`
  entity, `dim_coverages` for products, and `dim_adjusters` for reps. Match the
  domain the way the presets do.

### 3. Run the generator

```bash
python scripts/generate_dataset.py --industry "Healthcare & Hospitals" --rows 1000000 --out ./dataset
```

Or with a custom config:

```bash
python scripts/generate_dataset.py --config ./insurance_profile.json --rows 1000000 --out ./dataset
```

Useful flags:
- `--rows N` — fact-table row count. **Default 1,000,000.** Use a smaller number (e.g. `50000`) for a fast first look, then rerun at 1M. Dimension sizes stay per-spec regardless.
- `--seed N` — change the seed for a different draw (output is otherwise deterministic).
- `--out DIR` — output directory (created if missing).
- `--customers / --products / --locations / --reps` — override dimension sizes.
- `--list` — print the built-in presets.

A 1M-row run takes roughly 10 seconds and produces a ~100 MB fact CSV. Warn the
user before generating very large files, and suggest a quick small run first if
they just want to see the shape.

### 4. Hand off

Point the user at the two things they asked for — the data (the CSVs) and the
exercises file (`ANALYST_EXERCISES.md`) — and mention the ER summary and data
dictionary as the answer key. Do not "fix" the messiness: the flaws are the
product.

## Notes

- The script is standard-library only and self-contained, so it runs on any
  machine with Python 3.8+ — important because the user distributes this skill
  for others to install and test.
- If a `--config` run fails, the JSON is almost certainly missing a key or has a
  category with no subcategories — re-check against `references/industry-profiles.md`.
- Everything is synthetic and randomly generated; names, emails, and IDs are
  fake by construction.
