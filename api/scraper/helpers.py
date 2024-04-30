from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import WebDriverException
from bs4 import BeautifulSoup
import requests
from faker import Faker
from urllib.parse import urlparse
from models import URL, URLBase, URLType
from helpers import save_text_to_file, create_directory
import re
import os

##TODO move this to env file
FILE_LOCATION = "scraped_data"


def fetch_content(url: str):
    faker = Faker()

    def fetch_with_headless_chrome():
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--window-size=1920,1200")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--enable-logging")
        options.add_argument("--v=1")
        options.add_argument("--log-path=/path/to/chromedriver.log")

        executable_path = "/usr/local/bin/chromedriver"
        options.binary_location = executable_path

        try:
            with webdriver.Chrome(options=options) as driver:
                driver.get(url)
                return driver.page_source
        except WebDriverException as e:
            print(f"WebDriver error: {e}")
            return None

    headers = {
        "User-Agent": faker.user_agent(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    }

    try:

        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.text
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            print(
                "Encountered 403 Forbidden error, using headless Chrome to access the page."
            )
            return fetch_with_headless_chrome()
        else:
            print(f"Error fetching URL {url}: {e}")
            return None
    except requests.RequestException as e:
        print(f"Error fetching URL {url}: {e}")
        return None


def parse_html(html_content):

    soup = BeautifulSoup(html_content, "lxml")

    visible_text = soup.get_text(separator=" ", strip=True)
    script_texts = [
        script.string for script in soup.find_all("script") if script.string
    ]
    meta_contents = [
        meta.get("content") for meta in soup.find_all("meta") if meta.get("content")
    ]

    parsed_html = "\n".join([visible_text] + script_texts + meta_contents)
    return parsed_html


def parse_url(url):
    try:
        if not isinstance(url, str):
            raise ValueError("URL must be a string")

        # Parse the URL
        parsed_url = urlparse(url)

        # Extract the domain without the extension using regex
        domain_regex = r"(?:www\.)?([^\.]+)\.\w+$"
        match = re.search(domain_regex, parsed_url.netloc)
        if match:
            domain = match.group(1)
        else:
            domain = parsed_url.netloc.split(".")[0]

        # Combine path, query, and fragment
        full_path = f"{parsed_url.path}?{parsed_url.query}#{parsed_url.fragment}".strip(
            "?#"
        )

        # Replace special characters with underscores
        full_path_safe = re.sub(r"\W", "_", full_path)

        # Identify and save numeric parts which could be significant IDs
        numeric_id = next(
            (part for part in re.split(r"_+", full_path_safe) if part.isdigit()), None
        )

        # Filter out empty parts and avoid overly generic names
        meaningful_parts = [
            part
            for part in re.split(r"_+", full_path_safe)
            if part and not part.isdigit()
        ]

        # Include the numeric ID if it exists
        if numeric_id:
            meaningful_parts.append(numeric_id)

        # Join parts to form a base filename
        filename = "_".join(meaningful_parts)

        return domain, filename

    except ValueError as ve:
        print(f"Error: {ve}")
        return None, None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None, None


def createURL(url: URLBase) -> URL:

    url_data = url.dict()
    url_data["url"] = str(url_data["url"])

    response_html = fetch_content(url_data["url"])
    parsed_text = parse_html(response_html)
    domain, fileName = parse_url(url_data["url"])

    base_path = f"{os.getcwd()}/{FILE_LOCATION}/{domain}/"
    create_directory(base_path)

    html_file = base_path + fileName + ".html"
    text_file = base_path + fileName + ".txt"

    save_text_to_file(html_file, response_html)
    save_text_to_file(text_file, parsed_text)

    return URL(
        **url_data,
        type=URLType.ROLE,
        directory=domain,
        snapshotPath=None,
        htmlPath=html_file,
        parseTextPath=text_file,
    )
