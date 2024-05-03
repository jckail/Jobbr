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
import time
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


from langdetect import detect, LangDetectException
from selenium.webdriver.common.by import By

##TODO move this to env file
FILE_LOCATION = "scraped_data"


def fetch_with_headless_chrome(url):
    faker = Faker()  # Initialize Faker to generate fake data
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

    # User-Agent is generated using Faker
    headers = {
        "User-Agent": faker.user_agent(),  # Generates a random user-agent
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    }

    try:
        with webdriver.Chrome(options=options) as driver:
            for key, value in headers.items():
                options.add_argument(f"{key}={value}")
            driver.get(url)

            # Wait for elements to load using WebDriverWait to wait for the presence of the body tag
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(
                2
            )  # Sleep for additional 2 seconds to ensure all content is loaded
            page_source = driver.page_source
            screenshot = (
                driver.get_screenshot_as_png()
            )  # Takes screenshot of the page and returns it as a PNG
            return page_source, screenshot
    except WebDriverException as e:
        print(f"WebDriver error: {e}")
        return None, None


def fetch_content(url: str):
    faker = Faker()

    headers = {
        "User-Agent": faker.user_agent(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.text

    except requests.RequestException as e:
        print(f"Error fetching URL {url}: {e}")
        return None


def reduce_whitespace(text):
    # Replace multiple spaces with a single space
    return re.sub(r"[ \t]+", " ", text)


def is_english_text(text):
    # Regular expression to detect meaningful English text
    # Adjust the threshold and pattern according to your needs
    if re.search("[a-zA-Z]{3,}", text) and len(re.findall(r"[^\x00-\x7F]+", text)) == 0:
        try:
            # Further validate with langdetect if necessary
            return detect(text) == "en"
        except LangDetectException:
            return False
    return False


def parse_html(html_content):
    soup = BeautifulSoup(html_content, "lxml")
    # Extract visible text
    visible_text = soup.get_text(separator=" ", strip=True)
    visible_text = reduce_whitespace(visible_text)  # Apply whitespace reduction

    # Extract script tags text and filter non-English text
    script_texts = []
    for script in soup.find_all("script"):
        if script.string and is_english_text(script.string):
            script_texts.append(reduce_whitespace(script.string))

    # Extract meta tags content
    meta_contents = [
        reduce_whitespace(meta.get("content"))
        for meta in soup.find_all("meta")
        if meta.get("content")
    ]

    return [visible_text], meta_contents, script_texts


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
    try:
        url_data = url.dict()
        url_data["url"] = str(url_data["url"])

        try:
            response_html1 = fetch_content(url_data["url"])
        except Exception as e:
            response_html1 = None
            print(f"Error fetching URL content: {e}")

        try:
            response_html2, screenshot = fetch_with_headless_chrome(url_data["url"])
        except Exception as e:
            response_html2, screenshot = None, None
            print(f"Error fetching URL with headless Chrome: {e}")

        # Logic to determine which response to use
        if response_html1 and response_html2:
            response_html = (
                response_html1
                if len(response_html1) >= len(response_html2)
                else response_html2
            )
        elif response_html1:
            response_html = response_html1
        elif response_html2:
            response_html = response_html2
        else:
            raise ValueError("Failed to fetch any HTML content for the URL.")

        try:
            visible_text, meta_contents, script_texts = parse_html(response_html)
        except Exception as e:
            visible_text, meta_contents, script_texts = [], [], []
            print(f"Error parsing HTML: {e}")

        parsed_text = "\n".join(visible_text + meta_contents + script_texts)

        domain, fileName = parse_url(url_data["url"])

        base_path = f"{os.getcwd()}/{FILE_LOCATION}/{domain}/snapshots/"
        create_directory(base_path)

        base_path = f"{os.getcwd()}/{FILE_LOCATION}/{domain}/text_detail/"
        create_directory(base_path)

        base_path = f"{os.getcwd()}/{FILE_LOCATION}/{domain}/"
        create_directory(base_path)

        html_file = base_path + fileName + ".html"
        text_file = base_path + fileName + ".txt"
        visible_text_file = (
            base_path + "text_detail/" + fileName + "_visible_text" + ".txt"
        )
        meta_contents_file = (
            base_path + "text_detail/" + fileName + "_meta_contents" + ".txt"
        )
        script_texts_file = (
            base_path + "text_detail/" + fileName + "_script_texts" + ".txt"
        )
        png_file = base_path + "snapshots/" + fileName + ".png"

        try:
            save_text_to_file(html_file, response_html)
        except Exception as e:
            print(f"Failed to save HTML file: {e}")

        try:
            save_text_to_file(text_file, parsed_text)
        except Exception as e:
            print(f"Failed to save text file: {e}")

        try:
            save_text_to_file(visible_text_file, " ".join(visible_text))
        except Exception as e:
            print(f"Failed to save visible text file: {e}")

        try:
            save_text_to_file(script_texts_file, " ".join(script_texts))
        except Exception as e:
            print(f"Failed to save script texts file: {e}")

        try:
            save_text_to_file(meta_contents_file, " ".join(meta_contents))
        except Exception as e:
            print(f"Failed to save meta contents file: {e}")

        if screenshot:
            try:
                with open(png_file, "wb") as file:
                    file.write(screenshot)
            except Exception as e:
                print(f"Failed to save screenshot file: {e}")

        return URL(
            **url_data,
            type=URLType.ROLE,
            directory=domain,
            snapshotPath=png_file,
            htmlPath=html_file,
            parseTextPath=text_file,
        )
    except Exception as e:
        print(f"An error occurred: {e}")
        # Handle or log the error appropriately
        return None  # Return None or an appropriate response when an error occurs
