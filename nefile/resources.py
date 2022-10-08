
from dataclasses import dataclass
import self_documenting_struct as struct
from enum import Enum, IntFlag
from typing import Optional

## I did not know exactly what the NE resource types are,
## so I copied the relevant ones from the Win32 documentation:
## https://learn.microsoft.com/en-us/windows/win32/menurc/resource-types.
class ResourceType(Enum):
    RT_CURSOR = 1
    RT_BITMAP = 2
    RT_ICON = 3
    RT_MENU = 4
    RT_DIALOG = 5
    RT_STRING = 6
    RT_FONTDIR = 7
    RT_FONT = 8
    RT_ACCELERATOR = 9
    RT_RCDATA = 10
    RT_MESSAGETABLE = 11
    RT_GROUP_CURSOR = 12
    # There is no resource 0x0b.
    RT_GROUP_ICON = 14
    RT_VERSION = 16

    ## Returns true if the provided value is in this enum; false otherwise. 
    @classmethod
    def has_value(cls, value):
        return value in (val.value for val in cls.__members__.values())

## The resource table follows the segment table and contains entries 
## for each resource type and resource in this NE stream.
class ResourceTable:
    def __init__(self, stream):
        self.resource_table_start_offset = stream.tell()
        # The shift count is the an exponent of 2 (left shift),
        # for calculating start offsets and lengths of resource data.
        self.alignment_shift_count = struct.unpack.uint16_le(stream)

        # READ THE RESOURCE TYPE DECLARATIONS (TTYPEINFO).
        self.resource_types = {}
        resource_type = ResourceTypeTable(stream, self.alignment_shift_count, self.resource_table_start_offset)
        while not resource_type.is_end_flag:
            resource_dictionary_key = ResourceType(resource_type.type_code) if ResourceType.has_value(resource_type.type_code) else resource_type.type_code
            self.resource_types.update({resource_dictionary_key: resource_type.resources})
            resource_type = ResourceTypeTable(stream, self.alignment_shift_count, self.resource_table_start_offset)

## Declares each of the resource types stored in this stream.
class ResourceTypeTable:
    def __init__(self, stream, alignment_shift_count, resource_table_start_offset):
        # READ THE RESOURCE TYPE INFORMATION.
        # There must be one resource type info entry for each type
        # of resource in the executable stream.
        #
        # This is an integer type if the high-order bit is 
        # set (8000h); otherwise, it is an offset to the type string.
        # The offset is relative to the beginning of the resource
        # table. 
        self.is_end_flag = False
        raw_type_data = struct.unpack.uint16_le(stream)
        if raw_type_data == 0x0000:
            self.is_end_flag = True
            return
        type_code_is_integer: bool = raw_type_data & 0x8000
        if type_code_is_integer:
            self.type_code = raw_type_data & 0x7fff
        else:
            # This specifies the offset in bytes, relative to the start of the resource table,
            # where the string name for this type can be found.
            type_string_offset_from_file_start = resource_table_start_offset + raw_type_data
            self.type_code = ResourceString(stream, type_string_offset_from_file_start)

        # READ THE NUMBER OF RESOURCES OF THIS TYPE.
        resource_count = struct.unpack.uint16_le(stream)

        # TODO: Document this, if it can be documented.
        self.reserved = stream.read(4)

        # READ THE RESOURCES OF THIS TYPE.
        self.resources = {}
        for index in range(resource_count):
            resource = Resource(stream, alignment_shift_count, resource_table_start_offset)
            self.resources.update({resource.id: resource})

## Reads a resource stored in the stream.
class Resource:
    class ResourceFlags(IntFlag):
        MOVEABLE = 0x0010,
        PURE = 0x0020,
        # If the resource is not preloaded, it is loaded on demand.
        PRELOAD = 0x0040

    def __init__(self, stream, alignment_shift_count, resource_table_start_offset):
        # READ THE RESOURCE METADATA.
        # This offset is relative to the start of the stream,
        # not the Windows header like most of the other offsets.
        self.data_start_offset = struct.unpack.uint16_le(stream) << alignment_shift_count
        self.resource_length_in_bytes = struct.unpack.uint16_le(stream) << alignment_shift_count
        self.flags = self.ResourceFlags(struct.unpack.uint16_le(stream))

        # READ THE RESOURCE ID/NAME.
        # This is an integer ID if the high-order
        # bit is set (8000h), otherwise it is the offset to the
        # resource string. This offset is relative to the
        # beginning of the resource table.
        raw_id_data: int = struct.unpack.uint16_le(stream)
        id_is_integer: bool = raw_id_data & 0x8000
        if id_is_integer:
            self.id = raw_id_data & 0x7fff
        else:
            # This specifies the offset in bytes, relative to the start of the resource table,
            # where the string name for this type can be found.
            id_string_offset_from_file_start = resource_table_start_offset + raw_id_data
            self.id = ResourceString(stream, id_string_offset_from_file_start).string
        # TODO: Document this, if it can be documented.
        self.reserved = stream.read(4)

        # READ THE RESOURCE DATA.
        saved_stream_position = stream.tell()
        stream.seek(self.data_start_offset)
        self.data = stream.read(self.resource_length_in_bytes)
        stream.seek(saved_stream_position)

## Reads a resource name or type string by seeking to the correct offset.
## These strings are Pascal strings - case-sensitive and not null-terminated.
class ResourceString:
    def __init__(self, stream, offset_from_stream_start):
        saved_stream_position = stream.tell()
        stream.seek(offset_from_stream_start)
        string_length = struct.unpack.uint8(stream)
        if string_length > 0:
           # For NE streams, ASCII should always be used.
           self.string = stream.read(string_length).decode('ascii')
        else:
            self.string = ''

        stream.seek(saved_stream_position)
