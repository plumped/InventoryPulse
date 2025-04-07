import os

def delete_file_if_exists(filefield):
    if filefield and hasattr(filefield, 'path') and os.path.isfile(filefield.path):
        os.remove(filefield.path)
