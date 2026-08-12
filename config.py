"""
CXO GOOGLE SCRAPER
==================

Shared configuration for:

    Phase 1 - Website Input & Validation
    Phase 2 - CXO-Focused Website Discovery
    Phase 3 - Public Contact Extraction
"""

from pathlib import Path

# ============================================================
# PROJECT PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

INPUT_DIR = BASE_DIR / "input"

OUTPUT_DIR = BASE_DIR / "output"


# ============================================================
# INPUT / OUTPUT FILES
# ============================================================

COMPANIES_INPUT_FILE = INPUT_DIR / "companies.csv"

COMPANIES_OUTPUT_FILE = OUTPUT_DIR / "companies.csv"

WEBSITE_PAGES_OUTPUT_FILE = OUTPUT_DIR / "website_pages.csv"

PAGE_CONTACTS_OUTPUT_FILE = OUTPUT_DIR / "page_contacts.csv"


# ============================================================
# HTTP
# ============================================================

REQUEST_TIMEOUT = 15

REQUEST_DELAY = 2

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 "
    "(KHTML, like Gecko) "
    "Chrome/151.0.0.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "en-US,en;q=0.9",
}


# ============================================================
# URL
# ============================================================

ALLOWED_SCHEMES = {
    "http",
    "https",
}

MAX_URL_LENGTH = 2048


# ============================================================
# PHASE 2 DISCOVERY
# ============================================================

MAX_LINKS_FROM_HOMEPAGE = 300

MAX_PAGES_PER_COMPANY = 30

MIN_PAGE_SCORE = 55


# ============================================================
# HIGH-VALUE PAGE PATTERNS
# ============================================================

PAGE_PATTERNS = {
    "leadership": (
        "leadership",
        "leadership-team",
        "leadership-profile",
        "leadership-profiles",
        "senior-leadership",
        "senior-management",
    ),
    "management": (
        "management",
        "management-team",
        "management-profile",
        "management-profiles",
        "management-team-profiles",
    ),
    "executive": (
        "executive",
        "executive-team",
        "executive-leadership",
        "executive-management",
        "executive-profiles",
    ),
    "founder": (
        "founder",
        "founders",
        "founding-team",
        "co-founder",
        "cofounder",
        "co-founders",
    ),
    "board": (
        "board",
        "board-of-directors",
        "board-directors",
        "directors-board",
        "board-members",
        "board-member",
    ),
    "director": (
        "director",
        "directors",
        "director-profile",
        "director-profiles",
    ),
    "team": (
        "our-team",
        "the-team",
        "team",
        "meet-the-team",
        "our-people",
        "people",
        "people-profiles",
        "team-members",
    ),
    "contact": (
        "contact",
        "contact-us",
        "contactus",
        "get-in-touch",
        "reach-us",
        "talk-to-us",
        "contact-form",
    ),
    "about": (
        "about",
        "about-us",
        "about-company",
        "company-profile",
        "company-overview",
        "who-we-are",
    ),
}


# ============================================================
# PAGE SCORES
# ============================================================

PAGE_TYPE_SCORES = {
    "leadership": 100,
    "management": 100,
    "executive": 100,
    "founder": 100,
    "board": 100,
    "director": 95,
    "team": 90,
    "contact": 90,
    "about": 70,
}


# ============================================================
# EXCLUDED PATH SEGMENTS
# ============================================================

EXCLUDED_PATH_SEGMENTS = {
    # Authentication
    "login",
    "signin",
    "sign-in",
    "signup",
    "sign-up",
    "register",
    # Shopping
    "cart",
    "checkout",
    "shop",
    "store",
    # Search
    "search",
    # Legal
    "privacy",
    "terms",
    "cookie",
    "cookies",
    # CMS
    "wp-admin",
    "wp-login",
    # News / Media
    "blog",
    "blogs",
    "news",
    "newsroom",
    "press",
    "media",
    "media-kit",
    "media-center",
    "media-centre",
    # Articles
    "article",
    "articles",
    "analyst",
    "analyst-speak",
    "analyst-reports",
    "reports",
    # Events
    "events",
    "event",
    "webinar",
    "webinars",
    "podcast",
    "podcasts",
    # Careers
    "career",
    "careers",
    "jobs",
    "job",
    "vacancy",
    "vacancies",
    "recruitment",
    # Commercial
    "products",
    "product",
    "services",
    "service",
    "solutions",
    "solution",
    "industries",
    "industry",
    # Resources
    "resources",
    "case-studies",
    "case-study",
    "success-stories",
    "customer-stories",
    "downloads",
    "download",
    # ESG / CSR
    "csr",
    "esg",
    "sustainability",
    "corporate-social-responsibility",
    "corporate-citizenship",
    "social-responsibility",
    # Corporate subsections
    "alliances",
    "alliance",
    "partnerships",
    "partnership",
    "awards",
    "award",
    "recognitions",
    "recognition",
    "history",
    "innovation",
    "innovation-fund",
    "innovation-network",
    "incubator",
    "business-incubator",
    "diversity",
    "diversity-inclusion",
    "diversity-equity-inclusion",
    "inclusion",
    "well-being",
    "wellbeing",
    "supplier-diversity",
    "portfolio",
    "portfolio-companies",
    "our-portfolio-companies",
    "brand",
    "our-brand",
    "customer-speak",
    "clients-speak",
    # Locations
    "locations",
    "location",
    "offices",
    "office",
    # Taxonomy
    "tag",
    "tags",
    "category",
    "categories",
    "author",
    "authors",
}


# ============================================================
# EXCLUDED SEGMENT PREFIXES
#
# Useful for compound URL segments such as:
#
#     awards-and-recognitions
#     privacy-at-wipro
#     wipro-well-being
#     alliances-partnerships
# ============================================================

EXCLUDED_SEGMENT_KEYWORDS = (
    "award",
    "recognition",
    "privacy",
    "cookie",
    "alliance",
    "partner",
    "sustainab",
    "well-being",
    "wellbeing",
    "diversity",
    "inclusion",
    "history",
    "innovation",
    "corporate-citizenship",
    "social-responsibility",
    "portfolio",
    "customer-speak",
    "clients-speak",
    "brand",
)


# ============================================================
# NON-HTML EXTENSIONS
# ============================================================

NON_HTML_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".zip",
    ".rar",
    ".7z",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".svg",
    ".mp3",
    ".mp4",
    ".avi",
    ".mov",
    ".css",
    ".js",
    ".json",
    ".xml",
}


# ============================================================
# EXTERNAL DOMAINS
# ============================================================

EXCLUDED_EXTERNAL_DOMAINS = {
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "twitter.com",
    "x.com",
    "youtube.com",
    "t.me",
    "wa.me",
    "whatsapp.com",
    "google.com",
    "google.co.in",
    "maps.google.com",
    "apple.com",
}


# ============================================================
# PHASE 3
# ============================================================

MAX_PAGE_TEXT_LENGTH = 20000

MAX_EMAILS_PER_PAGE = 20

MAX_PHONES_PER_PAGE = 20

MAX_CONTACT_LINKS_PER_PAGE = 20


# ============================================================
# EMAIL FILTERING
# ============================================================

EXCLUDED_EMAIL_DOMAINS = {
    "example.com",
    "example.org",
    "example.net",
}


# ============================================================
# CONTACT LINK KEYWORDS
# ============================================================

CONTACT_LINK_KEYWORDS = {
    "contact",
    "contact-us",
    "contactus",
    "get-in-touch",
    "reach-us",
    "talk-to-us",
}
