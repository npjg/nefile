
from dataclasses import dataclass
import resource
import self_documenting_struct as struct
from enum import Enum, IntFlag

from .resources.bitmap import Bitmap
from .resources.icon import GroupIcon, Icon
from .resources.application_defined_data import ApplicationDefinedData
from .resources.string import StringTable

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

    ## Returns true if the provided value is in this enum; False otherwise. 
    @classmethod
    def has_value(cls, value):
        return value in (val.value for val in cls.__members__.values())

## The resource table follows the segment table and contains entries 
## for each resource type and resource in this NE stream.
## Resource data itself is lazily loaded; the resources are only loaded when requested.
class ResourceTable:
    def __init__(self, stream):
        self.stream = stream
        self._resources = None
        self.resource_table_start_offset = stream.tell()
        # The shift count is the an exponent of 2 (left shift),
        # for calculating start offsets and lengths of resource data.
        self.alignment_shift_count = struct.unpack.uint16_le(stream)

        # READ THE RESOURCE TYPE DECLARATIONS (TTYPEINFO).
        self.resource_type_tables = {}
        resource_type = ResourceTypeTable(stream, self.alignment_shift_count, self.resource_table_start_offset)
        while not resource_type.is_end_flag:
            resource_dictionary_key = ResourceType(resource_type.type_code) if ResourceType.has_value(resource_type.type_code) else resource_type.type_code
            self.resource_type_tables.update({resource_dictionary_key: resource_type})
            resource_type = ResourceTypeTable(stream, self.alignment_shift_count, self.resource_table_start_offset)

    @property
    def resources(self):
        if self._resources is not None:
            # RETURN THE CACHED RESOURCE DICTIONARY.
            return self._resources

        # PROCESS RESOURCE TYPES THAT REQUIRE PRE-PROCESSING.
        # These resource types must be in the resource dictionary
        # since they might be referenced at any time by group resources,
        # and it is not guaranteed that group resources are read before 
        # the individual resources.
        self._resources = {
            ResourceType.RT_ICON: self._parse_icons(),
            ResourceType.RT_CURSOR: self._parse_cursors()
        }

        for resource_type_table in self.resource_type_tables.values():
            resource_pre_parsed = resource_type_table.type_code == ResourceType.RT_ICON or \
                resource_type_table.type_code == ResourceType.RT_CURSOR
            if resource_pre_parsed:
                continue

            # PARSE THE RESOURCES OF THIS TYPE.
            current_type_resources = {}
            for resource_declaration in resource_type_table.resource_declarations:
                # PARSE THIS INDIVIDUAL RESOURCE.
                resource = self._parse_other_resource(resource_declaration, resource_type_table.type_code)
                current_type_resources.update({resource_declaration.id: resource})

            self._resources.update({resource_type_table.type_code: current_type_resources})
        return self._resources

    ## Finds a resource by 
    def find_resource_by_id(self, resource_id, type_id):
        return self.resources.get(type_id, {}).get(resource_id, None)

    ## Constructs the icons in this resource table.
    ## These must be constructed first because the group resources refer to them.
    def _parse_icons(self):
        icon_resource_type_table = self.resource_type_tables.get(ResourceType.RT_ICON, None)
        icon_resources = {}
        if icon_resource_type_table is None:
            return icon_resources

        for resource_declaration in icon_resource_type_table.resource_declarations:
            self.stream.seek(resource_declaration.data_start_offset)
            icon = Icon(self.stream, resource_declaration, self)
            icon_resources.update({resource_declaration.id: icon})
        return icon_resources

    def _parse_cursors(self):
        cursor_resource_type_table = self.resource_type_tables.get(ResourceType.RT_CURSOR, None)
        cursor_resources = {}
        if cursor_resource_type_table is None:
            return cursor_resources

        for resource_declaration in cursor_resource_type_table.resource_declarations:
            self.stream.seek(resource_declaration.data_start_offset)
            cursor = Cursor(self.stream, resource_declaration, self)
            cursor_resources.update({resource_declaration.id: cursor})
        return cursor_resources

    def _parse_other_resource(self, resource_declaration, resource_type_code):
        self.stream.seek(resource_declaration.data_start_offset)
        if resource_type_code == ResourceType.RT_BITMAP:
            return Bitmap(self.stream, resource_declaration, self)
        elif resource_type_code == ResourceType.RT_GROUP_ICON:
            return GroupIcon(self.stream, resource_declaration, self)
        elif resource_type_code == ResourceType.RT_STRING:
            return StringTable(self.stream, resource_declaration, self)
        else:
            return ApplicationDefinedData(self.stream, resource_declaration, self)

## Declares each of the resource types stored in this stream,
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
        self.resource_declarations = []
        self.is_end_flag = False
        raw_type_data = struct.unpack.uint16_le(stream)
        if raw_type_data == 0x0000:
            self.is_end_flag = True
            return
        type_code_is_integer: bool = raw_type_data & 0x8000
        if type_code_is_integer:
            self.type_code = raw_type_data & 0x7fff
            self.type_code = ResourceType(self.type_code) if ResourceType.has_value(self.type_code) else self.type_code
        else:
            # This specifies the offset in bytes, relative to the start of the resource table,
            # where the string name for this type can be found.
            type_string_offset_from_file_start = resource_table_start_offset + raw_type_data
            self.type_code = ResourceString(stream, type_string_offset_from_file_start).string

        # READ THE RESOURCE DECLARATIONS FOR THIS TYPE.
        resource_count = struct.unpack.uint16_le(stream)
        # TODO: Document this, if it can be documented.
        self.reserved = stream.read(4)
        for index in range(resource_count):
            resource_declaration = ResourceDeclaration(stream, alignment_shift_count, resource_table_start_offset)
            self.resource_declarations.append(resource_declaration)

## Reads a resource stored in the stream.
class ResourceDeclaration:
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
