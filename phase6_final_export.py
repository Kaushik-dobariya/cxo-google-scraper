"""
Phase 6 — Final Lead Dataset & Export
======================================

Purpose
-------
Combine the validated Phase 5 dataset with the best available Phase 5.1
enrichment fields and produce final, production-friendly CSV exports.

Cost policy
-----------
Google Places API : NOT USED
Google Search API  : NOT USED
Paid API           : NOT USED
Proxy              : NOT USED
Scraping service   : NOT USED

Inputs
------
output/cxo/cxo_people_final.csv
output/cxo/cxo_people_enriched.csv

Outputs
-------
output/final/leads_master.csv
output/final/cxo_leads.csv
output/final/board_leads.csv
output/final/executive_leadership_leads.csv
output/final/company_contacts.csv
output/final/run_summary.csv

Design principles
-----------------
- Phase 5 validation remains authoritative.
- Phase 5.1 enrichment is optional and never removes a validated lead.
- Missing enrichment remains blank.
- No data is invented.
- No extra web requests are made.
- The output is deterministic and auditable.
"""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

PHASE5_FILE = Path("output/cxo/cxo_people_final.csv")

PHASE51_FILE = Path("output/cxo/cxo_people_enriched.csv")

OUTPUT_DIR = Path("output/final")

LEADS_MASTER_FILE = OUTPUT_DIR / "leads_master.csv"
CXO_FILE = OUTPUT_DIR / "cxo_leads.csv"
BOARD_FILE = OUTPUT_DIR / "board_leads.csv"
EXECUTIVE_FILE = OUTPUT_DIR / "executive_leadership_leads.csv"
CONTACTS_FILE = OUTPUT_DIR / "company_contacts.csv"
SUMMARY_FILE = OUTPUT_DIR / "run_summary.csv"


MASTER_FIELDS = [
    "company_name",
    "company_domain",
    "person_name",
    "designation",
    "leadership_type",
    "lead_priority",
    "quality_score",
    "source_url",
    "verification_status",
    "verification_source",
    "enrichment_status",
    "enrichment_confidence",
    "professional_profile_url",
    "public_bio_url",
    "public_bio_excerpt",
    "public_location",
    "enrichment_method",
    "source_fetch_status",
]


CONTACT_FIELDS = [
    "company_name",
    "company_domain",
    "source_url",
]


PRIORITY_MAP = {
    "CXO": "HIGH",
    "Executive Leadership": "MEDIUM",
    "Board": "LOW",
}


def clean_text(value: object) -> str:
    """Normalize whitespace."""
    text = "" if value is None else str(value)
    return " ".join(text.replace("\xa0", " ").split())


def normalize_type(value: object) -> str:
    """Normalize leadership type."""
    value = clean_text(value)

    mapping = {
        "cxo": "CXO",
        "board": "Board",
        "executive leadership": "Executive Leadership",
    }

    return mapping.get(
        value.casefold(),
        value,
    )


def normalize_row(row: dict[str, str]) -> dict[str, str]:
    """Normalize fields from Phase 5 / Phase 5.1."""
    result = {key: clean_text(value) for key, value in row.items()}

    result["company_name"] = clean_text(result.get("company_name", ""))

    result["company_domain"] = clean_text(
        result.get("company_domain", "")
    ).removeprefix("www.")

    result["person_name"] = clean_text(result.get("person_name", ""))

    result["designation"] = clean_text(result.get("designation", ""))

    result["leadership_type"] = normalize_type(result.get("leadership_type", ""))

    return result


def load_csv(path: Path) -> list[dict[str, str]]:
    """Load a CSV file."""
    if not path.exists():
        raise FileNotFoundError(f"Required input file not found: {path}")

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        return list(csv.DictReader(handle))


def index_enrichment(
    rows: list[dict[str, str]],
) -> dict[tuple[str, str, str], dict[str, str]]:
    """Index enrichment by company + person + designation."""
    index: dict[
        tuple[str, str, str],
        dict[str, str],
    ] = {}

    for raw_row in rows:
        row = normalize_row(raw_row)

        key = (
            row["company_name"].casefold(),
            row["person_name"].casefold(),
            row["designation"].casefold(),
        )

        index[key] = row

    return index


def build_master_row(
    validated_row: dict[str, str],
    enrichment_row: dict[str, str] | None,
) -> dict[str, str]:
    """
    Build one final master row.

    Phase 5 data is the authority for identity, designation, type,
    quality score, and source. Phase 5.1 only contributes optional
    enrichment fields.
    """
    base = normalize_row(validated_row)

    merged = dict(base)

    if enrichment_row is not None:
        enrichment = normalize_row(enrichment_row)

        optional_fields = [
            "company_domain",
            "verification_status",
            "verification_source",
            "enrichment_status",
            "enrichment_confidence",
            "professional_profile_url",
            "public_bio_url",
            "public_bio_excerpt",
            "public_location",
            "enrichment_method",
            "source_fetch_status",
        ]

        for field in optional_fields:
            value = clean_text(
                enrichment.get(
                    field,
                    "",
                )
            )

            if value:
                merged[field] = value

    merged["lead_priority"] = PRIORITY_MAP.get(
        merged["leadership_type"],
        "LOW",
    )

    # Phase 5 verification remains authoritative.
    if clean_text(base.get("validation_status", "")) == "VALID":
        merged["verification_status"] = "VERIFIED"

    return {
        field: clean_text(
            merged.get(
                field,
                "",
            )
        )
        for field in MASTER_FIELDS
    }


def identity_key(
    row: dict[str, str],
) -> tuple[str, str, str]:
    """Return a conservative identity key."""
    return (
        row["company_name"].casefold(),
        row["person_name"].casefold(),
        row["designation"].casefold(),
    )


def deduplicate_master(
    rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], int]:
    """Deduplicate final master rows."""
    unique: dict[
        tuple[str, str, str],
        dict[str, str],
    ] = {}

    for row in rows:
        key = identity_key(row)

        if key not in unique:
            unique[key] = row

    removed = len(rows) - len(unique)

    return list(unique.values()), removed


def sort_master(
    rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Sort by priority, company, then person."""
    priority_rank = {
        "HIGH": 1,
        "MEDIUM": 2,
        "LOW": 3,
    }

    return sorted(
        rows,
        key=lambda row: (
            priority_rank.get(
                row["lead_priority"],
                9,
            ),
            row["company_name"].casefold(),
            row["person_name"].casefold(),
        ),
    )


def write_csv(
    path: Path,
    rows: list[dict[str, str]],
    fields: list[str],
) -> None:
    """Write a CSV with a stable field order."""
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
            extrasaction="ignore",
        )

        writer.writeheader()
        writer.writerows(rows)


def build_contacts(
    rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    """
    Build a company-level contact/source index from the final lead data.

    This is deliberately limited to company source metadata. No personal
    email or phone is guessed or fabricated.
    """
    seen: set[tuple[str, str, str]] = set()
    contacts: list[dict[str, str]] = []

    for row in rows:
        record = {
            "company_name": row["company_name"],
            "company_domain": row["company_domain"],
            "source_url": row["source_url"],
        }

        key = (
            record["company_name"].casefold(),
            record["company_domain"].casefold(),
            record["source_url"].casefold(),
        )

        if key in seen:
            continue

        seen.add(key)
        contacts.append(record)

    contacts.sort(
        key=lambda row: (
            row["company_name"].casefold(),
            row["source_url"].casefold(),
        )
    )

    return contacts


def build_summary_rows(
    rows: list[dict[str, str]],
    duplicates_removed: int,
    phase5_count: int,
    enrichment_count: int,
) -> list[dict[str, str]]:
    """Create an auditable run summary."""
    company_counts = Counter(row["company_name"] for row in rows)

    type_counts = Counter(row["leadership_type"] for row in rows)

    priority_counts = Counter(row["lead_priority"] for row in rows)

    verification_counts = Counter(row["verification_status"] for row in rows)

    enrichment_status_counts = Counter(
        row["enrichment_status"] or "NOT_PROCESSED" for row in rows
    )

    summary: list[dict[str, str]] = [
        {
            "metric": "phase5_input_records",
            "value": str(phase5_count),
            "detail": "",
        },
        {
            "metric": "phase51_input_records",
            "value": str(enrichment_count),
            "detail": "",
        },
        {
            "metric": "final_records",
            "value": str(len(rows)),
            "detail": "",
        },
        {
            "metric": "duplicates_removed",
            "value": str(duplicates_removed),
            "detail": "",
        },
    ]

    for key, value in sorted(company_counts.items()):
        summary.append(
            {
                "metric": "company",
                "value": str(value),
                "detail": key,
            }
        )

    for key, value in sorted(type_counts.items()):
        summary.append(
            {
                "metric": "leadership_type",
                "value": str(value),
                "detail": key,
            }
        )

    for key, value in sorted(priority_counts.items()):
        summary.append(
            {
                "metric": "lead_priority",
                "value": str(value),
                "detail": key,
            }
        )

    for key, value in sorted(verification_counts.items()):
        summary.append(
            {
                "metric": "verification_status",
                "value": str(value),
                "detail": key,
            }
        )

    for key, value in sorted(enrichment_status_counts.items()):
        summary.append(
            {
                "metric": "enrichment_status",
                "value": str(value),
                "detail": key,
            }
        )

    return summary


def main() -> None:
    print("Cost policy:")
    print("Google Places API : NOT USED")
    print("Google Search API : NOT USED")
    print("Paid API          : NOT USED")
    print("Proxy             : NOT USED")
    print("Scraping service  : NOT USED")

    print("\n============================================================")
    print("PHASE 6 - FINAL LEAD DATASET & EXPORT")
    print("============================================================")

    phase5_rows = load_csv(PHASE5_FILE)

    enrichment_rows = load_csv(PHASE51_FILE)

    print(f"\nPhase 5 records       : {len(phase5_rows)}")

    print(f"Phase 5.1 records     : {len(enrichment_rows)}")

    enrichment_index = index_enrichment(enrichment_rows)

    master_rows: list[dict[str, str]] = []

    for phase5_row in phase5_rows:
        normalized = normalize_row(phase5_row)

        key = (
            normalized["company_name"].casefold(),
            normalized["person_name"].casefold(),
            normalized["designation"].casefold(),
        )

        enrichment = enrichment_index.get(key)

        master_rows.append(
            build_master_row(
                phase5_row,
                enrichment,
            )
        )

    master_rows, duplicates_removed = deduplicate_master(master_rows)

    master_rows = sort_master(master_rows)

    cxo_rows = [row for row in master_rows if row["leadership_type"] == "CXO"]

    board_rows = [row for row in master_rows if row["leadership_type"] == "Board"]

    executive_rows = [
        row for row in master_rows if row["leadership_type"] == "Executive Leadership"
    ]

    company_contacts = build_contacts(master_rows)

    summary_rows = build_summary_rows(
        master_rows,
        duplicates_removed,
        len(phase5_rows),
        len(enrichment_rows),
    )

    write_csv(
        LEADS_MASTER_FILE,
        master_rows,
        MASTER_FIELDS,
    )

    write_csv(
        CXO_FILE,
        cxo_rows,
        MASTER_FIELDS,
    )

    write_csv(
        BOARD_FILE,
        board_rows,
        MASTER_FIELDS,
    )

    write_csv(
        EXECUTIVE_FILE,
        executive_rows,
        MASTER_FIELDS,
    )

    write_csv(
        CONTACTS_FILE,
        company_contacts,
        CONTACT_FIELDS,
    )

    write_csv(
        SUMMARY_FILE,
        summary_rows,
        [
            "metric",
            "value",
            "detail",
        ],
    )

    print("\nRESULT")
    print(f"Final master records : {len(master_rows)}")
    print(f"CXO leads            : {len(cxo_rows)}")
    print(f"Board leads          : {len(board_rows)}")
    print(f"Executive leadership : {len(executive_rows)}")
    print(f"Company source rows  : {len(company_contacts)}")
    print(f"Duplicates removed   : {duplicates_removed}")

    print("\nFILES")
    print(f"Master     : {LEADS_MASTER_FILE}")
    print(f"CXO        : {CXO_FILE}")
    print(f"Board      : {BOARD_FILE}")
    print(f"Executive  : {EXECUTIVE_FILE}")
    print(f"Contacts   : {CONTACTS_FILE}")
    print(f"Summary    : {SUMMARY_FILE}")

    print("\n============================================================")
    print("PHASE 6 COMPLETE")
    print("============================================================")
    print("\nFinal lead dataset export completed.")


if __name__ == "__main__":
    main()
