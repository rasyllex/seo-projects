"""HTML parser for Selenium crawler."""
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse


def extract_links(html: str, base_url: str) -> list[str]:
    """Извлекает внутренние ссылки из HTML."""
    soup = BeautifulSoup(html, "html.parser")
    links = []
    domain = urlparse(base_url).netloc
    for tag in soup.find_all("a", href=True):
        href = urljoin(base_url, tag["href"])
        if urlparse(href).netloc == domain:
            links.append(href)
    return list(set(links))


def extract_zones(html: str) -> dict:
    """Извлекает зоны страницы: title, h1, h2, description.
    Единый формат с requests-краулером (урок 07)."""
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else ""
    h1 = soup.h1.get_text(strip=True) if soup.h1 else ""
    h2 = " | ".join(t.get_text(strip=True) for t in soup.find_all("h2")[:3])
    desc_tag = soup.find("meta", attrs={"name": "description"})
    description = desc_tag["content"].strip() if desc_tag and desc_tag.get("content") else ""
    return {"title": title, "h1": h1, "h2": h2, "description": description}


def extract_dynamic_content(html: str) -> dict:
    """Извлекает контент, появившийся после JS-рендеринга."""
    soup = BeautifulSoup(html, "html.parser")
    return {
        "title": soup.title.text.strip() if soup.title else "",
        "h1": [h.get_text(strip=True) for h in soup.find_all("h1")],
        "products": [
            {
                "name": p.find("h2").get_text(strip=True) if p.find("h2") else "",
                "price": p.find("p", class_="price").get_text(strip=True)
                if p.find("p", class_="price")
                else "",
            }
            for p in soup.find_all("div", class_="product")
        ],
    }
