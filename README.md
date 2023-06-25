Like its namesake [`pefile`](https://github.com/erocarrera/pefile) does for the modern Portable Executable format, this `nefile` library parses the ancient 16-bit New Executable (NE) format.I
I drafted this library because here are not many good cross-platform tools for analyzing and extracting data (more than just code) from NE files. For instance, Ghidra is great at decompilation but not really at resources. This library fills that gap. Also, I just love Windows 3.1.

Currently there is read-only support for the NE header and resources, as that's all I need at the moment. Feel free to contribute if you need other functionality!

## Example Usage

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
# Produces files with names like "SHELL.DLL-RT_BITMAP-130.bmp"
```