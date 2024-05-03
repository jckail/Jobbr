import os
import random
import time
import glob


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


def load_html(file_path):
    with open(file_path, "r") as file:
        data = file.read()
    return data


def get_number_of_characters(file_path):
    with open(file_path, "r") as file:
        contents = file.read().replace("\n", "")
    return len(contents)


def load_file(file_path):
    if file_path.endswith(".html"):
        return load_html(file_path)
    else:
        return None
