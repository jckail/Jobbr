import pandas as pd
import requests


def post_urls_from_csv(csv_path):
    # Read the CSV file into a DataFrame
    # Load the CSV file into a DataFrame
    df = pd.read_csv(csv_path)
    print(df)

    # Ensure the 'url' column exists
    if "url" not in df.columns:
        raise ValueError("CSV file must contain a 'url' column")

    # Iterate over the DataFrame using the 'url' column
    for url in df["url"]:
        # Prepare the payload for the POST request

        # URL of the API endpoint
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


# Example usage:
# post_urls_from_csv('path_to_your_csv_file.csv')


if __name__ == "__main__":
    post_urls_from_csv("/Users/jordankail/quarg/jobbr/urls.csv")
