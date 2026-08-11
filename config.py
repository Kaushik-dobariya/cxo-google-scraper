from pathlib import Path

# ============================================================
# PROJECT
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"


# ============================================================
# INPUT / OUTPUT FILES
# ============================================================

SEARCH_FILE = INPUT_DIR / "search.csv"

COMPANIES_FILE = OUTPUT_DIR / "companies.csv"


# ============================================================
# SCRAPER SETTINGS
# ============================================================

# Maximum search results for each query.
MAX_RESULTS_PER_QUERY = 10

# Maximum number of search queries to process.
MAX_SEARCH_QUERIES = 20

# Seconds to wait between requests.
REQUEST_DELAY = 2

# HTTP request timeout.
REQUEST_TIMEOUT = 15


# ============================================================
# HTTP HEADERS
# ============================================================

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
# EXCLUDED DOMAINS
# ============================================================

# These are not normally company websites.
# We want to discover the actual company's website.

EXCLUDED_DOMAINS = {
    "google.com",
    "google.co.in",
    "bing.com",
    "duckduckgo.com",
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "twitter.com",
    "x.com",
    "youtube.com",
    "wikipedia.org",
    "justdial.com",
    "indiamart.com",
    "tradeindia.com",
    "sulekha.com",
    "yelp.com",
    "yellowpages.com",
    "crunchbase.com",
}
