# documentation : https://python.langchain.com/docs/modules/data_connection/document_loaders/pdf/
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
import os
import getpass


loader = PyPDFLoader("/Users/jordankail/Jobbr/Resume.pdf")
pages = loader.load_and_split()

# os.environ["OPENAI_API_KEY"] = getpass.getpass("OpenAI API Key:")
faiss_index = FAISS.from_documents(pages, OpenAIEmbeddings())
docs = faiss_index.similarity_search("where is jordan?", k=2)
for doc in docs:
    print(str(doc.metadata["page"]) + ":", doc.page_content)


# `pip install faiss-gpu` (for CUDA supported GPU)
