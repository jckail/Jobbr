from spider import Spider

apiKey = "sk-4e1c55ea-c5ef-43fd-80ed-afec3d2d90ad"
app = Spider(api_key="apiKey")

# Scrape a single URL
url = "https://spider.cloud"
scraped_data = app.scrape_url(url)
