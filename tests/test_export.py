#! python3

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
        # ATTEMPT TO EXPORT THE RESOURCES IN THIS NE.
        try:
            f = nefile.NE(binary)
            f.export_resources(temp_export_dir)
            # TODO: Check to make sure the bitmaps have the expected size and everything.

        # CATCH TEST DATA ISSUES.
        # I still need to remove some DOS executables and PEs from the dataset, 
        # but for now we will just skip these.
        except (nefile.Exceptions.NotValidNewExecutableError, nefile.Exceptions.IsPortableExecutableError) as e:
            pytest.skip(f'Skipping as this is likely an issue with test data and not our code: {str(e)}')

        # CATCH ALL OTHER ISSUES.
        # We do want to fail the test in this case.
        except Exception as e:
            # Include the temp directory path in the error message.
            pytest.fail(f'Error: {binary} {type(e).__name__} {str(e)}\n'
                        f'Temp directory: {temp_export_dir}\n'
                        f'{traceback.format_exc()}')

# This isn't required for running the tests from the `pytest` command line,
# but it is useful to be able to debug tests in VS Code.
if __name__ == "__main__":
    pytest.main()