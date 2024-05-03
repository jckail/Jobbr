from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from models import (
    Stg_RoleBase,
)

##TODO create timer functions so that we can better see timing
## TODO test against langchain outputs etc its going to be better than this i think
from models import URL
from helpers import load_html


def loadLoopFile(file):
    try:
        data: str = load_html(file)
        data_length = len(data)
        return file, data, data_length
    except Exception as e:
        print(f"Failed to intially load file {file}: {str(e)}")


def parseHTMLClaud3(html):
    f = Stg_RoleBase.__doc__
    userMessage = f"Parse the following job posting text into JSON format {f} according to the specified structure. Ensure that all requested fields are included in the output. If any data is missing or unavailable, populate them as None (use null values). Some details may not be explicitly mentioned, do your best to infer them. Here is the text: {html}"
    model = ChatAnthropic(
        model="claude-3-opus-20240229", temperature=0
    )  # claude-3-haiku-20240307 # claude-3-sonnet-20240229 #claude-3-opus-20240229
    structured_llm = model.with_structured_output(Stg_RoleBase, include_raw=True)
    return structured_llm.invoke(input=userMessage)


def parseHTMLgpt3(html):
    f = Stg_RoleBase.__doc__
    userMessage = f" Convert the following job posting text to exactly the desired json format {f}. Do not add in any new field names use only the ones I have previously provided. If there are any values that cannot be calculated return those as None. If there is a mention of 'not found' assume the role has been filled and the status is closed. Here is the job posting: {html}"
    model = ChatOpenAI(model="gpt-3.5-turbo-0125", temperature=0)
    structured_llm = model.with_structured_output(
        Stg_RoleBase, include_raw=True, method="json_mode"
    )
    return structured_llm.invoke(input=userMessage)


def parseHTMLgpt4(html):
    f = Stg_RoleBase.__doc__
    userMessage = f" Convert the following job posting text to exactly the desired json format {f}. Do not add in any new field names use only the ones I have previously provided. If there are any values that cannot be calculated return those as None. If there is a mention of 'not found' assume the role has been filled and the status is closed. Here is the job posting: {html}"
    model = ChatOpenAI(model="gpt-4-turbo-2024-04-09", temperature=0)
    structured_llm = model.with_structured_output(
        Stg_RoleBase, include_raw=True, method="json_mode"
    )
    return structured_llm.invoke(input=userMessage)


def htmlParserDetermine(url: URL):
    html_file, html_data, html_tokenCount = loadLoopFile(url.htmlPath)
    text_file, text_data, text_tokenCount = loadLoopFile(url.parseTextPath)
    vis_file, vis_data, vis_tokenCount = loadLoopFile(url.parseVisibleTextPath)

    if html_tokenCount <= 16000:
        return []
