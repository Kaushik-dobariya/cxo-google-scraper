"""
CXO GOOGLE SCRAPER
==================

PHASE 4.1
---------

Precision CXO / Leadership Identification

Purpose
-------

Extract publicly visible senior leadership information from
company leadership / management pages.

This version prioritizes precision over recall.

Cost policy
-----------

Google Places API : NOT USED
Google Search API : NOT USED
Paid API          : NOT USED
Proxy             : NOT USED
Scraping service  : NOT USED

Input
-----

output/website_pages.csv

Only:

    leadership
    management

pages are processed.

Output
------

output/cxo/cxo_people.csv

Important
---------

This module does NOT guess email addresses.

It does NOT generate person names from unrelated page text.

It only creates a candidate when the person's name and
leadership designation have a strong local relationship
inside the page DOM.
"""

from __future__ import annotations

import csv
import json
import re
import time
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup, Tag

import config

# ============================================================
# HTTP SESSION
# ============================================================

session = requests.Session()

session.headers.update(config.HEADERS)


# ============================================================
# OUTPUT
# ============================================================

CXO_OUTPUT_DIR = config.OUTPUT_DIR / "cxo"

CXO_OUTPUT_FILE = CXO_OUTPUT_DIR / "cxo_people.csv"


# ============================================================
# ROLE PATTERNS
# ============================================================

ROLE_PATTERNS = (
    # --------------------------------------------------------
    # CEO DESIGNATE
    # --------------------------------------------------------
    (
        re.compile(
            r"\bchief\s+executive\s+officer\s+designate\b",
            re.IGNORECASE,
        ),
        "Chief Executive Officer Designate",
        "CXO",
    ),
    (
        re.compile(
            r"\bceo\s+designate\b",
            re.IGNORECASE,
        ),
        "CEO Designate",
        "CXO",
    ),
    # --------------------------------------------------------
    # CEO
    # --------------------------------------------------------
    (
        re.compile(
            r"\bchief\s+executive\s+officer\b",
            re.IGNORECASE,
        ),
        "Chief Executive Officer",
        "CXO",
    ),
    (
        re.compile(
            r"\bceo\b",
            re.IGNORECASE,
        ),
        "CEO",
        "CXO",
    ),
    # --------------------------------------------------------
    # CTO
    # --------------------------------------------------------
    (
        re.compile(
            r"\bchief\s+technology\s+officer\b",
            re.IGNORECASE,
        ),
        "Chief Technology Officer",
        "CXO",
    ),
    (
        re.compile(
            r"\bcto\b",
            re.IGNORECASE,
        ),
        "CTO",
        "CXO",
    ),
    # --------------------------------------------------------
    # CIO
    # --------------------------------------------------------
    (
        re.compile(
            r"\bchief\s+information\s+officer\b",
            re.IGNORECASE,
        ),
        "Chief Information Officer",
        "CXO",
    ),
    (
        re.compile(
            r"\bcio\b",
            re.IGNORECASE,
        ),
        "CIO",
        "CXO",
    ),
    # --------------------------------------------------------
    # CFO
    # --------------------------------------------------------
    (
        re.compile(
            r"\bchief\s+financial\s+officer\b",
            re.IGNORECASE,
        ),
        "Chief Financial Officer",
        "CXO",
    ),
    (
        re.compile(
            r"\bcfo\b",
            re.IGNORECASE,
        ),
        "CFO",
        "CXO",
    ),
    # --------------------------------------------------------
    # COO
    # --------------------------------------------------------
    (
        re.compile(
            r"\bchief\s+operating\s+officer\b",
            re.IGNORECASE,
        ),
        "Chief Operating Officer",
        "CXO",
    ),
    (
        re.compile(
            r"\bcoo\b",
            re.IGNORECASE,
        ),
        "COO",
        "CXO",
    ),
    # --------------------------------------------------------
    # CMO
    # --------------------------------------------------------
    (
        re.compile(
            r"\bchief\s+marketing\s+officer\b",
            re.IGNORECASE,
        ),
        "Chief Marketing Officer",
        "CXO",
    ),
    (
        re.compile(
            r"\bcmo\b",
            re.IGNORECASE,
        ),
        "CMO",
        "CXO",
    ),
    # --------------------------------------------------------
    # CHRO
    # --------------------------------------------------------
    (
        re.compile(
            r"\bchief\s+human\s+resources\s+officer\b",
            re.IGNORECASE,
        ),
        "Chief Human Resources Officer",
        "CXO",
    ),
    (
        re.compile(
            r"\bchro\b",
            re.IGNORECASE,
        ),
        "CHRO",
        "CXO",
    ),
    # --------------------------------------------------------
    # CHIEF PEOPLE OFFICER
    # --------------------------------------------------------
    (
        re.compile(
            r"\bchief\s+people\s+officer\b",
            re.IGNORECASE,
        ),
        "Chief People Officer",
        "CXO",
    ),
    # --------------------------------------------------------
    # CHIEF DATA OFFICER
    # --------------------------------------------------------
    (
        re.compile(
            r"\bchief\s+data\s+officer\b",
            re.IGNORECASE,
        ),
        "Chief Data Officer",
        "CXO",
    ),
    # --------------------------------------------------------
    # CHIEF DIGITAL OFFICER
    # --------------------------------------------------------
    (
        re.compile(
            r"\bchief\s+digital\s+officer\b",
            re.IGNORECASE,
        ),
        "Chief Digital Officer",
        "CXO",
    ),
    # --------------------------------------------------------
    # CHIEF STRATEGY / RISK
    # --------------------------------------------------------
    (
        re.compile(
            r"\bchief\s+strategy\s+and\s+risk\s+officer\b",
            re.IGNORECASE,
        ),
        "Chief Strategy and Risk Officer",
        "CXO",
    ),
    (
        re.compile(
            r"\bchief\s+strategy\s+officer\b",
            re.IGNORECASE,
        ),
        "Chief Strategy Officer",
        "CXO",
    ),
    # --------------------------------------------------------
    # CHIEF LEGAL OFFICER
    # --------------------------------------------------------
    (
        re.compile(
            r"\bchief\s+legal\s+officer\b",
            re.IGNORECASE,
        ),
        "Chief Legal Officer",
        "CXO",
    ),
    # --------------------------------------------------------
    # CHIEF COMPLIANCE OFFICER
    # --------------------------------------------------------
    (
        re.compile(
            r"\bchief\s+compliance\s+officer\b",
            re.IGNORECASE,
        ),
        "Chief Compliance Officer",
        "CXO",
    ),
    # --------------------------------------------------------
    # CHIEF SUSTAINABILITY OFFICER
    # --------------------------------------------------------
    (
        re.compile(
            r"\bchief\s+sustainability\s+officer\b",
            re.IGNORECASE,
        ),
        "Chief Sustainability Officer",
        "CXO",
    ),
    # --------------------------------------------------------
    # MANAGING DIRECTOR
    # --------------------------------------------------------
    (
        re.compile(
            r"\bmanaging\s+director\b",
            re.IGNORECASE,
        ),
        "Managing Director",
        "Executive Leadership",
    ),
    # --------------------------------------------------------
    # EXECUTIVE CHAIRMAN
    # --------------------------------------------------------
    (
        re.compile(
            r"\bexecutive\s+chairman\b",
            re.IGNORECASE,
        ),
        "Executive Chairman",
        "Board",
    ),
    # --------------------------------------------------------
    # VICE CHAIRMAN
    # --------------------------------------------------------
    (
        re.compile(
            r"\bvice\s+chairman\b",
            re.IGNORECASE,
        ),
        "Vice Chairman",
        "Board",
    ),
    # --------------------------------------------------------
    # CHAIRMAN
    # --------------------------------------------------------
    (
        re.compile(
            r"\bchairman\b",
            re.IGNORECASE,
        ),
        "Chairman",
        "Board",
    ),
    # --------------------------------------------------------
    # EXECUTIVE DIRECTOR
    # --------------------------------------------------------
    (
        re.compile(
            r"\bexecutive\s+director\b",
            re.IGNORECASE,
        ),
        "Executive Director",
        "Executive Leadership",
    ),
    # --------------------------------------------------------
    # LEAD INDEPENDENT DIRECTOR
    # --------------------------------------------------------
    (
        re.compile(
            r"\blead\s+independent\s+director\b",
            re.IGNORECASE,
        ),
        "Lead Independent Director",
        "Board",
    ),
    # --------------------------------------------------------
    # INDEPENDENT DIRECTOR
    # --------------------------------------------------------
    (
        re.compile(
            r"\bindependent\s+director\b",
            re.IGNORECASE,
        ),
        "Independent Director",
        "Board",
    ),
    # --------------------------------------------------------
    # NON-EXECUTIVE DIRECTOR
    # --------------------------------------------------------
    (
        re.compile(
            r"\bnon[-\s]?executive\s+director\b",
            re.IGNORECASE,
        ),
        "Non-Executive Director",
        "Board",
    ),
    # --------------------------------------------------------
    # PRESIDENT
    # --------------------------------------------------------
    (
        re.compile(
            r"\bpresident\b",
            re.IGNORECASE,
        ),
        "President",
        "Executive Leadership",
    ),
    # --------------------------------------------------------
    # FOUNDER
    # --------------------------------------------------------
    (
        re.compile(
            r"\bco[-\s]?founder\b",
            re.IGNORECASE,
        ),
        "Co-Founder",
        "Founder",
    ),
    (
        re.compile(
            r"\bfounder\b",
            re.IGNORECASE,
        ),
        "Founder",
        "Founder",
    ),
    # --------------------------------------------------------
    # DIRECTOR
    # --------------------------------------------------------
    (
        re.compile(
            r"\bdirector\b",
            re.IGNORECASE,
        ),
        "Director",
        "Board",
    ),
)


# ============================================================
# GENERIC / INVALID NAME WORDS
# ============================================================

INVALID_NAME_EXACT = {
    "about us",
    "about",
    "leadership",
    "management",
    "management team",
    "leadership team",
    "investors",
    "investor",
    "top results",
    "results",
    "founders",
    "founder",
    "market leadership",
    "functional leadership",
    "our leadership",
    "our management",
    "board",
    "board of directors",
    "directors",
    "read more",
    "read bio",
    "view profile",
    "view bio",
    "profile",
    "careers",
    "contact",
    "contact us",
    "skip to main content",
    "menu",
    "home",
}


INVALID_NAME_PHRASES = {
    "about us",
    "top results",
    "market leadership",
    "functional leadership",
    "skip to",
    "read more",
    "view profile",
    "view bio",
    "investor relations",
    "contact us",
}


# ============================================================
# TEXT CLEANING
# ============================================================


def clean_text(
    value: str,
) -> str:
    """Normalize whitespace."""

    if not value:
        return ""

    return re.sub(
        r"\s+",
        " ",
        value,
    ).strip()


# ============================================================
# ROLE NORMALIZATION
# ============================================================


def classify_role(
    text: str,
) -> tuple[str, str]:
    """
    Return:

        designation
        leadership_type

    based on the first matching role pattern.
    """

    cleaned = clean_text(text)

    if not cleaned:
        return "", ""

    for (
        pattern,
        designation,
        leadership_type,
    ) in ROLE_PATTERNS:

        if pattern.search(cleaned):
            return (
                designation,
                leadership_type,
            )

    return "", ""


# ============================================================
# EXTRACT ACTUAL ROLE TEXT
# ============================================================


def extract_designation(
    text: str,
) -> tuple[str, str]:
    """
    Extract a cleaned designation from text.

    Keeps compound roles such as:

        CEO & Managing Director
        Chief Executive Officer & Managing Director
        CEO Designate
    """

    cleaned = clean_text(text)

    if not cleaned:
        return "", ""

    designation, leadership_type = classify_role(cleaned)

    if not designation:
        return "", ""

    # --------------------------------------------------------
    # Prefer the complete text if it is reasonably short.
    # --------------------------------------------------------

    if len(cleaned) <= 180:
        return (
            cleaned,
            leadership_type,
        )

    return (
        designation,
        leadership_type,
    )


# ============================================================
# NAME NORMALIZATION
# ============================================================


def normalize_person_name(
    value: str,
) -> str:
    """Normalize a candidate person's name."""

    name = clean_text(value)

    name = re.sub(
        r"^(mr|mrs|ms|miss|dr|prof)\.?\s+",
        "",
        name,
        flags=re.IGNORECASE,
    )

    return name.strip(" -–—:|,")


# ============================================================
# NAME VALIDATION
# ============================================================


def is_likely_person_name(
    value: str,
) -> bool:
    """
    Conservative person-name validation.

    False positives are more damaging than missed names
    in this phase.
    """

    name = normalize_person_name(value)

    if not name:
        return False

    lowered = name.lower()

    if lowered in INVALID_NAME_EXACT:
        return False

    if any(phrase in lowered for phrase in INVALID_NAME_PHRASES):
        return False

    if len(name) < 3:
        return False

    if len(name) > 100:
        return False

    words = name.split()

    if len(words) > 7:
        return False

    if "@" in name:
        return False

    if "http" in lowered:
        return False

    if "www." in lowered:
        return False

    if ".com" in lowered:
        return False

    # --------------------------------------------------------
    # Reject text containing obvious navigation words.
    # --------------------------------------------------------

    navigation_words = {
        "home",
        "about",
        "leadership",
        "management",
        "investor",
        "investors",
        "contact",
        "careers",
        "results",
        "menu",
        "search",
        "login",
        "privacy",
        "terms",
    }

    if any(word.lower() in navigation_words for word in words):
        return False

    # --------------------------------------------------------
    # Reject role words.
    # --------------------------------------------------------

    role_words = {
        "chief",
        "executive",
        "officer",
        "ceo",
        "cto",
        "cio",
        "cfo",
        "coo",
        "cmo",
        "chro",
        "president",
        "chairman",
        "director",
        "founder",
        "managing",
        "independent",
        "board",
    }

    if any(word.lower().strip(".,()") in role_words for word in words):
        return False

    # --------------------------------------------------------
    # Reject sentence-like text.
    # --------------------------------------------------------

    sentence_markers = (
        " is ",
        " are ",
        " was ",
        " were ",
        " has ",
        " have ",
        " and ",
        " for ",
        " with ",
        " from ",
        " to ",
    )

    if any(marker in f" {lowered} " for marker in sentence_markers):
        return False

    # --------------------------------------------------------
    # Accept common name characters.
    # --------------------------------------------------------

    return bool(
        re.fullmatch(
            r"[A-Za-zÀ-ÖØ-öø-ÿ0-9.'’&()\-–— ]+",
            name,
        )
    )


# ============================================================
# FETCH PAGE
# ============================================================


def fetch_page(
    url: str,
) -> tuple[
    requests.Response | None,
    str,
]:
    """Fetch public HTML."""

    try:
        response = session.get(
            url,
            timeout=config.REQUEST_TIMEOUT,
            allow_redirects=True,
        )

    except requests.RequestException as error:

        print(f"    [ERROR] {error}")

        return (
            None,
            "",
        )

    content_type = response.headers.get(
        "Content-Type",
        "",
    ).lower()

    if "text/html" not in content_type:
        return (
            response,
            "",
        )

    return (
        response,
        response.text,
    )


# ============================================================
# COMPANY OBJECT
# ============================================================


def company_from_page(
    page: dict,
) -> dict:
    """Build company information."""

    return {
        "company_name": clean_text(
            page.get(
                "company_name",
                "",
            )
        ),
        "company_domain": clean_text(
            page.get(
                "company_domain",
                "",
            )
        ),
    }


# ============================================================
# CANDIDATE CREATION
# ============================================================


def make_candidate(
    company: dict,
    person_name: str,
    designation: str,
    leadership_type: str,
    source_url: str,
    confidence: str,
    extraction_method: str,
) -> dict | None:
    """Create a validated candidate."""

    person_name = normalize_person_name(person_name)

    if not is_likely_person_name(person_name):
        return None

    designation = clean_text(designation)

    if not designation:
        return None

    domain = (
        company.get(
            "company_domain",
            "",
        )
        or urlparse(source_url).hostname
        or ""
    )

    domain = domain.lower().removeprefix("www.")

    return {
        "company_name": clean_text(
            company.get(
                "company_name",
                "",
            )
        ),
        "company_domain": domain,
        "person_name": person_name,
        "designation": designation,
        "leadership_type": leadership_type,
        "confidence": confidence,
        "extraction_method": extraction_method,
        "source_url": source_url,
    }


# ============================================================
# STRATEGY 1
# JSON-LD PERSON DATA
# ============================================================


def extract_json_ld_people(
    soup: BeautifulSoup,
    company: dict,
    source_url: str,
) -> list[dict]:
    """
    Extract Person information from JSON-LD.

    JSON-LD is highly useful because many corporate websites
    publish structured Person data for leadership profiles.
    """

    results = []

    scripts = soup.find_all(
        "script",
        attrs={
            "type": re.compile(
                r"application/ld\+json",
                re.IGNORECASE,
            )
        },
    )

    for script in scripts:

        raw = script.string

        if not raw:
            raw = script.get_text(strip=True)

        if not raw:
            continue

        try:
            data = json.loads(raw)

        except (
            json.JSONDecodeError,
            TypeError,
        ):
            continue

        objects = []

        if isinstance(
            data,
            dict,
        ):
            objects.append(data)

            graph = data.get("@graph")

            if isinstance(
                graph,
                list,
            ):
                objects.extend(graph)

        elif isinstance(
            data,
            list,
        ):
            objects.extend(
                item
                for item in data
                if isinstance(
                    item,
                    dict,
                )
            )

        for item in objects:

            item_type = item.get(
                "@type",
                "",
            )

            if isinstance(
                item_type,
                list,
            ):
                type_values = {str(value).lower() for value in item_type}

            else:
                type_values = {str(item_type).lower()}

            if "person" not in type_values:
                continue

            name = clean_text(
                str(
                    item.get(
                        "name",
                        "",
                    )
                )
            )

            job_title = clean_text(
                str(
                    item.get(
                        "jobTitle",
                        "",
                    )
                )
            )

            if not name or not job_title:
                continue

            designation, leadership_type = extract_designation(job_title)

            if not designation:
                continue

            candidate = make_candidate(
                company,
                name,
                designation,
                leadership_type,
                source_url,
                "HIGH",
                "json_ld",
            )

            if candidate:
                results.append(candidate)

    return results


# ============================================================
# FIND PERSON CANDIDATES INSIDE ELEMENT
# ============================================================


def find_names_in_container(
    container: Tag,
) -> list[str]:
    """
    Find likely person names from semantic elements
    inside a small container.
    """

    names = []

    # --------------------------------------------------------
    # Strong semantic name candidates first.
    # --------------------------------------------------------

    for element in container.find_all(
        [
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "strong",
            "b",
        ]
    ):

        text = clean_text(
            element.get_text(
                " ",
                strip=True,
            )
        )

        if is_likely_person_name(text):
            names.append(text)

    # --------------------------------------------------------
    # Profile links as secondary candidates.
    # --------------------------------------------------------

    if not names:

        for link in container.find_all("a"):

            text = clean_text(
                link.get_text(
                    " ",
                    strip=True,
                )
            )

            if is_likely_person_name(text):
                names.append(text)

    # --------------------------------------------------------
    # Remove duplicates while preserving order.
    # --------------------------------------------------------

    unique = []

    seen = set()

    for name in names:

        key = name.lower()

        if key in seen:
            continue

        seen.add(key)

        unique.append(name)

    return unique


# ============================================================
# FIND ROLE IN CONTAINER
# ============================================================


def find_roles_in_container(
    container: Tag,
) -> list[tuple[str, str]]:
    """
    Find leadership designations inside a small container.
    """

    roles = []

    # --------------------------------------------------------
    # Prefer small text elements.
    # --------------------------------------------------------

    for element in container.find_all(
        [
            "p",
            "span",
            "div",
            "li",
            "small",
            "em",
        ]
    ):

        text = clean_text(
            element.get_text(
                " ",
                strip=True,
            )
        )

        if not text:
            continue

        if len(text) > 180:
            continue

        designation, leadership_type = extract_designation(text)

        if not designation:
            continue

        roles.append(
            (
                designation,
                leadership_type,
            )
        )

    # --------------------------------------------------------
    # Headings can also contain roles.
    # --------------------------------------------------------

    for element in container.find_all(
        [
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
        ]
    ):

        text = clean_text(
            element.get_text(
                " ",
                strip=True,
            )
        )

        designation, leadership_type = extract_designation(text)

        if designation:
            roles.append(
                (
                    designation,
                    leadership_type,
                )
            )

    # --------------------------------------------------------
    # Deduplicate.
    # --------------------------------------------------------

    unique = []

    seen = set()

    for designation, leadership_type in roles:

        key = (
            designation.lower(),
            leadership_type.lower(),
        )

        if key in seen:
            continue

        seen.add(key)

        unique.append(
            (
                designation,
                leadership_type,
            )
        )

    return unique


# ============================================================
# STRATEGY 2
# SEMANTIC PERSON CARDS
# ============================================================


def extract_semantic_cards(
    soup: BeautifulSoup,
    company: dict,
    source_url: str,
) -> list[dict]:
    """
    Extract person-role pairs from small semantic cards.

    Allowed containers:

        article
        li
        small divs
        profile containers

    Large page sections are intentionally rejected.
    """

    results = []

    containers = soup.find_all(
        [
            "article",
            "li",
        ]
    )

    # --------------------------------------------------------
    # Add selected divs with profile-like class names.
    # --------------------------------------------------------

    for div in soup.find_all("div"):

        classes = " ".join(
            div.get(
                "class",
                [],
            )
        ).lower()

        if not classes:
            continue

        if not any(
            token in classes
            for token in (
                "profile",
                "leader",
                "leadership",
                "executive",
                "management",
                "person",
                "team-member",
                "team_member",
                "bio",
            )
        ):
            continue

        containers.append(div)

    # --------------------------------------------------------
    # Process containers.
    # --------------------------------------------------------

    seen_container_ids = set()

    for container in containers:

        container_id = id(container)

        if container_id in seen_container_ids:
            continue

        seen_container_ids.add(container_id)

        text = clean_text(
            container.get_text(
                " ",
                strip=True,
            )
        )

        # ----------------------------------------------------
        # Precision guard.
        # ----------------------------------------------------

        if not text:
            continue

        if len(text) > 500:
            continue

        names = find_names_in_container(container)

        if len(names) != 1:
            continue

        roles = find_roles_in_container(container)

        if len(roles) != 1:
            continue

        name = names[0]

        designation, leadership_type = roles[0]

        candidate = make_candidate(
            company,
            name,
            designation,
            leadership_type,
            source_url,
            "HIGH",
            "semantic_card",
        )

        if candidate:
            results.append(candidate)

    return results


# ============================================================
# STRATEGY 3
# NAME / ROLE SIBLING PAIRS
# ============================================================


def extract_sibling_pairs(
    soup: BeautifulSoup,
    company: dict,
    source_url: str,
) -> list[dict]:
    """
    Detect structures where name and designation are
    adjacent siblings.

    Examples:

        <h3>Mohit Joshi</h3>
        <p>CEO and Managing Director</p>

    or:

        <p>Chief Financial Officer</p>
        <h3>Rohit Anand</h3>
    """

    results = []

    name_elements = soup.find_all(
        [
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "strong",
            "b",
            "a",
        ]
    )

    for element in name_elements:

        name = clean_text(
            element.get_text(
                " ",
                strip=True,
            )
        )

        if not is_likely_person_name(name):
            continue

        parent = element.parent

        if not isinstance(
            parent,
            Tag,
        ):
            continue

        # ----------------------------------------------------
        # Only inspect direct/near siblings.
        # ----------------------------------------------------

        siblings = []

        for sibling in parent.children:

            if not isinstance(
                sibling,
                Tag,
            ):
                continue

            siblings.append(sibling)

        try:
            index = siblings.index(element)
        except ValueError:
            continue

        nearby = siblings[
            max(
                0,
                index - 2,
            ) : index
            + 3
        ]

        role_matches = []

        for sibling in nearby:

            if sibling is element:
                continue

            text = clean_text(
                sibling.get_text(
                    " ",
                    strip=True,
                )
            )

            if not text or len(text) > 180:
                continue

            designation, leadership_type = extract_designation(text)

            if designation:
                role_matches.append(
                    (
                        designation,
                        leadership_type,
                    )
                )

        if len(role_matches) != 1:
            continue

        designation, leadership_type = role_matches[0]

        candidate = make_candidate(
            company,
            name,
            designation,
            leadership_type,
            source_url,
            "HIGH",
            "sibling_pair",
        )

        if candidate:
            results.append(candidate)

    return results


# ============================================================
# STRATEGY 4
# LOCAL PARENT SEARCH
# ============================================================


def extract_local_parent_pairs(
    soup: BeautifulSoup,
    company: dict,
    source_url: str,
) -> list[dict]:
    """
    Search a maximum of three parent levels around a
    role-bearing element.

    This is intentionally narrow.

    It never scans the entire page for names.
    """

    results = []

    role_elements = soup.find_all(
        [
            "p",
            "span",
            "small",
            "div",
            "li",
        ]
    )

    for role_element in role_elements:

        role_text = clean_text(
            role_element.get_text(
                " ",
                strip=True,
            )
        )

        if not role_text:
            continue

        if len(role_text) > 180:
            continue

        designation, leadership_type = extract_designation(role_text)

        if not designation:
            continue

        current = role_element

        for _level in range(3):

            parent = current.parent

            if not isinstance(
                parent,
                Tag,
            ):
                break

            parent_text = clean_text(
                parent.get_text(
                    " ",
                    strip=True,
                )
            )

            if len(parent_text) > 500:
                break

            names = find_names_in_container(parent)

            if len(names) == 1:

                candidate = make_candidate(
                    company,
                    names[0],
                    designation,
                    leadership_type,
                    source_url,
                    "MEDIUM",
                    "local_parent",
                )

                if candidate:
                    results.append(candidate)

                break

            current = parent

    return results


# ============================================================
# DEDUPLICATION
# ============================================================


def deduplicate_candidates(
    candidates: list[dict],
) -> list[dict]:
    """Deduplicate candidates and keep strongest evidence."""

    confidence_rank = {
        "HIGH": 3,
        "MEDIUM": 2,
        "LOW": 1,
    }

    unique = {}

    for candidate in candidates:

        key = (
            candidate["company_domain"].lower(),
            candidate["person_name"].lower(),
            candidate["designation"].lower(),
        )

        existing = unique.get(key)

        if existing is None:

            unique[key] = candidate

            continue

        current_rank = confidence_rank.get(
            candidate["confidence"],
            0,
        )

        existing_rank = confidence_rank.get(
            existing["confidence"],
            0,
        )

        if current_rank > existing_rank:

            unique[key] = candidate

            continue

        # ----------------------------------------------------
        # If confidence is equal, prefer structured data.
        # ----------------------------------------------------

        if (
            current_rank == existing_rank
            and candidate["extraction_method"] == "json_ld"
        ):

            unique[key] = candidate

    return list(unique.values())


# ============================================================
# LOAD INPUT
# ============================================================


def load_leadership_pages() -> list[dict]:
    """Load leadership and management pages only."""

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

                print("[ERROR] " "website_pages.csv " "has no header.")

                return []

            pages = []

            for row in reader:

                page_type = (
                    row.get(
                        "page_type",
                        "",
                    )
                    .strip()
                    .lower()
                )

                if page_type not in {
                    "leadership",
                    "management",
                }:
                    continue

                page_url = clean_text(
                    row.get(
                        "page_url",
                        "",
                    )
                )

                if not page_url:
                    continue

                pages.append(row)

            return pages

    except OSError as error:

        print("[ERROR] " "Could not read website_pages.csv:")

        print(error)

        return []


# ============================================================
# PROCESS ONE PAGE
# ============================================================


def process_page(
    page: dict,
) -> list[dict]:
    """Process one leadership page."""

    company = company_from_page(page)

    company_name = company["company_name"]

    page_type = clean_text(
        page.get(
            "page_type",
            "",
        )
    )

    url = clean_text(
        page.get(
            "page_url",
            "",
        )
    )

    print()
    print(f"Company : {company_name}")

    print(f"Type    : {page_type}")

    print(f"URL     : {url}")

    response, html = fetch_page(url)

    if not response or not html:

        print("Status  : FAILED")

        return []

    print(f"Status  : {response.status_code}")

    soup = BeautifulSoup(
        html,
        "lxml",
    )

    candidates = []

    # --------------------------------------------------------
    # Strategy 1
    # JSON-LD
    # --------------------------------------------------------

    json_ld_candidates = extract_json_ld_people(
        soup,
        company,
        url,
    )

    candidates.extend(json_ld_candidates)

    # --------------------------------------------------------
    # Strategy 2
    # Semantic cards
    # --------------------------------------------------------

    semantic_candidates = extract_semantic_cards(
        soup,
        company,
        url,
    )

    candidates.extend(semantic_candidates)

    # --------------------------------------------------------
    # Strategy 3
    # Sibling pairs
    # --------------------------------------------------------

    sibling_candidates = extract_sibling_pairs(
        soup,
        company,
        url,
    )

    candidates.extend(sibling_candidates)

    # --------------------------------------------------------
    # Strategy 4
    # Narrow local parent search
    # --------------------------------------------------------

    local_candidates = extract_local_parent_pairs(
        soup,
        company,
        url,
    )

    candidates.extend(local_candidates)

    candidates = deduplicate_candidates(candidates)

    print(f"Candidates: " f"{len(candidates)}")

    return candidates


# ============================================================
# SAVE OUTPUT
# ============================================================


def save_results(
    candidates: list[dict],
) -> None:
    """Save CXO CSV."""

    CXO_OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    fieldnames = [
        "company_name",
        "company_domain",
        "person_name",
        "designation",
        "leadership_type",
        "confidence",
        "extraction_method",
        "source_url",
    ]

    with open(
        CXO_OUTPUT_FILE,
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        writer.writerows(candidates)


# ============================================================
# SUMMARY
# ============================================================


def display_summary(
    candidates: list[dict],
) -> None:
    """Display extraction summary."""

    print()
    print("=" * 70)
    print("PHASE 4.1 PRECISION CXO SUMMARY")
    print("=" * 70)

    print(f"Total records : " f"{len(candidates)}")

    company_counts = {}

    method_counts = {}

    confidence_counts = {}

    for candidate in candidates:

        company = candidate.get(
            "company_name",
            "",
        )

        method = candidate.get(
            "extraction_method",
            "",
        )

        confidence = candidate.get(
            "confidence",
            "",
        )

        company_counts[company] = (
            company_counts.get(
                company,
                0,
            )
            + 1
        )

        method_counts[method] = (
            method_counts.get(
                method,
                0,
            )
            + 1
        )

        confidence_counts[confidence] = (
            confidence_counts.get(
                confidence,
                0,
            )
            + 1
        )

    print()
    print("BY COMPANY")

    for company, count in sorted(company_counts.items()):

        print(f"{company:<35}" f"{count:>5}")

    print()
    print("BY CONFIDENCE")

    for confidence in (
        "HIGH",
        "MEDIUM",
        "LOW",
    ):

        print(f"{confidence:<15}" f"{confidence_counts.get(confidence, 0):>5}")

    print()
    print("BY EXTRACTION METHOD")

    for method, count in sorted(method_counts.items()):

        print(f"{method:<20}" f"{count:>5}")


# ============================================================
# MAIN
# ============================================================


def main() -> None:
    """Run Phase 4.1."""

    print()
    print("=" * 70)
    print("CXO GOOGLE SCRAPER")
    print("PHASE 4.1 - PRECISION CXO IDENTIFICATION")
    print("=" * 70)

    print()
    print("Cost policy:")

    print("Google Places API : NOT USED")

    print("Google Search API : NOT USED")

    print("Paid API          : NOT USED")

    print("Proxy             : NOT USED")

    print("Scraping service  : NOT USED")

    pages = load_leadership_pages()

    if not pages:

        print()
        print("[INFO] " "No leadership/management pages found.")
        print("No CXO records can be extracted for this batch.")
        print("Writing an empty cxo_people.csv and continuing.")

        save_results([])

        display_summary([])

        print()
        print(f"File: {CXO_OUTPUT_FILE}")
        print("Records: 0")
        print()
        print("Phase 4 completed with zero leadership pages.")
        print("The pipeline will continue to the next phase.")

        return

    print()
    print(f"Leadership pages loaded: " f"{len(pages)}")

    all_candidates = []

    for index, page in enumerate(
        pages,
        start=1,
    ):

        print()
        print("-" * 70)

        print(f"PAGE " f"{index}/" f"{len(pages)}")

        candidates = process_page(page)

        all_candidates.extend(candidates)

        if index < len(pages):

            time.sleep(config.REQUEST_DELAY)

    all_candidates = deduplicate_candidates(all_candidates)

    display_summary(all_candidates)

    save_results(all_candidates)

    print()
    print("=" * 70)
    print("PHASE 4.1 COMPLETE")
    print("=" * 70)

    print()
    print(f"File: {CXO_OUTPUT_FILE}")

    print(f"Records: " f"{len(all_candidates)}")

    print()
    print("Precision CXO identification completed.")

    print()
    print("DO NOT RUN PHASE 5 YET.")

    print("Inspect cxo_people.csv first.")


if __name__ == "__main__":
    main()
