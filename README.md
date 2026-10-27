# messy-data-generator

A Claude [Skill](https://docs.claude.com/en/docs/claude-code/skills) that generates
a realistic, deliberately **messy** multi-table dataset for data-analyst practice —
a full star schema for any industry, complete with the data-quality problems,
join traps, and business-rule violations analysts face in the real world, plus a
ready-made exercise list and answer key.

You tell it an industry; it generates:

- a **fact table** (default **1,000,000 rows**, tunable) + **4 dimension/lookup tables** + a **many-to-many bridge** + a **wide table** for unpivot practice,
- **`ANALYST_EXERCISES.md`** — 10 graded tasks (profile → clean → join → transform → validate → aggregate),
- **`DATA_DICTIONARY.md`** and **`ENTITY_RELATIONSHIP_SUMMARY.md`** — the answer key: every injected flaw and every correct join key.

The flaws are the point — missing values, duplicates, mixed date/currency/phone/ID
formats, outliers, orphaned foreign keys, a key-name mismatch, fanout, stale
dimensions, and validation violations are all baked in on purpose.

## What makes it work for *any* industry

Ten industries ship as built-in presets: **retail, healthcare, finance,
manufacturing, logistics, real estate, HR, edtech, SaaS, hospitality**. For any
industry *not* in that list (insurance, telecom, agriculture, government,
nonprofit, …), the skill writes a small config file supplying that industry's
vocabulary and feeds it to the same generator — so the output is always
domain-appropriate (`fact_claims` + `dim_policyholders` for insurance, etc.).

## Requirements

**Python 3.8+. That's it** — the generator uses only the Python standard library,
no `pip install`, no pandas. A 1M-row run takes ~10 seconds and writes a ~100 MB
fact CSV.

## Install

### As a Claude Code / Claude Desktop skill

Clone (or download) this repo into your skills directory:

```bash
git clone https://github.com/<your-username>/messy-data-generator.git \
  ~/.claude/skills/messy-data-generator
```

Then just ask Claude, e.g. *"generate a messy healthcare dataset for analyst
practice"* or *"make me a million-row retail dataset to clean"*, and the skill
triggers automatically.

### Run the generator directly (no Claude needed)

```bash
# See the built-in industry presets
python scripts/generate_dataset.py --list

# Generate 1M rows for a preset industry
python scripts/generate_dataset.py --industry "Retail & E-Commerce" --rows 1000000 --out ./dataset

# Quick 50k-row run to see the shape first
python scripts/generate_dataset.py --industry saas --rows 50000 --out ./dataset

# Any other industry: use a custom config (see references/industry-profiles.md)
python scripts/generate_dataset.py --config ./insurance_profile.json --rows 1000000 --out ./dataset
```

### Flags

| Flag | Default | Description |
|---|---|---|
| `--industry` | — | Industry name; matched loosely against the built-in presets. |
| `--config` | — | Path to a custom industry-profile JSON (for industries not in presets). |
| `--rows` | `1000000` | Fact-table row count. |
| `--out` | `./output` | Output directory. |
| `--seed` | `42` | Random seed; output is deterministic for a given seed. |
| `--customers` / `--products` / `--locations` / `--reps` | 1000 / 200 / 100 / 75 | Dimension sizes. |
| `--list` | — | Print built-in presets and exit. |

## What's injected (the practice material)

- **Missing values** (~10–15%), including structured missingness (Guests have no email).
- **Duplicates** (~3–5%): exact rows, near-duplicate names (casing/spacing/punctuation), and the same transaction recorded twice.
- **Inconsistent formatting**: dates in three formats in one column; mixed phone, currency, boolean, and text-case styles; inconsistent ID prefixes (`CUST-0001` / `0001` / `C0001` / `CUST0001`).
- **Outliers** (~2–4%): age 999, negative amounts, 10×+ spikes, quantity 0 on completed orders, future dates.
- **Join traps**: a deliberate key-name mismatch (fact vs dimension), ~4% orphaned foreign keys, fanout via the bridge, and stale (inactive/churned) dimension rows still appearing in recent facts.
- **Validation violations**: end-date-before-start, zero amount on completed, under-18 where adult verification is required, duplicate IDs with different amounts, and region mismatches.

## Repository layout

```
messy-data-generator/
├── SKILL.md                         # skill definition (triggers + workflow)
├── README.md                        # this file
├── scripts/
│   └── generate_dataset.py          # the generator (stdlib only)
└── references/
    └── industry-profiles.md         # config JSON spec for custom industries
```

## License

MIT — use it, fork it, teach with it.
