import os


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
