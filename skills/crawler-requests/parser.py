"""
Парсинг HTML: извлечение ссылок и зон.
"""

from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup


def extract_links(html, base_url):
    """Извлекает ссылки с того же домена."""
    soup = BeautifulSoup(html, "lxml")
    # Добавляем scheme если его нет (студент может передать просто домен)
    if not base_url.startswith(("http://", "https://")):
        base_url = "https://" + base_url
    base_domain = urlparse(base_url).netloc
    links = []

    for tag in soup.find_all("a", href=True):
        href = tag["href"]
        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)

        if parsed.netloc == base_domain and parsed.scheme in ("http", "https"):
            # Убираем якоря и параметры
            clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            if clean_url not in links:
                links.append(clean_url)

    return links


def extract_zones(html):
    """Извлекает title, h1, h2, description."""
    soup = BeautifulSoup(html, "lxml")

    title = soup.title.string.strip() if soup.title else ""
    h1 = soup.h1.get_text(strip=True) if soup.h1 else ""

    h2_tags = soup.find_all("h2")
    h2 = " | ".join(tag.get_text(strip=True) for tag in h2_tags[:3])

    desc_tag = soup.find("meta", attrs={"name": "description"})
    description = desc_tag["content"].strip() if desc_tag and desc_tag.get("content") else ""

    return {
        "title": title,
        "h1": h1,
        "h2": h2,
        "description": description
    }


def extract_canonical(html):
    """Извлекает canonical URL."""
    soup = BeautifulSoup(html, "lxml")
    tag = soup.find("link", attrs={"rel": "canonical"})
    return tag["href"] if tag else ""
