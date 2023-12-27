Like its namesake [`pefile`](https://github.com/erocarrera/pefile) does for the modern Portable Executable format, this `nefile` library parses the ancient 16-bit New Executable (NE) format. 

I drafted this library because here are not many good cross-platform tools for analyzing and extracting data (more than just code) from NE files. For instance, Ghidra is great at decompilation but not really at resources. `wrestool` and `icoutils` are the only tools I have found to date that can extract resources from NE files, but I ran into multiple issues using `wrestool`, including resources being corrupted upon extraction. 

This library fills the gap. Also, I just love Windows 3.1.

Currently there is read-only support for the NE header and resources, as that's all I need at the moment. Feel free to contribute if you need other functionality from Python!

## Spec References
The main spec reference used is the Microsoft Windows 3.1 Programmer's Reference, Volume 4 (Resources), referred to 
in the code as `W3.1PRV4`. 

The Microsoft MS-DOS Programmer's Reference helped provide insight into the DOS MZ header. 

## Installation
Get it [on PyPI](https://pypi.org/project/nefile/): ```pip3 install nefile```

## Usage

```python
import nefile
from nefile.resource_table import ResourceType

# OPEN THE WINDOWS 3.1 PROGRAM MANAGER.
progman = nefile.NE('/media/windows-3.1/WINDOWS/PROGMAN.EXE')
print(progman.header.target_operating_system) # <TargetOperatingSystem.WINDOWS_3X: 2>
print(progman.header.expected_windows_version) # 3.10
# See the resource types defined in Program Manager.
print(progman.resource_table.resource_type_tables.keys())
# Known resource types are replaced with an enum member. There can also be integer and string IDs
# for resource types that don't have a globally-defined type.
# dict_keys([<ResourceType.RT_GROUP_ICON: 14>, <ResourceType.RT_MENU: 4>, <ResourceType.RT_DIALOG: 5>, 
#            <ResourceType.RT_STRING: 6>, <ResourceType.RT_ACCELERATOR: 9>, <ResourceType.RT_VERSION: 16>,
#            <ResourceType.RT_ICON: 3>])
# 
# List all the bitmap resources defined in Program Manager.
print(progman.resource_table.resource_type_tables[ResourceType.RT_GROUP_ICON])
# Individual resource IDs are either integer or string IDs, as dictated in the file.
# {3: <nefile.resources.Resource object at 0x7f0d72c79fa0>, 6: <nefile.resources.Resource object at 0x7f0d72c7af40>, 
#  'DATAICON': <nefile.resources.Resource object at 0x7f0d72c7a0d0>, 'COMMICON': <nefile.resources.Resource object at 0x7f0d72c7afd0>, 
#  'MSDOSICON': <nefile.resources.Resource object at 0x7f0d72c7ab80>}

# OPEN THE WINDOWS 3.1 SHELL.
# This is where the famous easter egg is stored! I actually wrote this library
# because I wanted to get at those resources solely in Python and not bother
# with `wrestool`.
shell = nefile.NE('/media/windows-3.1/WINDOWS/SYSTEM/SHELL.DLL')
# dict_keys([<ResourceType.RT_BITMAP: 2>, <ResourceType.RT_DIALOG: 5>, <ResourceType.RT_STRING: 6>, 
#            <ResourceType.RT_RCDATA: 10>, <ResourceType.RT_VERSION: 16>, 100])
shell.export_resources("/root/shell")
# Produces files with names like "SHELL.DLL-RT_BITMAP-130.bmp".
```

## Tests
Test data is not included in this repository, but these are the sources  used:
* [630 Windows 3.x Games](https://archive.org/details/630-windows-3x-games)

To set up tests, create the `tests/test_data` directory and put NEs in there. Currently DLLs and EXEs are picked up.
If any turn out to be PE files or plain DOS EXEs, they will be marked as skipped in the tests. 

To run the tests, just run `pytest` from the root of the repository.