from supabase import create_client, Client
from dotenv import load_dotenv
import os

load_dotenv()

SUPABASE_URL = str(os.getenv("SUPABASE_URL"))
SUPABASE_KEY = str(os.getenv("SUPABASE_KEY"))

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# File path
fp = "/Users/jordankail/quarg/jobbr/positions_5705340.txt"

# Open the file in binary mode and upload
with open(fp, "rb") as f:
    supabase.storage.from_("scraped_data").upload(
        file=f, path="test/testy/test/test/positions_5705340.txt"
    )


# List the contents in the bucket
res = supabase.storage.from_("scraped_data").list()
print(res)
