import pandas as pd
from sqlalchemy import create_engine, text
import openai


openai.api_key = "already deleted"
job_file_location = "/Users/jordankail/Jobbr/testingStuff/jobs.csv"
dburl = "postgresql+psycopg2://postgres:postgres@localhost:5432/exampledb"

# Load the CSV file
df = pd.read_csv(job_file_location)

# Preview the data to understand its structure
print(df.head())

engine = create_engine(dburl)
connection = engine.connect()  # This creates a new connection to the database

# Executing a query


df.to_sql("test_jobs", engine, if_exists="replace", index=False)


sql_query = text("SELECT * FROM test_jobs")

# Execute the query
result = connection.execute(sql_query)
for row in result:
    print(row)
connection.close()

response = openai.ChatCompletion.create(
    model="text-davinci-003",
    messages=[
        {
            "role": "system",
            "content": f"I've given you a bunch of data for jobs i'm intrested in here: {result}",
        },
        {
            "role": "user",
            "content": "What is the highest paying Job",
        },
    ],
)

print(response["choices"][0]["message"]["content"])
