"""
CXO GOOGLE SCRAPER
==================

PHASE 3.1

Public Contact Information Extraction

Input:
    output/website_pages.csv

Output:
    output/page_contacts.csv
"""

from __future__ import annotations

import csv
import re
import time
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

import config

# ============================================================
# HTTP SESSION
# ============================================================

session = requests.Session()

session.headers.update(config.HEADERS)


# ============================================================
# TEXT
# ============================================================


def clean_text(value: str) -> str:
    """Normalize whitespace."""

    if not value:
        return ""

    return re.sub(
        r"\s+",
        " ",
        value,
    ).strip()


# ============================================================
# DOMAIN
# ============================================================


def extract_domain(url: str) -> str:
    """Extract normalized domain."""

    if not url:
        return ""

    try:
        parsed = urlparse(url)
    except (TypeError, ValueError):
        return ""

    return (parsed.hostname or "").lower().removeprefix("www.")


# ============================================================
# EMAIL
# ============================================================

EMAIL_PATTERN = re.compile(
    r"""
    (?<![\w.+-])
    [A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+
    @
    [A-Za-z0-9-]+
    (?:\.[A-Za-z0-9-]+)+
    (?![\w.-])
    """,
    re.VERBOSE,
)


def extract_emails(
    text: str,
) -> list[str]:
    """Extract visible email addresses."""

    if not text:
        return []

    emails = []

    seen = set()

    for email in EMAIL_PATTERN.findall(text):

        email = email.lower().strip()

        domain = email.split("@")[-1]

        if domain in (config.EXCLUDED_EMAIL_DOMAINS):
            continue

        if email in seen:
            continue

        seen.add(email)

        emails.append(email)

        if len(emails) >= (config.MAX_EMAILS_PER_PAGE):
            break

    return emails


# ============================================================
# PHONE
# ============================================================

PHONE_PATTERN = re.compile(
    r"""
    (?<!\w)
    (?:
        \+?\d{1,3}
        [\s().-]*
    )?
    (?:\(?\d{2,5}\)?)
    [\s.-]*
    \d{3,5}
    [\s.-]*
    \d{3,5}
    (?!\w)
    """,
    re.VERBOSE,
)


def normalize_phone(
    value: str,
) -> str:
    """Normalize phone whitespace."""

    return clean_text(value)


def is_probable_phone(
    value: str,
) -> bool:
    """Reject obviously invalid numeric strings."""

    digits = re.sub(
        r"\D",
        "",
        value,
    )

    return 7 <= len(digits) <= 15


def extract_phone_numbers(
    text: str,
) -> list[str]:
    """Extract probable phone numbers."""

    if not text:
        return []

    phones = []

    seen = set()

    for phone in PHONE_PATTERN.findall(text):

        phone = normalize_phone(phone)

        if not is_probable_phone(phone):
            continue

        digits = re.sub(
            r"\D",
            "",
            phone,
        )

        if digits in seen:
            continue

        seen.add(digits)

        phones.append(phone)

        if len(phones) >= (config.MAX_PHONES_PER_PAGE):
            break

    return phones


# ============================================================
# HTML CLEANING
# ============================================================


def clean_page_html(
    html: str,
) -> BeautifulSoup:
    """Remove non-content HTML elements."""

    soup = BeautifulSoup(
        html,
        "lxml",
    )

    for element in soup(
        [
            "script",
            "style",
            "noscript",
            "svg",
            "canvas",
            "iframe",
            "template",
        ]
    ):
        element.decompose()

    return soup


# ============================================================
# PAGE TITLE
# ============================================================


def extract_page_title(
    soup: BeautifulSoup,
) -> str:
    """Extract page title."""

    if not soup.title:
        return ""

    return clean_text(
        soup.title.get_text(
            " ",
            strip=True,
        )
    )


# ============================================================
# VISIBLE TEXT
# ============================================================


def extract_visible_text(
    soup: BeautifulSoup,
) -> str:
    """Extract visible page text."""

    text = soup.get_text(
        " ",
        strip=True,
    )

    text = clean_text(text)

    if len(text) > (config.MAX_PAGE_TEXT_LENGTH):
        text = text[: config.MAX_PAGE_TEXT_LENGTH]

    return text


# ============================================================
# MAILTO EXTRACTION
# ============================================================


def extract_mailto_emails(soup: BeautifulSoup) -> list[str]:
    """Extract valid email addresses from mailto links."""
    emails: list[str] = []

    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href", "")).strip()

        if not href:
            continue

        if not href.casefold().startswith("mailto:"):
            continue

        email = href.removeprefix("mailto:").strip()

        # Remove optional query parameters such as ?subject=...
        email = email.split("?", 1)[0].strip()

        if not email:
            continue

        if "@" not in email:
            continue

        emails.append(email)

    return list(dict.fromkeys(emails))


# ============================================================
# TEL EXTRACTION
# ============================================================


def extract_tel_numbers(soup: BeautifulSoup) -> list[str]:
    """Extract valid phone numbers from tel links."""
    phones: list[str] = []

    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href", "")).strip()

        if not href:
            continue

        if not href.casefold().startswith("tel:"):
            continue

        phone = href.removeprefix("tel:").strip()

        # Remove optional parameters such as ;ext=123.
        phone = phone.split(";", 1)[0].strip()

        if not phone:
            continue

        digits = re.sub(r"\D", "", phone)

        if len(digits) < 7:
            continue

        phones.append(phone)

    return list(dict.fromkeys(phones))


# ============================================================
# CONTACT PAGE DETECTION
# ============================================================


def is_contact_page(
    page_url: str,
    page_type: str,
) -> bool:
    """
    Determine whether the page itself is a contact page.

    This is deliberately based on the page URL/type,
    NOT on whether a footer contains a Contact link.
    """

    if page_type == "contact":
        return True

    path = urlparse(page_url).path.lower()

    segments = [segment for segment in path.split("/") if segment]

    return any(
        segment
        in {
            "contact",
            "contact-us",
            "contactus",
            "get-in-touch",
            "reach-us",
            "talk-to-us",
        }
        for segment in segments
    )


# ============================================================
# CONTACT LINKS
# ============================================================


def extract_contact_links(
    soup: BeautifulSoup,
    base_url: str,
) -> list[str]:
    """
    Extract actual contact-related links.

    This does NOT mean the page has contact information.
    It only records that a contact destination exists.
    """

    links = []

    seen = set()

    for anchor in soup.find_all(
        "a",
        href=True,
    ):

        href = anchor.get(
            "href",
            "",
        ).strip()

        anchor_text = clean_text(
            anchor.get_text(
                " ",
                strip=True,
            )
        ).lower()

        if not href:
            continue

        lower_href = href.lower()

        # ----------------------------------------------------
        # Skip mailto/tel here because they are stored
        # separately.
        # ----------------------------------------------------

        if lower_href.startswith(
            (
                "mailto:",
                "tel:",
            )
        ):
            continue

        combined = f"{lower_href} " f"{anchor_text}"

        if not any(keyword in combined for keyword in (config.CONTACT_LINK_KEYWORDS)):
            continue

        absolute_url = urljoin(
            base_url,
            href,
        )

        absolute_url, _ = urldefrag(absolute_url)

        if absolute_url in seen:
            continue

        seen.add(absolute_url)

        links.append(absolute_url)

        if len(links) >= (config.MAX_CONTACT_LINKS_PER_PAGE):
            break

    return links


# ============================================================
# FETCH
# ============================================================


def fetch_page(
    url: str,
) -> tuple[
    requests.Response | None,
    str,
]:
    """Download public HTML page."""

    try:
        response = session.get(
            url,
            timeout=config.REQUEST_TIMEOUT,
            allow_redirects=True,
        )
    except requests.RequestException as error:
        print(f"    [ERROR] {error}")
        return None, ""

    content_type = response.headers.get(
        "Content-Type",
        "",
    ).lower()

    if "text/html" not in content_type:
        return response, ""

    return response, response.text


# ============================================================
# PROCESS PAGE
# ============================================================


def process_page(
    page: dict,
) -> dict:
    """Extract public contact information."""

    page_url = page.get(
        "page_url",
        "",
    )

    result = {
        "company_name": page.get(
            "company_name",
            "",
        ),
        "company_domain": page.get(
            "company_domain",
            "",
        ),
        "page_url": page_url,
        "page_type": page.get(
            "page_type",
            "",
        ),
        "score": page.get(
            "score",
            "",
        ),
        "page_title": "",
        "final_url": "",
        "status_code": "",
        "emails": "",
        "mailto_emails": "",
        "phone_numbers": "",
        "tel_numbers": "",
        "contact_page": "NO",
        "contact_links": "",
        "page_text": "",
        "error": "",
    }

    if not page_url:
        result["error"] = "Page URL is empty"
        return result

    response, html = fetch_page(page_url)

    if not response:
        result["error"] = "Page request failed"
        return result

    result["status_code"] = response.status_code

    result["final_url"] = response.url

    if not html:
        result["error"] = "Page did not return HTML"
        return result

    soup = clean_page_html(html)

    result["page_title"] = extract_page_title(soup)

    page_text = extract_visible_text(soup)

    result["page_text"] = page_text

    # --------------------------------------------------------
    # Visible email addresses
    # --------------------------------------------------------

    visible_emails = extract_emails(page_text)

    result["emails"] = "; ".join(visible_emails)

    # --------------------------------------------------------
    # Explicit mailto addresses
    # --------------------------------------------------------

    mailto_emails = extract_mailto_emails(soup)

    result["mailto_emails"] = "; ".join(mailto_emails)

    # --------------------------------------------------------
    # Visible phone numbers
    # --------------------------------------------------------

    visible_phones = extract_phone_numbers(page_text)

    result["phone_numbers"] = "; ".join(visible_phones)

    # --------------------------------------------------------
    # Explicit tel links
    # --------------------------------------------------------

    tel_numbers = extract_tel_numbers(soup)

    result["tel_numbers"] = "; ".join(tel_numbers)

    # --------------------------------------------------------
    # Actual contact page
    # --------------------------------------------------------

    if is_contact_page(
        page_url,
        page.get(
            "page_type",
            "",
        ),
    ):
        result["contact_page"] = "YES"

    # --------------------------------------------------------
    # Contact destinations
    # --------------------------------------------------------

    contact_links = extract_contact_links(
        soup,
        response.url,
    )

    result["contact_links"] = "; ".join(contact_links)

    return result


# ============================================================
# LOAD DISCOVERED PAGES
# ============================================================


def load_pages() -> list[dict]:
    """Load Phase 2 page discovery output."""

    input_file = config.WEBSITE_PAGES_OUTPUT_FILE

    if not input_file.exists():
        print("[ERROR] " "website_pages.csv not found:")
        print(input_file)
        return []

    try:
        with open(
            input_file,
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as file:

            reader = csv.DictReader(file)

            if not reader.fieldnames:
                print("[ERROR] " "CSV has no header.")
                return []

            return list(reader)

    except OSError as error:
        print("[ERROR] " "Could not read website pages:")
        print(error)
        return []


# ============================================================
# SAVE
# ============================================================


def save_results(
    results: list[dict],
) -> None:
    """Save Phase 3 results."""

    config.OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_file = config.PAGE_CONTACTS_OUTPUT_FILE

    fieldnames = [
        "company_name",
        "company_domain",
        "page_url",
        "page_type",
        "score",
        "page_title",
        "final_url",
        "status_code",
        "emails",
        "mailto_emails",
        "phone_numbers",
        "tel_numbers",
        "contact_page",
        "contact_links",
        "page_text",
        "error",
    ]

    with open(
        output_file,
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        writer.writerows(results)

    print()
    print("=" * 70)
    print("CONTACT EXTRACTION OUTPUT")
    print("=" * 70)

    print(f"File: {output_file}")

    print(f"Pages processed: " f"{len(results)}")


# ============================================================
# SUMMARY
# ============================================================


def display_summary(
    results: list[dict],
) -> None:
    """Display Phase 3 summary."""

    print()
    print("=" * 70)
    print("PHASE 3 RESULTS")
    print("=" * 70)

    if not results:
        print("No pages processed.")
        return

    successful_pages = sum(
        1
        for result in results
        if str(
            result.get(
                "status_code",
                "",
            )
        ).startswith(
            (
                "2",
                "3",
            )
        )
    )

    pages_with_email = sum(
        bool(
            result.get(
                "emails",
                "",
            )
            or result.get(
                "mailto_emails",
                "",
            )
        )
        for result in results
    )

    pages_with_phone = sum(
        bool(
            result.get(
                "phone_numbers",
                "",
            )
            or result.get(
                "tel_numbers",
                "",
            )
        )
        for result in results
    )

    contact_pages = sum(
        result.get(
            "contact_page",
            "",
        )
        == "YES"
        for result in results
    )

    pages_with_contact_link = sum(
        bool(
            result.get(
                "contact_links",
                "",
            )
        )
        for result in results
    )

    print(f"Pages processed          : " f"{len(results)}")

    print(f"Successful pages         : " f"{successful_pages}")

    print(f"Pages with email         : " f"{pages_with_email}")

    print(f"Pages with phone         : " f"{pages_with_phone}")

    print(f"Actual contact pages    : " f"{contact_pages}")

    print(f"Pages linking to contact: " f"{pages_with_contact_link}")


# ============================================================
# MAIN
# ============================================================


def main() -> None:
    """Run Phase 3."""

    print()
    print("=" * 70)
    print("CXO GOOGLE SCRAPER")
    print("PHASE 3.1 - ACCURATE PUBLIC CONTACT EXTRACTION")
    print("=" * 70)

    print()
    print("Cost policy:")

    print("Google Places API : NOT USED")

    print("Google Search API : NOT USED")

    print("Paid API          : NOT USED")

    print("Proxy             : NOT USED")

    print("Scraping service  : NOT USED")

    pages = load_pages()

    if not pages:
        print("[ERROR] " "No discovered pages available.")
        print("Run Phase 2.3 first.")
        return

    print()
    print(f"Pages loaded: " f"{len(pages)}")

    results = []

    for index, page in enumerate(
        pages,
        start=1,
    ):

        print()
        print("-" * 70)

        print(f"PAGE " f"{index}/" f"{len(pages)}")

        print(f"Company: " f"{page.get('company_name', '')}")

        print(f"Type: " f"{page.get('page_type', '')}")

        print(f"URL: " f"{page.get('page_url', '')}")

        try:
            result = process_page(page)
        except (
            AttributeError,
            IndexError,
            KeyError,
            TypeError,
            ValueError,
        ) as error:
            print(
                "[WARNING] Page skipped due to extraction error: "
                f"{type(error).__name__}: {error}"
            )
            continue

        results.append(result)

        if index < len(pages):
            time.sleep(config.REQUEST_DELAY)

    display_summary(results)

    save_results(results)

    print()
    print("=" * 70)
    print("PHASE 3.1 COMPLETE")
    print("=" * 70)

    print()
    print("Accurate public contact extraction completed.")

    print()
    print("Next phase:")

    print("Phase 4 - CXO / Leadership Identification")


if __name__ == "__main__":
    main()
