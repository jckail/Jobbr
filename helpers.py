import os
import random
import time
import glob
from db import supabase
import time


def download_from_supa_base(remote_path, bucket_id, local_path=None):
    if not local_path:
        local_path = remote_path
    with open(local_path, "wb+") as f:
        res = supabase.storage.from_(bucket_id).download(remote_path)
        f.write(res)
    return local_path


def appendUnixTime(fileName):
    return str(int(time.time())) + "_" + fileName


def upload_to_supa_base(local_path, bucket_id, remote_path=None):
    # Open the file in binary mode and upload
    local_path = local_path.replace(f"{os.getcwd()}/", "")
    if not remote_path:
        remote_path = local_path
    with open(local_path, "rb") as f:
        supabase.storage.from_(bucket_id).upload(file=f, path=remote_path)
    return remote_path


def save_text_to_file(file_path, text):
    try:
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(text)
            # print(f"Text saved to file {file_path}")
    except IOError as e:
        print(f"Error saving text to file {file_path}: {e}")
        # Optionally, you might


def appendFile(file_path, fileName, text):
    try:
        with open(file_path, "a", encoding="utf-8") as file:
            file.write(fileName + ": \n" + text + "\n \n")
            # print(f"Text appended to file {file_path}")
    except IOError as e:
        print(f"Error appending text to file {file_path}: {e}")


def create_directory(path):
    """
    Creates a directory at the specified path if it does not already exist.

    Parameters:
    - path (str): The path where the directory will be created.

    Returns:
    None
    """
    try:
        # Check if the directory already exists
        if not os.path.exists(path):
            # Create the directory, including any intermediate directories
            os.makedirs(path)
            # print(f"Directory created at: {path}")
        else:
            print(f"Directory already exists at: {path}")
    except Exception as e:
        print(f"An error occurred while creating the directory: {e}")


def random_sleep(min=5, max=15):
    # Generate a random number between 5 and 15
    sleep_time = random.randint(10, 15)
    # Sleep for the generated number of seconds
    time.sleep(sleep_time)
    print(f"Slept for {sleep_time} seconds")


def filter_files_on_suffix(file_list, suffixes):
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
    return html_files


def get_number_of_characters(file_path):
    with open(file_path, "r") as file:
        contents = file.read().replace("\n", "")
    return len(contents)


def load_html(file_path):
    if file_path.endswith(".html"):
        with open(file_path, "r") as file:
            data = file.read()
        return data


def load_txt(file_path):
    if file_path.endswith(".txt"):
        with open(file_path, "r") as file:
            data = file.read()
        return data


def load_file(file_path):
    try:
        if file_path.endswith(".html"):
            return load_html(file_path)
        elif file_path.endswith(".txt"):
            return load_txt(file_path)
        else:
            return None

    except Exception as e:
        print(f"Failed to load file {file_path}: {str(e)}")
