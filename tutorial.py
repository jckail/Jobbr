from typing import List
from langchain_community.document_loaders.csv_loader import CSVLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents.base import Document
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.vectorstores.pgvector import PGVector
from langchain.evaluation import load_evaluator


import openai
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain.prompts import ChatPromptTemplate
from sqlalchemy import create_engine, text


openai.api_key = "sk-proj-S6OHkmcumvbFPU9geTuFT3BlbkFJGcGsLRjGl5MrNMNEzbxy"
job_file_location = "/Users/jordankail/Jobbr/testingStuff/jobs.csv"
dburl = "postgresql+psycopg2://postgres:postgres@localhost:5432/exampledb"
csvFile = "/Users/jordankail/Jobbr/testingStuff/jobs.csv"


loader = CSVLoader(file_path=csvFile)
data: List[Document] = loader.load()
# print(data)


text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=450)
texts = text_splitter.split_documents(data)
print(len(texts))


embeddings = OpenAIEmbeddings()


doc_vectors = embeddings.embed_documents([t.page_content for t in texts])


COLLECTION_NAME = "jordan_job_list"

engine = create_engine(dburl)

# Connect to the database
table_name = "langchain_pg_collection"
table_name2 = "langchain_pg_embedding"
column_name = "name"

with engine.connect() as connection:
    transaction = connection.begin()
    # SQL statement to execute
    query = text(
        f"SELECT uuid FROM {table_name} WHERE {column_name} = '{COLLECTION_NAME}'"
    )
    print(query)

    # Execute the query and fetch the result
    fk = connection.execute(query)
    print(fk.fetchone())
    if fk.fetchone():
        the_fk = fk.fetchone()[0]

        query = text(
            f"Delete FROM {table_name} WHERE {column_name} = '{COLLECTION_NAME}'"
        )
        print(query)
        connection.execute(query)

        query = text(f"Delete FROM {table_name2} WHERE collection_id = '{the_fk}'")
        print(query)
        connection.execute(query)
        transaction.commit()

db = PGVector.from_documents(
    embedding=embeddings,
    documents=texts,
    collection_name=COLLECTION_NAME,
    connection_string=dburl,
)


question = "Which job 5 jobs are best for python and why?"

results = db.similarity_search_with_relevance_scores(question, k=50)
for doc in results:
    print(doc)


loader = PyPDFLoader("/Users/jordankail/Jobbr/Resume.pdf")
pages = loader.load_and_split()

text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=450)
texts = text_splitter.split_documents(pages)
embeddings = OpenAIEmbeddings()
embeddings.embed_documents([t.page_content for t in texts])

COLLECTION_NAME = "jordanresume"
table_name = "langchain_pg_collection"
table_name2 = "langchain_pg_embedding"
column_name = "name"

with engine.connect() as connection:
    transaction = connection.begin()
    # SQL statement to execute
    query = text(
        f"SELECT uuid FROM {table_name} WHERE {column_name} = '{COLLECTION_NAME}'"
    )
    print(query)

    # Execute the query and fetch the result
    fk = connection.execute(query)

    if fk.fetchone():
        the_fk = fk.fetchone()[0]

        query = text(
            f"Delete FROM {table_name} WHERE {column_name} = '{COLLECTION_NAME}'"
        )
        print(query)
        connection.execute(query)

        query = text(f"Delete FROM {table_name2} WHERE collection_id = '{the_fk}'")
        print(query)
        connection.execute(query)
        transaction.commit()

db = PGVector.from_documents(
    embedding=embeddings,
    documents=texts,
    collection_name=COLLECTION_NAME,
    connection_string=dburl,
)


PROMPT_TEMPLATE = """

{context}
----------------
Answer "{question}" based on the above context. 

"""

context_text = "\n\n---\n\n".join([doc.page_content for doc, _score in results])
prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
prompt = prompt_template.format(context=context_text, question=question)
print(prompt)

model = ChatOpenAI()
response_text = model.invoke(prompt)
print("\n", question, "\n", response_text.content, "\n")

# if len(results) == 0 or results[0][1] < 0.7:
#     print(f"Unable to find matching results.")
#     return

# evaluator = load_evaluator("pairwise_embedding_distance")
# x = evaluator.evaluate_string_pairs(prediction="apple", prediction_b="orange")
# print(x)


embeddings = OpenAIEmbeddings()
loader = PyPDFLoader("/Users/jordankail/Jobbr/Resume.pdf")
pages = loader.load_and_split()


faiss_index = FAISS.from_documents(pages, embeddings)
docs = faiss_index.similarity_search("where is jordan?", k=2)
for doc in docs:
    print(str(doc.metadata["page"]) + ":", doc.page_content)

# db = PGVector.from_documents(
#     embedding=embeddings,
#     documents=pages,
#     collection_name="jordankailresume",
#     connection_string=dburl,
# )
