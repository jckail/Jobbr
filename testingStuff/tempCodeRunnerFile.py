from bs4 import BeautifulSoup
from langdetect import detect, LangDetectException
import re


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

    # Extract script tags text and filter non-English text
    script_texts = []
    for script in soup.find_all("script"):
        if script.string:
            try:
                # Check if the script text is in English
                if detect(script.string) == "en":
                    script_texts.append(script.string)
            except LangDetectException:
                # Handle the case where language detection fails
                continue

    # Extract meta tags content
    meta_contents = [
        meta.get("content") for meta in soup.find_all("meta") if meta.get("content")
    ]

    parsedHtml = "\n".join([visible_text] + script_texts + meta_contents)

    return parsedHtml


if __name__ == "__main__":
    file = "/Users/jordankail/Jobbr/scraped_data/openai/careers_analytics_data_engineer_applied_engineering.html"
    ## open file
    with open(file, "r") as f:
        file = f.read()

    data = parse_html(file)
    print(len(data))

    # save file to "/Users/jordankail/Jobbr/scraped_data/openai/test_careers_analytics_data_engineer_applied_engineering.txt"
    with open(
        "/Users/jordankail/Jobbr/scraped_data/openai/test_careers_analytics_data_engineer_applied_engineering.txt",
        "w",
    ) as f:
        f.write(data)
