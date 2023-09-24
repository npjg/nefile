
from enum import Enum, IntFlag
import mmap
import os
from typing import Optional

import self_documenting_struct as struct
from . import resource_table
from . import Exceptions

## Models the header information for the DOS (MZ) stub.
class MZ:
    def __init__(self, stream):
        # VERIFY THE MZ SIGNATURE.
        actual_signature = stream.read(2)
        if actual_signature != b'MZ':
            raise Exceptions.NotValidNewExecutableError(
                'This is not a valid NE file, as it does not start with an MZ stub. '
                'The file might be packed or corrupt.')

        # READ THE NE HEADER START OFFSET.
        # "If the word value at offset 18h is 40h or greater, the word value at 3Ch
        #  is an offset to a Windows header." (W3.1PRV4, p. 69)
        # TODO: Look at the DOS Programmer's Manual to determine what this field actually is.
        stream.seek(0x18)
        has_offset_to_ne_header = (struct.unpack.uint16_le(stream) >= 0x40)
        if not has_offset_to_ne_header:
            raise Exceptions.NotValidNewExecutableError(
                "This is not a valid NE file, as the DOS header doesn't have an offset to an NE header." 
                'The file might be packed or corrupt.')
        stream.seek(0x3c)
        self.ne_header_offset = struct.unpack.uint16_le(stream)

## Models a New Executable file.
class NE:
    def __init__(self, filepath: str = None, stream = None, user_defined_resource_parsers = {}):
        # MAP THE FILE DATA.
        # A filepath can be provided to open a file from disk, or an in-memory binary stream can be provided.
        # However, providing both of these is an error.
        # First, we see if the data sources are ambiguous.
        more_than_one_data_source_provided: bool = filepath is not None and stream is not None
        if more_than_one_data_source_provided:
            raise ValueError(
                'A filepath and a stream cannot both be provided to define a stream. ' 
                'The data source of the file would be ambiguous')
        only_filepath_provided = filepath is not None
        if only_filepath_provided:
            # MAP THE DATA AT THIS FIELPATH TO A BINARY STREAM WITH READ-ONLY ACCESS.
            with open(filepath, mode = 'rb') as file:
                # By specifying a length of zero, we will map the whole stream.
                self.stream = mmap.mmap(file.fileno(), length = 0, access = mmap.ACCESS_READ)
        only_stream_provided: bool = stream is not None
        if only_stream_provided:
            # USE THE EXISTING STREAM.
            # This is useful for fully in-memory files (like files read from an archive)
            # and never stored on the filesystem.
            self.stream = stream
        self.filepath = filepath

        # READ THE DOS (MZ) HEADER.
        self.mz = MZ(self.stream)
        self.stream.seek(self.mz.ne_header_offset)

        # READ THE NE HEADER.
        # This is sometimes calld a Windows header, 
        # but it could be for another platform too.
        self.header = NEHeader(self.stream)

        # READ THE RESOURCE TABLE.
        try:
            self.stream.seek(self.header.resource_table_offset)
            self.resource_table = resource_table.ResourceTable(self.stream, user_defined_resource_parsers)
        except ValueError:       
            # TODO: Make this specifically look for a seek error.
            # Some NEs don't have resource table, as verified by 
            # wrestool and ResourcesExtract, even though there is 
            # a valid pointer to a resource table, and this pointer
            # isn't the same as pointers to other structures in the 
            # NE. It looks like wrestool can't do any better than this
            # and just gives up when the resource table has a nonsensical pointer.
            print(f'INFO [{self.filepath}]: Could not parse resource table. '
                'The executable probably has no resource table.')
            self.resource_table = None

    @property
    def filename(self):
        return os.path.split(self.filepath)[1]

    def export_resources(self, directory_path):
        print(f'Exporting resources for {self.filepath}')
        if self.resource_table is None:
            return 
        
        for resource_type_code, resource_type in self.resource_table.resources.items():
            resource_type_string: str = resource_type_code.name if isinstance(resource_type_code, Enum) else resource_type_code
            for resource_id, resource in resource_type.items():
                export_filename = f'{self.filename}-{resource_type_string}-{resource_id}'
                export_filepath = os.path.join(directory_path, export_filename)
                resource.export(export_filepath)

## Models an NE header. This is sometimes called a "Windows header",
## but that is not quite correct as other platforms like OS/2 can use this header too.
## Because of the age of the format some items are unclear in meaning.
## TODO: Straighten up the format based on Windows 3.1 SDK Programmer's Reference, Vol. 4.
class NEHeader:
    class ExecutableContent(IntFlag):
        # Set if the file is a dynamic-link library (DLL). Contains only one one data segment. 
        SINGLE_DATA_SEGMENT = 0x0001
        # Set if the file is a Windows application. Contains multiple data segments.
        # If the file is neither single nor multiple, there is no automatic data segment. 
        MULTIPLE_DATA_SEGMENTS = 0x0002
        PER_PROCESS_LIBRARY_INITIALIZATION = 0x0004
        PROTECTED_MODE_ONLY = 0x0008
        INSTRUCTIONS_8086 = 0x0010
        INSTRUCTIONS_80286 = 0x0020
        INSTRUCTIONS_80386 = 0x0040
        # Floating-point instructions.
        INSTRUCTIONS_80x87 = 0x0080
        USES_PRESENTATION_MANAGER_API = 0x0300
        COMPATIBLE_WITH_PRESENTATION_MANAGER_API = 0x0200
        NOT_COMPATIBLE_WITH_PRESENTATION_MANAGER_API = 0x0100
        # Set if the first segment contains code that loads the application.
        CUSTOM_LOADER = 0x0800,
        # The linker has detected errors but still created an application.
        LINKER_DETECTED_ERRORS = 0x2000,
        # Set if the executable file is a library module (not a process).
        IS_LIBRARY = 0x8000

    ## Specifies the operating system this executable targets.
    class TargetOperatingSystem(Enum):
        # Any new-style operating system
        UNKNOWN = 0x00
        # TODO: Is this all OS/2 applications?
        OS2 = 0x01
        # Windows 3.x (Win16)
        WINDOWS_3X = 0x02
        # European MS-DOS 4.x
        MSDOS_4 = 0x03
        # Windows/386
        WINDOWS_386 = 0x04
        # Borland Operating System Services
        BOSS = 0x05
        PHARLAP_286_DOS_EXTENDER_OS2 = 0x81
        PHARLAP_286_DOS_EXTENDER_WINDOWS = 0x82

    def __init__(self, stream):
        # VERIFY THE SIGNATURE.
        self.start_offset = stream.tell()
        actual_signature = stream.read(2)
        if (actual_signature != b'NE'):
            # CHECK IF THIS IS ACTUALLY A PE.
            # We can show a better error message.
            if actual_signature == b'PE':
                raise Exceptions.IsPortableExecutableError(
                    'This appears to be a PE file, not an NE file. Use the pefile library instead.')
            # If we have gotten to this point, we know we have a valid MZ signature,
            # because that is checked before we read the offset to the NE program.
            raise Exceptions.NotValidNewExecutableError(
                f'This does not contain a valid NE signature, but it has a valid MZ (DOS-style) signature. '
                'The file might be packed or corrupted.')

        # READ THE HEADER DATA.
        # These fields don't really follow a logical progression,
        # so I won't try to categorize them.
        self.linker_version_number = struct.unpack.uint8(stream)
        self.linker_revision_number = struct.unpack.uint8(stream)
        # This offset is relative to the start of this Windows header.
        self.entry_table_offset = struct.unpack.uint16_le(stream)
        self.entry_table_length_in_bytes = struct.unpack.uint16_le(stream)
        # TODO: Is this always a CRC-32? Some resources list it as reserved.
        # This is set to 0 in Borland's TPW.
        self.crc32 = struct.unpack.uint32_le(stream)
        self.executable_content_flags = self.ExecutableContent(struct.unpack.uint16_le(stream))
        self.automatic_data_segment_number = struct.unpack.uint16_le(stream)
        self.initial_heap_size_in_bytes = struct.unpack.uint16_le(stream)
        self.initial_stack_size_in_bytes = struct.unpack.uint16_le(stream)
        self.cs_ip_segment_offset = struct.unpack.uint32_le(stream)
        # The value specified in SS is an index to the module's segment table. 
        # The first entry in the segment table corresponds to segment number 1.
        # If SS addresses the automatic data segment and SP is zero, 
        # SP is set to the address obtained by adding the size of the
        # automatic data segment to the size of the stack. 
        self.ss_sp_segment_offset = struct.unpack.uint32_le(stream)
        self.segment_table_entry_count = struct.unpack.uint16_le(stream)
        self.module_reference_table_count = struct.unpack.uint16_le(stream)
        self.nonresident_name_table_size_in_bytes = struct.unpack.uint16_le(stream)
        # All of these offsets are from the start of this header.
        self._segment_table_offset_from_header_start = struct.unpack.uint16_le(stream)
        self._resource_table_offset_from_header_start = struct.unpack.uint16_le(stream)
        self._resident_name_table_offset_from_header_start = struct.unpack.uint16_le(stream)
        self._module_reference_table_offset_from_header_start = struct.unpack.uint16_le(stream)
        self._imported_name_table_offset_from_header_start = struct.unpack.uint16_le(stream)
        # This offset is from the start of this stream.
        self.nonresident_name_table_offset = struct.unpack.uint32_le(stream)
        self.entry_table_movable_entry_count = struct.unpack.uint16_le(stream)
        # This is log(base 2) of the segment sector size (default 9).
        # (This  value corresponds  to the  /alignment [/a] linker switch.
        #  When the linker command line contains  /a:16, the shift count is  4. 
        #  When the linker command line  contains /a:512, the shift count is 9.)
        self.logical_sector_alignment_shift_count = struct.unpack.uint16_le(stream)
        self.resource_entry_count = struct.unpack.uint16_le(stream)
        self.target_operating_system = self.TargetOperatingSystem(struct.unpack.uint8(stream))
        # TODO: Docuemnt these flags.
        self.os2_flags = struct.unpack.uint8(stream)
        # Offset to return thunks or start of gangload area - what is gangload?
        # TODO: Document this field.
        self.thunk_offset = struct.unpack.uint16_le(stream)
        # Offset to segment reference thunks or size of gangload area.
        # TODO: Document this field.
        self.segment_reference_thunks = struct.unpack.uint16_le(stream)
        self.minimum_code_swap_area_size_in_bytes = struct.unpack.uint16_le(stream)
        self.expected_windows_revision = struct.unpack.uint8(stream)
        self.expected_windows_major_version = struct.unpack.uint8(stream)

    ## Returns the expected Windows version in <Major Version>.<Revision> format.
    @property
    def expected_windows_version(self) -> str:
        return f'{self.expected_windows_major_version}.{self.expected_windows_revision}'

    ## Calculates the offset of the resource table from the start of the stream.
    ## The offset actually stored is the offset of the resource table from the
    ## start of this header.
    @property
    def resource_table_offset(self) -> Optional[int]:
        return self.start_offset + self._resource_table_offset_from_header_start
    
    ## Returns true if there is a local heap allocated; false otherwise.
    @property
    def local_heap_allocated(self) -> bool:
        return self.initial_heap_size_in_bytes > 0
