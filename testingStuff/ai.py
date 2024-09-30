from langchain_community.document_loaders.csv_loader import CSVLoader
from langchain.text_splitter import (
    CharacterTextSplitter,
    RecursiveCharacterTextSplitter,
)
from langchain_core.documents.base import Document
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_postgres import PGVector


import openai
from langchain_community.document_loaders import PyPDFLoader
from langchain_openai import OpenAIEmbeddings
from langchain.prompts import ChatPromptTemplate

import os

# TODO understand how to embed a PDF into a vector datbase


openai.api_key = "already deleted"


def loadDocument(file_path: str):
    loader = None
    if file_path.endswith(".pdf"):
        loader = PyPDFLoader(file_path=file_path)
    elif file_path.endswith(".csv"):
        loader = CSVLoader(file_path=csvFile, source_column="URL")
        data = loader.load()
        print(data[:1])
        # this is only returning the entire
    else:
        raise ValueError("File type not supported")
    file_name_without_ext = os.path.splitext(os.path.basename(file_path))[0]
    return file_name_without_ext, loader.load_and_split()


def createDocChunks(documents, chunk_size=2000, chunk_overlap=100, recursive=False):

    if recursive:
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size, chunk_overlap=chunk_overlap
        )

    else:
        text_splitter = CharacterTextSplitter(
            chunk_size=chunk_size, chunk_overlap=chunk_overlap
        )

    return text_splitter.split_documents(documents)


def getVectorStore(collection_name, connectionstring):
    # # create the store
    return PGVector(
        embeddings=OpenAIEmbeddings(),
        collection_name=collection_name,
        connection=connectionstring,
        use_jsonb=True,
    )


def formatContexts(collection_name, new_contexts, contextList):
    # doc.page_content, _score in pg.similarity_search_with_relevance_scores(query, k=k)
    for doc, score in new_contexts:
        contextList.append(
            f"Document: {collection_name} \n VectorScore: {score} \n Context: {doc.page_content}"
        )
    return contextList


def generatePrompt(query, contextList, prompt_template: str):

    context = "\n---\n ".join(contextList)

    prompt_template = ChatPromptTemplate.from_template(prompt_template)
    return prompt_template.format(context=context, question=query)


if __name__ == "__main__":
    ##TODO become more specific with source of context
    prompt_template = """
    Answer the qustion provided only the documents and context I give you:

    Contexts:
    {context} 

    -----------------
    -----------------

    question: "{question}" 

    """
    connection_string = (
        "postgresql+psycopg2://postgres:postgres@localhost:5432/exampledb"
    )
    csvFile = "/Users/jordankail/Jobbr/testingStuff/jobs.csv"
    pdfFile = "/Users/jordankail/Jobbr/Resume.pdf"

    contextList = []

    question = input("\n\n ask a question? ")

    # list of collections and docs
    docsQueue = [loadDocument(file_) for file_ in [csvFile]]
    for collection_name, docs in docsQueue:
        vectorstore = getVectorStore(
            collection_name,
            connection_string,
        )
        docs = pdf_content_into_documents(docs)

        vectorstore.add_documents(docs, ids=[doc.metadata["row"] for doc in docs])
        searched_docs = vectorstore.similarity_search_with_relevance_scores(
            question, k=5
        )
        new_contexts = [(doc, _score) for doc, _score in searched_docs]

        contextList = formatContexts(collection_name, new_contexts, contextList)

    # print("Searching based on query.")
    # prompt = generatePrompt(question, contextList, prompt_template)

    # model = ChatOpenAI()
    # response_text = model.invoke(prompt)

    # print(
    #     f"\n---\n \n Promt:{prompt}\nQuestion:{question}\nResponse:{response_text.content}"
    # )
