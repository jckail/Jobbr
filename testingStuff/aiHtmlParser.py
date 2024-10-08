import glob
import random
import os
import time


from sqlmodel import Session


from db import init_db, engine
from models import (
    AIFunctionRunBase,
    AIFunctionRun,
    AIFunctionResult,
    Stg_RoleBase,
    Stg_Role,
)
from ai import htmlParsers

##TODO create timer functions so that we can better see timing
## TODO test against langchain outputs etc its going to be better than this i think


def filter_files(file_list):
    suffixes = ["_visible_text.txt", "_script_texts.txt", "_meta_contents.txt"]
    # Filter the list to exclude files that end with the specified suffixes
    filtered_list = [
        file
        for file in file_list
        if not any(file.endswith(suffix) for suffix in suffixes)
    ]
    return filtered_list


def get_all_html_files(directory, file_type):
    html_files = []
    for subdir in os.scandir(directory):
        if subdir.is_dir():
            html_files.extend(
                glob.glob(f"{subdir.path}/**/*.{file_type}", recursive=True)
            )
    return filter_files(html_files)


def load_html(file_path):
    with open(file_path, "r") as file:
        data = file.read()
    return data


def get_number_of_characters(file_path):
    with open(file_path, "r") as file:
        contents = file.read().replace("\n", "")
    return len(contents)


def random_sleep():
    # Generate a random number between 5 and 15
    sleep_time = random.randint(10, 15)
    # Sleep for the generated number of seconds
    time.sleep(sleep_time)
    print(f"Slept for {sleep_time} seconds")


def loadLoopFile(file: str):
    try:
        print(file)
        html = load_html(file)
        tokenCount = len(html) // 4
        return html, tokenCount
    except Exception as e:
        print(f"Failed to intially load file {file}: {str(e)}")


# scraped_data/google/about_careers_applications_jobs_results_data_engineer_machine_learning_125881358477075142_visible_text.txt


def process_file(file):

    max_tries = 3
    tries = 0
    dump = None
    model = "3.5"
    print(file)
    while tries < max_tries:
        tries += 1
        html, tokenCount = loadLoopFile(file)
        if tokenCount >= 16000 and tries == 1:
            try:
                file = file.replace(".txt", "_visible_text.txt")
                html, tokenCount = loadLoopFile(file)
            except Exception as e:
                print(f"Failed to load file {file}: {str(e)}")

        if tries == 2 or tokenCount >= 16000:
            model = "claude"

        if tries == 3:
            model = "4"
            file = file.replace(".txt", ".html")
            html, tokenCount = loadLoopFile(file)
        tokenMax = 75000
        if tokenCount > tokenMax:
            # raise exception too many tokens in one query
            raise Exception(f"Too many tokens in one query, max set to {tokenMax}")

        print(
            f"\n\n-----\n\nModel:{model}\nParsing: {file} \n Tokens: {tokenCount} \n Try:{tries}\n\n-----\n"
        )
        # TODO: VECTORIZE THE HTML FILE*
        try:

            # this should be populated within the call to AIFunctionRun
            a = {
                "input_model": model,
                "tokenCount": tokenCount,
                "function": "parseStg_RoleHtml",
                "tries": tries,
                "file_source": file,
                "url": None,
            }
            aib = AIFunctionRunBase(**a)
            air = AIFunctionRun(**aib.model_dump())

            dump = air.model_dump()
            with Session(engine) as session:
                session.add(air)
                session.commit()
                
            model = "claude"
            fkid = dump.pop("id", None)
            if model == "4":
                x = htmlParsers.parseHTMLgpt4(html)
            elif model == "3.5":
                x = htmlParsers.parseHTMLgpt3(html)
            elif model == "claude":
                x = htmlParsers.parseHTMLClaud3(html)
            else:
                raise ValueError("Model not supported")

            #
            print("\n----\n\n----\n")
            print("\n--x[raw]--\n", x, "\n----")
            z = x["raw"]
            # print("\n----\n", z.response_metadata, "\n----")
            # print("\n----\n", z, "\n----")
            print(f"\n--Parsed--\n {z.content[0]} \n----\n")
            print(f"\n--Parsed--\n {x["parsed"]} \n----\n")

            if not x["parsed"]:
                raise ValueError("No parsed response from model")

            payload = x["parsed"]
            role = Stg_Role(
                **payload,
                AIFunctionRun_id=fkid,
                file_source=file,
            )
            z = x["raw"]
            # print(f"n\n\ncontent {z.content}\n\n\n")
            
            if model in ["3.5", "4"]:

                airR = AIFunctionResult(
                    **a,
                    AIFunctionRun_id=fkid,
                    success=True,
                    message="success",
                    model=z.response_metadata["model_name"],
                    response_id=z.response_metadata["system_fingerprint"],
                    stop_reason=z.response_metadata["finish_reason"],
                    stop_sequence=None,
                    input_tokens=z.response_metadata["token_usage"]["prompt_tokens"],
                    output_tokens=z.response_metadata["token_usage"][
                        "completion_tokens"
                    ],  # openai  completion_tokens #claude output_tokens
                    parsing_error=str(x["parsing_error"]),
                )
            elif model == "claude":
                airR = AIFunctionResult(
                    **a,
                    AIFunctionRun_id=fkid,
                    success=True,
                    message="success",
                    model=z.response_metadata["model"],
                    response_id=z.response_metadata["id"],
                    stop_reason=z.response_metadata["stop_reason"],
                    stop_sequence=z.response_metadata["stop_sequence"],
                    input_tokens=z.response_metadata["usage"]["input_tokens"],
                    output_tokens=z.response_metadata["usage"][
                        "output_tokens"
                    ],  # openai  completion_tokens #claude output_tokens
                    parsing_error=str(x["parsing_error"]),
                )
            with Session(engine) as session:
                session.add(role)
                session.add(airR)
                session.commit()
            print(
                f"\n\n---Completed---\n\nModel:{model}\nParsing: {file} \n Tokens: {tokenCount} \n Try:{tries}\n\n-----\n"
            )
            return True
        except Exception as e:

            print(f"\n Failed to process file {file}. Error: {e}")
            traceback.print_exc()  # This will print the stack trace
            if tries < max_tries:
                print(f"Retrying in 5 seconds... (Attempt {tries+1} of {max_tries})")
                random_sleep()
            else:
                print(f"Failed to process file {file} after {max_tries} attempts.")
            try:
                airR = AIFunctionResult(
                    **a, AIFunctionRun_id=fkid, success=False, message=str(e)
                )
                with Session(engine) as session:
                    session.add(airR)
                    session.commit()
            except Exception as e:
                print(f"Failed to log error for file {file}. Error: {e}")

    print(
        f"\n\n---Failed---\n\nModel:{model}\nParsing: {file} \n Tokens: {tokenCount} \n Try:{tries}\n\n-----\n"
    )

    return False


if __name__ == "__main__":
    file = "/Users/jordankail/Jobbr/scraped_data/openai/careers_analytics_data_engineer_applied_engineering.txt"
    file = "scraped_data/plaid/careers_openings_engineering_san_francisco_data_engineer_data_engineering.txt"
    file = "scraped_data/plaid/careers_openings_engineering_san_francisco_data_engineer_data_engineering.txt"
    directory = "scraped_data/"
    file = "/Users/jordankail/Jobbr/scraped_data/snagajob/jobs_searchResponseId_2afb5ec0_4a6d_aa1e_262034b76995_searchRequestId_e5e2248d_2dd5_44d2_819d_78b0cdd2ad07_promo_532620979.html"

    import concurrent.futures

    import traceback

    import time

    init_db()
    process_file(file)

    # with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
    #     executor.map(process_file, get_all_html_files(directory, "txt"))
    # Define a function to process a file and return the result if any

    # def process_and_yield(file):
    #     result = process_file(file)
    #     if result:
    #         return result
    #     print("thread_sleeping")
    #     random_sleep()

    # # Get all HTML files in the directory
    # files = get_all_html_files(directory, "txt")

    # # Submit tasks to the executor and process the results as they complete
    # with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
    #     futures = [executor.submit(process_and_yield, file) for file in files]
    #     for future in concurrent.futures.as_completed(futures):
    #         result = future.result()
    #         if result:
    #             print(result)
    #             # Do something with the result
