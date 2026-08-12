"""
Phase 6.1 — Public Contact Merge
================================

Purpose
-------
Merge public company-level phone/email data discovered by Phase 3 into
the final Phase 6 lead dataset.

Inputs
------
output/final/leads_master.csv
output/page_contacts.csv

Outputs
-------
output/final/leads_master_with_contacts.csv
output/final/cxo_leads_with_contacts.csv
output/final/board_leads_with_contacts.csv
output/final/executive_leadership_leads_with_contacts.csv
output/final/company_contacts_with_contacts.csv
output/final/contact_merge_summary.csv

Cost policy
-----------
Google Places API : NOT USED
Google Search API  : NOT USED
Paid API           : NOT USED
Proxy              : NOT USED
Scraping service   : NOT USED

Important
---------
These are PUBLIC COMPANY CONTACTS unless Phase 3 explicitly provides
strong evidence otherwise. This phase does not invent or infer personal
CXO email addresses or direct phone numbers.

The merge is deliberately flexible because Phase 3 contact CSVs may use
slightly different column names (email/emails, phone/phones, etc.).
"""

from __future__ import annotations

import csv
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

FINAL_DIR = Path("output/final")
MASTER_FILE = FINAL_DIR / "leads_master.csv"
CXO_FILE = FINAL_DIR / "cxo_leads.csv"
BOARD_FILE = FINAL_DIR / "board_leads.csv"
EXECUTIVE_FILE = FINAL_DIR / "executive_leadership_leads.csv"
COMPANY_CONTACTS_FILE = FINAL_DIR / "company_contacts.csv"

PAGE_CONTACTS_FILE = Path("output/page_contacts.csv")

MASTER_WITH_CONTACTS = FINAL_DIR / "leads_master_with_contacts.csv"
CXO_WITH_CONTACTS = FINAL_DIR / "cxo_leads_with_contacts.csv"
BOARD_WITH_CONTACTS = FINAL_DIR / "board_leads_with_contacts.csv"
EXECUTIVE_WITH_CONTACTS = FINAL_DIR / "executive_leadership_leads_with_contacts.csv"
COMPANY_CONTACTS_WITH_CONTACTS = FINAL_DIR / "company_contacts_with_contacts.csv"
SUMMARY_FILE = FINAL_DIR / "contact_merge_summary.csv"


EMAIL_COLUMNS = (
    "email",
    "emails",
    "email_address",
    "email_addresses",
    "public_email",
    "company_email",
    "contact_email",
)

PHONE_COLUMNS = (
    "phone",
    "phones",
    "phone_number",
    "phone_numbers",
    "telephone",
    "telephones",
    "public_phone",
    "company_phone",
    "contact_phone",
)

COMPANY_COLUMNS = (
    "company_name",
    "company",
    "organisation",
    "organization",
)

DOMAIN_COLUMNS = (
    "company_domain",
    "domain",
    "website_domain",
)

URL_COLUMNS = (
    "page_url",
    "source_url",
    "url",
    "contact_page",
)

CONTACT_LINK_COLUMNS = (
    "contact_url",
    "contact_link",
    "contact_page_url",
)


def clean_text(value: object) -> str:
    """Normalize whitespace."""
    if value is None:
        return ""

    text = str(value).replace("\xa0", " ")

    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


def normalize_key(value: object) -> str:
    """Normalize a matching key."""
    return clean_text(value).casefold()


def normalize_domain(value: object) -> str:
    """Normalize a domain or URL into a hostname."""
    value = clean_text(value)

    if not value:
        return ""

    parsed = urlparse(value)

    if parsed.netloc:
        host = parsed.hostname or ""
    else:
        host = value.split("/")[0]

    return host.casefold().removeprefix("www.")


def split_contact_values(value: object) -> list[str]:
    """
    Split a contact field into individual values.

    Supports common separators used in CSV output:
    comma, semicolon, pipe, newline.
    """
    text = clean_text(value)

    if not text:
        return []

    parts = re.split(
        r"[;,|\n]+",
        text,
    )

    return [clean_text(part) for part in parts if clean_text(part)]


def valid_email(value: str) -> bool:
    """Basic public email validation."""
    return bool(
        re.fullmatch(
            r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+"
            r"@"
            r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+",
            value,
        )
    )


def normalize_phone(value: str) -> str:
    """
    Keep a public phone number without guessing its country code.

    Allows digits, spaces, parentheses, +, -, and x/ext markers.
    """
    value = clean_text(value)

    if not value:
        return ""

    value = re.sub(
        r"(?i)\b(?:ext\.?|extension)\s*",
        " x",
        value,
    )

    value = re.sub(
        r"[^0-9+()xX.\-\s]",
        "",
        value,
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    ).strip()

    digits = re.sub(
        r"\D",
        "",
        value,
    )

    if len(digits) < 7:
        return ""

    return value


def unique_join(
    values: list[str],
    separator: str = " | ",
) -> str:
    """Deduplicate and join values while preserving order."""
    result: list[str] = []
    seen: set[str] = set()

    for value in values:
        cleaned = clean_text(value)

        if not cleaned:
            continue

        key = cleaned.casefold()

        if key in seen:
            continue

        seen.add(key)
        result.append(cleaned)

    return separator.join(result)


def first_value(
    row: dict[str, str],
    columns: tuple[str, ...],
) -> str:
    """Return the first non-empty value from matching column names."""
    normalized_columns = {key.casefold(): key for key in row}

    for candidate in columns:
        actual = normalized_columns.get(candidate.casefold())

        if actual is None:
            continue

        value = clean_text(row.get(actual, ""))

        if value:
            return value

    return ""


def collect_values(
    row: dict[str, str],
    columns: tuple[str, ...],
) -> list[str]:
    """Collect values from all matching columns."""
    normalized_columns = {key.casefold(): key for key in row}

    values: list[str] = []

    for candidate in columns:
        actual = normalized_columns.get(candidate.casefold())

        if actual is None:
            continue

        values.extend(split_contact_values(row.get(actual, "")))

    return values


def load_csv(path: Path) -> list[dict[str, str]]:
    """Load a CSV file."""
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        return list(csv.DictReader(handle))


def write_csv(
    path: Path,
    rows: list[dict[str, str]],
) -> None:
    """Write CSV with stable field order."""
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not rows:
        # Still create a headerless file only when no fields exist.
        path.write_text(
            "",
            encoding="utf-8",
        )
        return

    fields = list(dict.fromkeys(key for row in rows for key in row))

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


def extract_company_identity(
    row: dict[str, str],
) -> tuple[str, str]:
    """Return normalized company name and domain."""
    company = first_value(
        row,
        COMPANY_COLUMNS,
    )

    domain = normalize_domain(
        first_value(
            row,
            DOMAIN_COLUMNS,
        )
    )

    if not domain:
        domain = normalize_domain(
            first_value(
                row,
                URL_COLUMNS,
            )
        )

    return (
        normalize_key(company),
        domain,
    )


def extract_contact_record(
    row: dict[str, str],
) -> dict[str, str]:
    """Extract normalized public company contacts from a Phase 3 row."""
    company_name = first_value(
        row,
        COMPANY_COLUMNS,
    )

    domain = normalize_domain(
        first_value(
            row,
            DOMAIN_COLUMNS,
        )
    )

    source_url = first_value(
        row,
        URL_COLUMNS,
    )

    if not domain:
        domain = normalize_domain(source_url)

    emails: list[str] = []

    for value in collect_values(
        row,
        EMAIL_COLUMNS,
    ):
        value = clean_text(value).lower()

        if valid_email(value):
            emails.append(value)

    phones: list[str] = []

    for value in collect_values(
        row,
        PHONE_COLUMNS,
    ):
        normalized = normalize_phone(value)

        if normalized:
            phones.append(normalized)

    contact_links = collect_values(
        row,
        CONTACT_LINK_COLUMNS,
    )

    return {
        "company_name": company_name,
        "company_domain": domain,
        "company_email": unique_join(emails),
        "company_phone": unique_join(phones),
        "contact_source_url": source_url,
        "contact_page_url": unique_join(contact_links),
    }


def build_contact_index(
    rows: list[dict[str, str]],
) -> dict[tuple[str, str], dict[str, str]]:
    """
    Aggregate contact information by company.

    Matching uses:
        company name + domain

    If a company name is missing, domain alone is used.
    """
    index: dict[
        tuple[str, str],
        dict[str, str],
    ] = {}

    for raw_row in rows:
        record = extract_contact_record(raw_row)

        company_key = normalize_key(record["company_name"])

        domain_key = normalize_domain(record["company_domain"])

        if not company_key and not domain_key:
            continue

        key = (
            company_key,
            domain_key,
        )

        existing = index.get(
            key,
            {
                "company_name": record["company_name"],
                "company_domain": record["company_domain"],
                "company_email": "",
                "company_phone": "",
                "contact_source_url": "",
                "contact_page_url": "",
            },
        )

        existing["company_email"] = unique_join(
            (
                split_contact_values(existing["company_email"])
                + split_contact_values(record["company_email"])
            )
        )

        existing["company_phone"] = unique_join(
            (
                split_contact_values(existing["company_phone"])
                + split_contact_values(record["company_phone"])
            )
        )

        if not existing["contact_source_url"]:
            existing["contact_source_url"] = record["contact_source_url"]

        existing["contact_page_url"] = unique_join(
            (
                split_contact_values(existing["contact_page_url"])
                + split_contact_values(record["contact_page_url"])
            )
        )

        if not existing["company_name"]:
            existing["company_name"] = record["company_name"]

        if not existing["company_domain"]:
            existing["company_domain"] = record["company_domain"]

        index[key] = existing

    return index


def find_contact_for_lead(
    row: dict[str, str],
    contact_index: dict[
        tuple[str, str],
        dict[str, str],
    ],
) -> dict[str, str] | None:
    """Find the best company contact record for a lead."""
    company_key = normalize_key(row.get("company_name", ""))

    domain_key = normalize_domain(row.get("company_domain", ""))

    exact_key = (
        company_key,
        domain_key,
    )

    if exact_key in contact_index:
        return contact_index[exact_key]

    # Fallback: match by company name only.
    for key, value in contact_index.items():
        if company_key and key[0] == company_key:
            return value

    # Fallback: match by domain only.
    for key, value in contact_index.items():
        if domain_key and key[1] == domain_key:
            return value

    return None


def enrich_lead_row(
    row: dict[str, str],
    contact: dict[str, str] | None,
) -> dict[str, str]:
    """Add public company contact fields to a lead."""
    result = dict(row)

    result["company_email"] = ""
    result["company_phone"] = ""
    result["contact_source_url"] = ""
    result["contact_page_url"] = ""
    result["contact_status"] = "NOT_FOUND"
    result["contact_confidence"] = "LOW"

    if contact is None:
        return result

    result["company_email"] = contact.get(
        "company_email",
        "",
    )

    result["company_phone"] = contact.get(
        "company_phone",
        "",
    )

    result["contact_source_url"] = contact.get(
        "contact_source_url",
        "",
    )

    result["contact_page_url"] = contact.get(
        "contact_page_url",
        "",
    )

    if result["company_email"] or result["company_phone"]:
        result["contact_status"] = "FOUND"
        result["contact_confidence"] = "HIGH"
    else:
        result["contact_status"] = "SOURCE_FOUND"
        result["contact_confidence"] = "MEDIUM"

    return result


def aggregate_output_rows(
    rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Deduplicate identical final lead rows."""
    seen: set[tuple[str, str, str]] = set()

    result: list[dict[str, str]] = []

    for row in rows:
        key = (
            normalize_key(row.get("company_name", "")),
            normalize_key(row.get("person_name", "")),
            normalize_key(row.get("designation", "")),
        )

        if key in seen:
            continue

        seen.add(key)
        result.append(row)

    return result


def build_company_contact_output(
    rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Build company-level contact output."""
    grouped: dict[
        tuple[str, str],
        dict[str, str],
    ] = {}

    for row in rows:
        company = clean_text(row.get("company_name", ""))

        domain = normalize_domain(row.get("company_domain", ""))

        key = (
            normalize_key(company),
            domain,
        )

        if key not in grouped:
            grouped[key] = {
                "company_name": company,
                "company_domain": domain,
                "company_email": "",
                "company_phone": "",
                "contact_source_url": "",
                "contact_page_url": "",
                "contact_status": "NOT_FOUND",
                "contact_confidence": "LOW",
            }

        record = grouped[key]

        record["company_email"] = unique_join(
            split_contact_values(record["company_email"])
            + split_contact_values(row.get("company_email", ""))
        )

        record["company_phone"] = unique_join(
            split_contact_values(record["company_phone"])
            + split_contact_values(row.get("company_phone", ""))
        )

        record["contact_source_url"] = record["contact_source_url"] or row.get(
            "contact_source_url",
            "",
        )

        record["contact_page_url"] = unique_join(
            split_contact_values(record["contact_page_url"])
            + split_contact_values(row.get("contact_page_url", ""))
        )

    result = list(grouped.values())

    for row in result:
        if row["company_email"] or row["company_phone"]:
            row["contact_status"] = "FOUND"
            row["contact_confidence"] = "HIGH"
        else:
            row["contact_status"] = "NOT_FOUND"
            row["contact_confidence"] = "LOW"

    result.sort(
        key=lambda row: (
            row["company_name"].casefold(),
            row["company_domain"].casefold(),
        )
    )

    return result


def main() -> None:
    print("Cost policy:")
    print("Google Places API : NOT USED")
    print("Google Search API : NOT USED")
    print("Paid API          : NOT USED")
    print("Proxy             : NOT USED")
    print("Scraping service  : NOT USED")

    print("\n============================================================")
    print("PHASE 6.1 - PUBLIC CONTACT MERGE")
    print("============================================================")

    master_rows = load_csv(MASTER_FILE)

    page_contact_rows = load_csv(PAGE_CONTACTS_FILE)

    print(f"\nFinal lead records loaded : " f"{len(master_rows)}")

    print(f"Phase 3 contact rows      : " f"{len(page_contact_rows)}")

    contact_index = build_contact_index(page_contact_rows)

    print(f"Company contact groups    : " f"{len(contact_index)}")

    enriched_rows: list[dict[str, str]] = []

    for row in master_rows:
        contact = find_contact_for_lead(
            row,
            contact_index,
        )

        enriched_rows.append(
            enrich_lead_row(
                row,
                contact,
            )
        )

    enriched_rows = aggregate_output_rows(enriched_rows)

    cxo_rows = [row for row in enriched_rows if row.get("leadership_type") == "CXO"]

    board_rows = [row for row in enriched_rows if row.get("leadership_type") == "Board"]

    executive_rows = [
        row
        for row in enriched_rows
        if row.get("leadership_type") == "Executive Leadership"
    ]

    company_rows = build_company_contact_output(enriched_rows)

    write_csv(
        MASTER_WITH_CONTACTS,
        enriched_rows,
    )

    write_csv(
        CXO_WITH_CONTACTS,
        cxo_rows,
    )

    write_csv(
        BOARD_WITH_CONTACTS,
        board_rows,
    )

    write_csv(
        EXECUTIVE_WITH_CONTACTS,
        executive_rows,
    )

    write_csv(
        COMPANY_CONTACTS_WITH_CONTACTS,
        company_rows,
    )

    found_emails = sum(bool(row.get("company_email")) for row in enriched_rows)

    found_phones = sum(bool(row.get("company_phone")) for row in enriched_rows)

    contact_found = sum(row.get("contact_status") == "FOUND" for row in enriched_rows)

    summary = [
        {
            "metric": "final_lead_records",
            "value": str(len(enriched_rows)),
            "detail": "",
        },
        {
            "metric": "company_contact_groups",
            "value": str(len(company_rows)),
            "detail": "",
        },
        {
            "metric": "leads_with_email",
            "value": str(found_emails),
            "detail": "",
        },
        {
            "metric": "leads_with_phone",
            "value": str(found_phones),
            "detail": "",
        },
        {
            "metric": "leads_with_any_contact",
            "value": str(contact_found),
            "detail": "",
        },
        {
            "metric": "cxo_records",
            "value": str(len(cxo_rows)),
            "detail": "",
        },
        {
            "metric": "board_records",
            "value": str(len(board_rows)),
            "detail": "",
        },
        {
            "metric": "executive_leadership_records",
            "value": str(len(executive_rows)),
            "detail": "",
        },
    ]

    write_csv(
        SUMMARY_FILE,
        summary,
    )

    print("\nRESULT")
    print(f"Final lead records : {len(enriched_rows)}")
    print(f"Leads with email   : {found_emails}")
    print(f"Leads with phone   : {found_phones}")
    print(f"Leads with contact : {contact_found}")
    print(f"CXO                : {len(cxo_rows)}")
    print(f"Board              : {len(board_rows)}")
    print(f"Executive          : {len(executive_rows)}")

    print("\nFILES")
    print(f"Master     : {MASTER_WITH_CONTACTS}")
    print(f"CXO        : {CXO_WITH_CONTACTS}")
    print(f"Board      : {BOARD_WITH_CONTACTS}")
    print(f"Executive  : {EXECUTIVE_WITH_CONTACTS}")
    print(f"Companies  : {COMPANY_CONTACTS_WITH_CONTACTS}")
    print(f"Summary    : {SUMMARY_FILE}")

    print("\n============================================================")
    print("PHASE 6.1 COMPLETE")
    print("============================================================")

    print("\nPublic company contact merge completed.")


if __name__ == "__main__":
    main()
