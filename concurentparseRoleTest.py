import pandas as pd
import requests
import concurrent.futures


def post_url(url):
    api_url = "http://127.0.0.1:8000/api/parse/stg_role?input_url=" + url
    headers = {"accept": "application/json"}
    # Send the POST request
    response = requests.post(api_url, headers=headers)

    # Check the response status
    if response.status_code == 200:
        print(f"Successfully posted URL: {url}")
    else:
        print(
            f"Failed to post URL: {url}. Status code: {response.status_code}, Response: {response.text}"
        )


def post_urls_from_csv(csv_path):
    # Load the CSV file into a DataFrame
    df = pd.read_csv(csv_path)
    print(df)

    # Ensure the 'Role Link' column exists
    if "url" not in df.columns:
        raise ValueError("CSV file must contain a 'Role Link' column")

    # Use a ThreadPoolExecutor to post URLs concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        # Map the post_url function to each URL and process asynchronously
        results = executor.map(post_url, df["url"])

        # Print the results as they are completed
        for result in results:
            print(result)


# Example usage:
# post_urls_from_csv('path_to_your_csv_file.csv')

if __name__ == "__main__":
    post_urls_from_csv("/Users/jordankail/quarg/jobbr/urls.csv")
