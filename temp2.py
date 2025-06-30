import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import os
import csv
import re

def sanitize_filename(url):
    """Convert URL to a safe filename."""
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    if not path:
        path = "index"
    filename = parsed.netloc + "_" + path
    filename = re.sub(r"[^a-zA-Z0-9_\-]", "_", filename)
    return filename + ".csv"

def crawl(url, visited=None):
    if visited is None:
        visited = set()
    if url in visited:
        return
    visited.add(url)

    try:
        response = requests.get(url, timeout=5)
        if "text/html" not in response.headers.get("Content-Type", ""):
            return

        soup = BeautifulSoup(response.text, "html.parser")
        text = soup.get_text(separator="\n", strip=True)

        # Save the page content to a CSV
        filename = sanitize_filename(url)
        filepath = os.path.join("website", filename)
        with open(filepath, "w", newline='', encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["url", "content"])
            writer.writerow([url, text])

        # Crawl linked pages recursively
        for link in soup.find_all("a", href=True):
            href = link["href"]
            full_url = urljoin(url, href)
            if urlparse(full_url).netloc == urlparse(url).netloc:
                crawl(full_url, visited)

    except Exception as e:
        print(f"Failed to crawl {url}: {e}")

# Create output directory if it doesn't exist
os.makedirs("website", exist_ok=True)

# Start crawling from the homepage
start_url = "https://www.iran-australia.com"
crawl(start_url)

print("Crawling complete. Each page saved as a separate CSV in the 'website' folder.")
