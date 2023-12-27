#! python3

import glob
import pytest
import tempfile
import traceback
import os

import nefile

# FIND ALL NE DLLs and EXEs IN THE TEST FOLDER.
# The current working directory MUST be the root of the repository, not the tests directory.
# If the current directory is not correct, there will be no items found and so the file 
# will be marked as skipped. You need to run `pytest -rs` to see this, though.
# TODO: Let it be run from the tests directory too, it will just be more code.
def find_dll_and_exe_files(directory):
    """
    Recursively search for .dll and .exe files in the given directory, case-insensitively.

    Args:
    directory (str): The directory to search in.

    Returns:
    list: A list of paths to the found .dll and .exe files.
    """
    files = []
    for root, dirs, filenames in os.walk(directory):
        for filename in filenames:
            if filename.lower().endswith(('.dll', '.exe')):
                files.append(os.path.join(root, filename))
    return files
binaries = find_dll_and_exe_files('tests/test_data')

@pytest.mark.parametrize("binary", binaries)
def test_nefile_export(binary):
    # Create a temporary directory for export
    with tempfile.TemporaryDirectory() as temp_export_dir:
        # 
        f = nefile.NE(binary)

        # ATTEMPT TO EXPORT THE RESOURCES IN THIS NE.
        try:
            f.export_resources(temp_export_dir)
        except Exception as e:
            # Include the temp directory path in the error message
            pytest.fail(f'Error: {binary} {type(e).__name__} {str(e)}\n'
                        f'Temp directory: {temp_export_dir}\n'
                        f'{traceback.format_exc()}')
