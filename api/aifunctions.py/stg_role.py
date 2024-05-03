## GIVEN a URL object run this: w/ mapps to
import glob
import os


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


def process_file(file):

    max_tries = 3
    tries = 0
    dump = None
    model = "3.5"

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
            # print("\n----\n\n----\n")
            # print("\n--x[raw]--\n", x, "\n----")
            # z = x["raw"]
            # # print("\n----\n", z.response_metadata, "\n----")
            # # print("\n----\n", z, "\n----")
            # print(f"\n--Parsed--\n {z.content[0]} \n----\n")
            # print(f"\n--Parsed--\n {x["parsed"]} \n----\n")

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
    file = "scraped_data/google/text_detail/about_careers_applications_jobs_results_data_engineer_machine_learning_125881358477075142_visible_text.txt"

    import traceback

    import time

    init_db()
    # process_file(file)

    # with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
    #     executor.map(process_file, get_all_html_files(directory, "txt"))
    # Define a function to process a file and return the result if any
