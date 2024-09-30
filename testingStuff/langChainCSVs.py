import openai
import os
import re
from langchain_community.document_loaders.csv_loader import CSVLoader
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents.base import Document
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_postgres import PGVector
from langchain.prompts import ChatPromptTemplate
from langchain.text_splitter import (
    CharacterTextSplitter,
    RecursiveCharacterTextSplitter,
)

openai.api_key = "already deleted"


def cleanDocPageContent(doc):

    text = doc.page_content
    # Replace null characters
    cleaned_text = text.replace("\x00", "")

    # Remove unwanted unicode characters and special symbols
    cleaned_text = re.sub(r"[^\x20-\x7E]+", " ", cleaned_text)

    # Normalize space variations, remove leading/trailing whitespace
    doc.page_content = " ".join(cleaned_text.split())

    return doc


def cleanDocs(docs):
    return [cleanDocPageContent(doc) for doc in docs]


def loadPDF(path):
    loader = PyPDFLoader(path)
    print(loader.load_and_split())
    return cleanDocs(loader.load_and_split())


def loadCSV(path, source_column=None):
    loader = CSVLoader(file_path=path, source_column=source_column)
    return cleanDocs(loader.load())


def loadDocument(file_path: str, source_column=None):
    file_name_without_ext = os.path.splitext(os.path.basename(file_path))[0]
    if file_path.endswith(".pdf"):
        return file_name_without_ext, loadPDF(file_path)
    elif file_path.endswith(".csv"):
        return file_name_without_ext, loadCSV(file_path, source_column)
    else:
        raise ValueError("File type not supported")


def addDocumentChunkId(collection_name, docs):
    for i, chunk in enumerate(docs):
        chunk.metadata["chunk_id"] = f"{collection_name}_{i}"

    return docs


def addDocumentMetaData(docs, datas):
    for doc in docs:
        for data in datas:
            if data not in doc.metadata:
                doc.metadata[data] = datas[data]
    return docs


def createDocChunks(documents, chunk_size=10, chunk_overlap=8, recursive=True):

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


def addVectors(vectorstore, id, docs):

    vectorstore.add_documents(docs, ids=[doc.metadata[id] for doc in docs])
    return vectorstore


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

    prompt_template = """
    Answer the qustion provided only the documents and context I give you:

    Contexts:
    {context} 

    -----------------
    -----------------

    question: "{question}" 

    """

    csvFile = "/Users/jordankail/Jobbr/testingStuff/jobs.csv"
    pdfFile = "/Users/jordankail/Jobbr/Resume.pdf"
    connection_string = (
        "postgresql+psycopg2://postgres:postgres@localhost:5432/exampledb"
    )
    query = input("\n\n Ask a question! \n")

    contextList = []

    # list of collections and docs
    docsQueue = [loadDocument(file_) for file_ in [csvFile, pdfFile]]
    for collection_name, docs in docsQueue:

        chunkedDocs = addDocumentChunkId(collection_name, docs)
        chunkedDocs = addDocumentMetaData(chunkedDocs, {"user": "jordankail"})

        vectorstore = getVectorStore(
            collection_name,
            connection_string,
        )

        print(chunkedDocs[:2])
        vectorstore = addVectors(
            vectorstore,
            "chunk_id",  # this will need to be UUID
            chunkedDocs,
        )

        new_contexts = vectorstore.similarity_search_with_relevance_scores(
            query,
            k=10,
            # filter={"user": {"$eq": "jordankail"}},
        )
        print(new_contexts)
        contextList = formatContexts(collection_name, new_contexts, contextList)

    print("Searching based on query.")
    prompt = generatePrompt(query, contextList, prompt_template)

    model = ChatOpenAI()
    response_text = model.invoke(prompt)
    vectorstore.drop_tables()
    print(
        f"\n---\n \n Promt:{prompt}\nQuestion:{query}\nResponse:{response_text.content}"
    )

    # docs = loadCSV(csvFile, source_column="Role Link")
    # vectorstore = getVectorStore(
    #     "jobs",
    #     connection_string,
    # )
    # docs = addDocumentMetaData(docs, {"user": "jordankail"})

    # vectorstore.add_documents(docs, ids=[doc.metadata["row"] for doc in docs])
    # roleContext = vectorstore.similarity_search_with_relevance_scores(
    #     query,
    #     k=10,
    #     filter={"user": {"$eq": "jordankail"}},
    # )
    # ###################PDF TESTS
    # pdfFile = "/Users/jordankail/Jobbr/Resume.pdf"
    # docs = loadPDF(pdfFile)
    # print("\n")
    # print("\n")
    # print(len(docs))

    # chunkedDocs = createDocChunks(docs, 100, 50, True)
    # chunkedDocs = addDocumentChunkId(chunkedDocs)
    # chunkedDocs = addDocumentMetaData(chunkedDocs, {"user": "jordankail"})

    # print(len(chunkedDocs))
    # print("\n")
    # print("\n")
    # for doc in chunkedDocs[:2]:
    #     print("\n")
    #     print(doc)
    # vectorstore = getVectorStore(
    #     "resumes",
    #     connection_string,
    # )

    # addVectors(vectorstore, "chunk_id", chunkedDocs)

    # x = vectorstore.similarity_search_with_relevance_scores(
    #     query,
    #     k=10,
    #     filter={"user": {"$eq": "jordankail"}},
    # )

    # print(x)
    # new_contexts = [(doc, _score) for doc, _score in searched_docs]

    # contextList = formatContexts(collection_name, new_contexts, contextList)


### TODO:

##1. given html file in htmlfiles turn into structure data: https://python.langchain.com/docs/use_cases/question_answering/sources/
##2a. create an api endpoint that given a file path it validates its HTML, Parses to a structured format
##2b if url already exists in url then run ai ELSE add to HTMLS and then run AI
##2. Save to
##2. Load to pandas and vectorize for future use: https://python.langchain.com/docs/integrations/document_loaders/pandas_dataframe/
