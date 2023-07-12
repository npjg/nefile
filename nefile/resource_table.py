
from dataclasses import dataclass
import resource
import self_documenting_struct as struct
from enum import Enum, IntFlag

from .resources.bitmap import Bitmap
from .resources.icon import GroupIcon, Icon
from .resources.cursor import Cursor
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


## Declares each of the resource types and resources in this NE stream.
## The resource declarations are read immediately, but the resource data 
## is only parsed when requested.
class ResourceTable:
    BUILT_IN_RESOURCE_PARSERS = {
        ResourceType.RT_CURSOR: Cursor,
        ResourceType.RT_GROUP_ICON: GroupIcon,
        ResourceType.RT_STRING: StringTable
    }

    ## Reads a resource table from a binary stream.
    ## \param[in] stream - The binary stream positioned at the resource table start.
    ## \param[in] user_defined_resource_parsers - A dict that maps resource type IDs
    ##            to resource parser classes.
    def __init__(self, stream, user_defined_resource_parsers):
        # DEFINE THE RESOURCE PARSERS.
        # TODO: Support more built-in resources.
        self.resource_parsers = {
            ResourceType.RT_CURSOR: Cursor,
            ResourceType.RT_GROUP_ICON: GroupIcon,
            ResourceType.RT_STRING: StringTable
        }
        self.resource_parsers.update(user_defined_resource_parsers)
    
        # READ THE RESORUCE METADATA.
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

    ## Parses the resources in this resource table.
    ## The resources are always parsed in this order:
    ##  - Built-in types (ResourceType) in numerical order.
    ##  - All other types in the order they appear in the file.
    ##
    ## This ordering helps resolve dependencies within and among
    ## these groups. Built-in types with higher numerical order (like
    ## RT_GROUPICON) can depend on built-in types with lower numerical
    ## order (like RT_ICON). And user-defined types can depend on built-
    ## in types, and so forth.
    ##
    ## Built-in and user-defined types are parsed with the provided classes,
    ## any any other types have raw resource data read for processing later.
    @property
    def resources(self):
        # CHECK IF THE RESOURCES HAVE PREVIOUSLY BEEN PARSED.
        # Parsing resources can be expensive, so we cache the
        # parsing results after parsing the first time.
        if self._resources is not None:
            # RETURN THE CACHED RESOURCE DICTIONARY.
            return self._resources
        self._resources = {}

        # PARSE RESOURCES FROM THE BUILT-IN RESOURCE TYPES.
        # This loop guarantees the resource types are processed in definition order.
        for resource_type in ResourceType:
            resource_type_table = self.resource_type_tables.get(resource_type)
            if resource_type_table is not None:
                resources = self._parse_resources(resource_type_table)
                self._resources.update({resource_type_table.type_code: resources})

        # PARSE RESOURCES FROM ALL OTHER RESOURCE TYPES.
        # THese resource types are processed as they appear in the file.
        for resource_type_table in self.resource_type_tables.values():
            resource_already_parsed = ResourceType.has_value(resource_type_table.type_code)
            if not resource_already_parsed:
                resources = self._parse_resources(resource_type_table)
                self._resources.update({resource_type_table.type_code: resources})

        # RETURN THE PARSED RESOURCES.
        return self._resources

    ## Passes the actual data referenced by each resource declaration
    ## to the appropriate parsing class and returns the result.
    def _parse_resources(self, resource_type_table):
        # GET THE PARSER CLASS FOR THIS RESOURCE TYPE.
        defined_resource_parser = self.resource_parsers.get(resource_type_table.type_code, ApplicationDefinedData)

        # PARSE THE RESOURCES OF THIS TYPE.
        resources = {}
        for resource_declaration in resource_type_table.resource_declarations:
            self.stream.seek(resource_declaration.data_start_offset)
            resource = defined_resource_parser(self.stream, resource_declaration, self)
            resources.update({resource_declaration.id: resource})
        return resources

    ## Finds a resource by its type and resource ID.
    ## The type is required because two resources with different types
    ## can have the same resource ID.
    def find_resource_by_id(self, resource_id, type_id):
        return self.resources.get(type_id, {}).get(resource_id, None)

## Declares each of the resource types stored in this stream.
## Resource data is not actually accessible until the resources are parsed.
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

## Declares a resource stored in the stream.
## Resource data is not actually accessible until the resources are parsed.
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

    @property
    def data_end_offset(self):
        return self.data_start_offset + self.resource_length_in_bytes

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
