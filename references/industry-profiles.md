# Industry Profile Config Reference

When the requested industry is **not** one of the built-in presets, build a
config JSON that supplies the industry's vocabulary and pass it with `--config`.
The generator's mechanics (volume, messiness, join traps, docs) are identical
across industries — the config only chooses names. Think of it as casting the
same play with a different setting.

## The JSON shape

Every key below is required. Copy this template and change the strings.

```json
{
  "industry": "Insurance",
  "fact_table": "fact_claims",
  "fact_record": "claim",
  "date_col": "claim_date",
  "secondary_date_col": "settled_date",
  "amount_col": "claim_amount",
  "statuses": ["Settled", "Open", "Denied", "Pending", "Completed"],
  "customer": {
    "table": "dim_policyholders",
    "noun": "policyholder",
    "id_dim": "policyholder_id",
    "id_fact": "policy_holder_id",
    "id_prefix": "POL",
    "segments": ["Individual", "Family", "Commercial", "Guest"],
    "statuses": ["Active", "Lapsed", "Prospect", "Preferred"],
    "adult_required": true
  },
  "product": {
    "table": "dim_coverages",
    "noun": "coverage",
    "id": "coverage_id",
    "id_prefix": "COV",
    "name_col": "coverage_name",
    "categories": {
      "Auto": ["Liability", "Collision", "Comprehensive"],
      "Home": ["Dwelling", "Contents", "Liability"],
      "Life": ["Term", "Whole", "Universal"]
    }
  },
  "rep": {
    "table": "dim_adjusters",
    "id": "adjuster_id",
    "id_prefix": "ADJ",
    "name_col": "adjuster_name",
    "role": "Claims Adjuster",
    "teams": ["Auto", "Property", "Specialty", "Catastrophe"]
  }
}
```

## Field-by-field

### Top level
| Key | What it is | Guidance |
|---|---|---|
| `industry` | Display name, used in all doc headers. | e.g. "Insurance", "Telecom", "Agriculture". |
| `fact_table` | Fact CSV name (no extension). | `fact_<plural noun>` — `fact_claims`, `fact_calls`, `fact_harvests`. |
| `fact_record` | Singular noun for one fact row. | Used in prose: "one row per **claim**". |
| `date_col` | Primary date column name. | The event date — `claim_date`, `call_date`, `harvest_date`. |
| `secondary_date_col` | Follow-up date column. | Later-than-primary date — `settled_date`, `resolved_date`. Used for `days_to_close` and the end-before-start violation. |
| `amount_col` | Main numeric measure column. | `claim_amount`, `call_revenue`, `yield_value`. |
| `statuses` | Lifecycle statuses for the fact row. | **First entry is treated as the "Completed/closed" state** for the zero-quantity and zero-amount validation rules, so put the terminal success status first. Keep "Completed" in the list if you want that literal value too. |

### `customer` (the main entity dimension)
| Key | What it is | Guidance |
|---|---|---|
| `table` | Dimension CSV name. | `dim_policyholders`, `dim_subscribers`, `dim_farms`. |
| `noun` | Singular entity noun. | "policyholder", "subscriber", "farm". Used in prose and the bridge name. |
| `id_dim` | PK column name **in the dimension**. | e.g. `policyholder_id`. |
| `id_fact` | FK column name **in the fact table**. | **Make it deliberately different from `id_dim`** (e.g. `policy_holder_id` vs `policyholder_id`) — this is the intentional key-name-mismatch join trap. |
| `id_prefix` | Prefix used when formatting IDs. | 3–4 uppercase letters, e.g. `POL`. |
| `segments` | 3–4 segment/type values. | Keep `"Guest"` as one of them if you want the structured-missing-email behavior (Guests usually have blank emails). |
| `statuses` | Lifecycle statuses for the entity. | e.g. Active / Lapsed / Prospect. Some get marked inactive yet appear in recent fact rows (stale-dimension trap). |
| `adult_required` | `true`/`false`. | Set `true` for domains where age<18 is a real violation (finance, insurance, healthcare). Affects the validation exercise wording. |

### `product` (the thing transacted)
| Key | What it is | Guidance |
|---|---|---|
| `table` | Dimension CSV name. | `dim_coverages`, `dim_plans`, `dim_crops`. |
| `noun` | Singular noun. | "coverage", "plan", "crop". |
| `id` | PK/FK column name (same in both tables here). | e.g. `coverage_id`. |
| `id_prefix` | ID prefix. | e.g. `COV`. |
| `name_col` | Name column. | `coverage_name`. |
| `categories` | Object of **3 categories**, each mapping to a list of **2–3 subcategories**. | Must be non-empty. Drives both `category` and `subcategory` columns and the generated product names. |

### `rep` (secondary lookup, reached via the bridge)
| Key | What it is | Guidance |
|---|---|---|
| `table` | Lookup CSV name. | `dim_adjusters`, `dim_agents`, `dim_coops`. |
| `id` | PK column name. | e.g. `adjuster_id`. |
| `id_prefix` | ID prefix. | e.g. `ADJ`. |
| `name_col` | Name column. | `adjuster_name`. |
| `role` | Human-readable role. | "Claims Adjuster". The last word becomes the bridge-name suffix (`bridge_policyholder_adjuster`). |
| `teams` | 3–4 team values. | e.g. Auto / Property / Specialty. |

## Checklist before running

- All three nested objects (`customer`, `product`, `rep`) present.
- `customer.id_dim` ≠ `customer.id_fact` (so the key-mismatch trap exists).
- `product.categories` has at least one category, each with at least one subcategory.
- `statuses[0]` is the terminal/success status.
- IDs prefixes are short and uppercase.

Then:

```bash
python scripts/generate_dataset.py --config ./your_profile.json --rows 1000000 --out ./dataset
```
