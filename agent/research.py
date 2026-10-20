"""Understand the business: crawl the website (and optionally a local repo's docs) and write
`knowledge/business_brief.auto.md`. The curated `business_brief.md` stays the authority; the
auto brief adds whatever the site says that the curated one does not.
"""

from __future__ import annotations

import pathlib
import re
import time
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup

from .config import KNOWLEDGE, now_ist, read_text
from .llm import Gemini

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; sarthi-social-agent/1.0; +https://interviewsarthi.com)"}
SKIP_EXT = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico", ".pdf", ".zip", ".exe", ".xml", ".txt", ".js", ".css")
PAGE_CHARS = 6000
TOTAL_CHARS = 150000

OUTLINE = """# <Business name>: auto brief
Generated <date> from <n> pages of <site>.

## One line
## What it does, in detail
## How it works (technology, privacy, requirements)
## Pricing (exact numbers and terms as published)
## Who it is for
## Problems it solves
## Differentiators and proof points (only what the site states)
## Voice, tone and words the site uses
## Words and claims the site avoids or warns about
## Links worth pointing to (URL: what it is)
## Frequently asked questions (as answered on the site)
## Content angles suggested by the site's own pages
## Open questions the owner should confirm
"""


def _sitemap_urls(root: str) -> list[str]:
    try:
        response = requests.get(urljoin(root, "/sitemap.xml"), headers=HEADERS, timeout=30)
        if response.status_code != 200:
            return []
        tree = ElementTree.fromstring(response.content)
        return [el.text.strip() for el in tree.iter() if el.tag.endswith("loc") and el.text]
    except Exception:  # noqa: BLE001
        return []


def _page_text(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "nav", "footer", "iframe"]):
        tag.decompose()
    title = (soup.title.string.strip() if soup.title and soup.title.string else "")
    desc = ""
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        desc = meta["content"].strip()
    text = soup.get_text("\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text).strip()
    return title, (desc + "\n" + text).strip()


def crawl(start_url: str, max_pages: int = 40) -> list[dict]:
    root = f"{urlparse(start_url).scheme}://{urlparse(start_url).netloc}"
    host = urlparse(start_url).netloc
    queue = [start_url] + [u for u in _sitemap_urls(root) if urlparse(u).netloc == host]
    seen: set[str] = set()
    pages: list[dict] = []
    while queue and len(pages) < max_pages:
        url = queue.pop(0).split("#")[0]
        if url in seen or urlparse(url).netloc != host or url.lower().endswith(SKIP_EXT):
            continue
        seen.add(url)
        try:
            response = requests.get(url, headers=HEADERS, timeout=30)
        except requests.RequestException:
            continue
        if response.status_code != 200 or "text/html" not in response.headers.get("content-type", ""):
            continue
        title, text = _page_text(response.text)
        pages.append({"url": url, "title": title, "text": text[:PAGE_CHARS]})
        soup = BeautifulSoup(response.text, "html.parser")
        for a in soup.find_all("a", href=True):
            link = urljoin(url, a["href"]).split("#")[0]
            if urlparse(link).netloc == host and link not in seen and not link.lower().endswith(SKIP_EXT):
                queue.append(link)
        time.sleep(0.4)
    return pages


def repo_docs(path: str | pathlib.Path) -> list[dict]:
    base = pathlib.Path(path)
    files = sorted(base.glob("*.md")) + sorted((base / "docs").glob("*.md")) if base.exists() else []
    docs = []
    for f in files:
        text = read_text(f)
        if text.strip():
            docs.append({"name": f.name, "text": text[:8000]})
    return docs


def synthesize(llm: Gemini, site: str, pages: list[dict], docs: list[dict]) -> str:
    budget = TOTAL_CHARS
    chunks = []
    for page in pages:
        piece = f"\n\n=== PAGE {page['url']}\nTITLE: {page['title']}\n{page['text']}"
        if budget - len(piece) < 0:
            break
        budget -= len(piece)
        chunks.append(piece)
    for doc in docs:
        piece = f"\n\n=== REPO DOC {doc['name']}\n{doc['text']}"
        if budget - len(piece) < 0:
            break
        budget -= len(piece)
        chunks.append(piece)
    system = ("You are a marketing analyst. You read a company's website and internal docs and write a precise "
              "business brief for a social media team. State only what the material supports. Quote prices, "
              "limits and guarantees exactly. Prefer the newest information when pages disagree and say so. "
              "Write in plain English, short paragraphs and bullet lists, no em dashes.")
    user = (f"Write the brief for {site} using exactly this outline (keep the headings, fill each section):\n\n"
            f"{OUTLINE}\n\nDate: {now_ist().strftime('%d %B %Y')}. Pages: {len(pages)}.\n\nMATERIAL:" + "".join(chunks))
    return llm.text(system, user, temperature=0.3, max_tokens=8000)


def run(llm: Gemini, url: str, repo: str | None = None, out: pathlib.Path | None = None, max_pages: int = 40) -> pathlib.Path:
    pages = crawl(url, max_pages=max_pages)
    if not pages:
        raise RuntimeError(f"could not read any page from {url}")
    docs = repo_docs(repo) if repo else []
    print(f"[research] read {len(pages)} pages and {len(docs)} repo docs")
    brief = synthesize(llm, url, pages, docs).replace("—", ", ").replace("–", "-")
    out = out or (KNOWLEDGE / "business_brief.auto.md")
    out.write_text(brief.strip() + "\n", encoding="utf-8")
    print(f"[research] wrote {out}")
    return out
