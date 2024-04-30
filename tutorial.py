from langchain_community.document_loaders.csv_loader import CSVLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain.vectorstores.pgvector import PGVector

# from dotenv import load_dotenv

import pandas as pd
from sqlalchemy import create_engine, text
import openai


openai.api_key = "sk-proj-S6OHkmcumvbFPU9geTuFT3BlbkFJGcGsLRjGl5MrNMNEzbxy"
job_file_location = "/Users/jordankail/Jobbr/testingStuff/jobs.csv"
dburl = "postgresql+psycopg2://postgres:postgres@localhost:5432/exampledb"
csvFile = "/Users/jordankail/Jobbr/testingStuff/jobs.csv"


loader = CSVLoader(file_path=csvFile)
data = loader.load()
# print(data)


text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=80)
texts = text_splitter.split_documents(data)


embeddings = OpenAIEmbeddings()
vector = embeddings.embed_query("testing")

# print(vector)
print(len(vector))


doc_vectors = embeddings.embed_documents([t.page_content for t in texts[:5]])
