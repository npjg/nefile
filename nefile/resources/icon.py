
import self_documenting_struct as struct
import os
from .bitmap import BitmapInfoHeader

## Reads an RT_GROUP_ICON resource.
## In the executable, the RT_GROUP_ICON resource itself 
## only holds the icon directory for the icons in the group, so
## we must look up the icons elsewhere in this resource library.
## \param[in] resource - The resource to be modeled by this class.
## \param[in] resource_table - The full resource table from the executable.
class GroupIcon:
    def __init__(self, stream, resource_declaration, resource_table):
        self.resource_id = resource_declaration.id
        self.icons = {}
        self.icon_directory = IconDirectory(stream)
        for index in range(self.icon_directory.icon_count):
            # GET THE REFERENCED ICON.
            from nefile.resource_table import ResourceType
            icon_directory_entry = IconDirectoryEntry(stream, as_group_entry = True)
            referenced_icon = resource_table.find_resource_by_id(icon_directory_entry.icon_resource_id, type_id = ResourceType.RT_ICON)
            self.icons.update({icon_directory_entry.icon_resource_id: referenced_icon})

    ## Exports this resource as a BMP file.
    ## @param[in] filepath - The filepath of the file to export.
    ##            A suffix will be added with the resource type and ID
    ##            to make this filepath unique.
    def export(self, filepath):
        for index, icon in enumerate(self.icons.values()):
            with open(filepath + ".ico", 'wb') as icon_file:
                icon.write_ico_file(icon_file)

## Reads/writes the first structure in an ICO file (ICONDIR) 
## and RT_GROUP_ICON resource (GRPICONDIR).
class IconDirectory:
    LENGTH_IN_BYTES = 0x06
    def __init__(self, stream = None):
        self.signature: int = 0x0000
        self.type: int = 0x0001
        self.icon_count: int = 0x0000
        if stream is not None:
            self.decode(stream)

    def decode(self, stream):
        self.signature = struct.unpack.uint16_le(stream)
        assert self.signature == 0x0000
        self.type = struct.unpack.uint16_le(stream)
        self.icon_count = struct.unpack.uint16_le(stream)

    def encode(self, stream):
        stream.write(struct.pack.uint16_le(self.signature))
        stream.write(struct.pack.uint16_le(self.type))
        stream.write(struct.pack.uint16_le(self.icon_count))

## Read/writes the ICONDIRENTRY and GRPICONENTRY structures.
## The GRPICONDIRENTRY structure is the same as the usual ICONDIRENTRY structure,
## except the last entry specifies the resource ID of the referenced icon,
## rather than the offset to the icon in the file.
## (Source: https://devblogs.microsoft.com/oldnewthing/20120720-00/?p=7083)
class IconDirectoryEntry:
    LENGTH_IN_BYTES = 0x10
    GROUP_LENGTH_IN_BYTES = 0x0e
    def __init__(self, stream = None, as_group_entry: bool = False):
        self.width = None
        self.height = None
        # Should be 0 if the image does not use a color palette.
        self.total_palette_colors = None
        self.color_planes = None
        self.bits_per_pixel = None
        self.icon_size_in_bytes = None
        self.icon_resource_id = None
        self.bitmap_start_offset = None
        if stream is not None:
            self.decode(stream, as_group_entry)

    ## Populates the fields of this class with values unpacked from a binary stream.
    ## @param[in] as_group_entry - True if the stream contains a GRPICONDIRENTRY structure,
    ##                             False if the stream contains a plain ICONDIRENTRY structure.
    def decode(self, stream, as_group_entry: bool):
        self.width = struct.unpack.uint8(stream)
        self.height = struct.unpack.uint8(stream)
        # Should be 0 if the image does not use a color palette.
        self.total_palette_colors = struct.unpack.uint16_le(stream)
        self.color_planes = struct.unpack.uint16_le(stream)
        self.bits_per_pixel = struct.unpack.uint16_le(stream)
        self.icon_size_in_bytes = struct.unpack.uint32_le(stream)
        if as_group_entry:
            self.icon_resource_id = struct.unpack.uint16_le(stream)
        else:
            self.bitmap_start_offset = struct.unpack.uint32_le(stream)

    ## Packs the values in class into a binary stream.
    ## @param[in] as_group_entry - True if this object contains a GRPICONDIRENTRY structure,
    ##                             False if this object contains a plain ICONDIRENTRY structure.
    def encode(self, stream, as_group_entry: bool = False):
        stream.write(struct.pack.uint8(self.width))
        stream.write(struct.pack.uint8(self.height))
        stream.write(struct.pack.uint16_le(self.total_palette_colors))
        stream.write(struct.pack.uint16_le(self.color_planes))
        stream.write(struct.pack.uint16_le(self.bits_per_pixel))
        stream.write(struct.pack.uint32_le(self.icon_size_in_bytes))
        if as_group_entry:
            stream.write(struct.pack.uint16_le(self.icon_resource_id))
        else:
            stream.write(struct.pack.uint32_le(self.bitmap_start_offset))

## Reads an RT_ICON resource.
class Icon:
    def __init__(self, stream, resource_declaration, resource_library):
        self.resource_id = resource_declaration.id
        resource_start = stream.tell()
        self.bitmap_header = BitmapInfoHeader(stream)
        stream.seek(resource_start)
        self.data = stream.read(resource_declaration.resource_length_in_bytes)

    ## Exports this resource as a BMP file.
    ## @param[in] filepath - The filepath of the file to export.
    ##            A suffix will be added with the resource type and ID
    ##            to make this filepath unique.
    def export(self, filepath):
        with open(filepath + ".ico", 'wb') as icon_file:
            self.write_ico_file(icon_file)

    ## Writes a complete ICO file that has one icon - the icon described by this image.
    def write_ico_file(self, stream):
        self.ico_directory.encode(stream)
        self.ico_directory_entry.encode(stream)
        stream.write(self.data)

    ## Creates an icon directory (ICO file header).
    ## When paired with an icon directory entry and an RT_ICON resource,
    ## a complete ICO file can be written.
    @property
    def ico_directory(self):
        ico_directory = IconDirectory()
        ico_directory.icon_count = 1
        return ico_directory

    ## Returns an icon directory entry for this icon. When paired with an icon directory,
    ## and an RT_ICON resource, a complete ICO file can be written.
    ## Non-grouped icon resources from NE binaries are just like RT_BITMAP resources:
    ##  - These resouces begin with a BITMAPINFOHEADER structure, not a BITMAPFILEINFO header.
    ##  - These resources do NOT begin with ICONDIR or ICONDIRENTRY structures.
    ##    However, they CANNOT simply be exported as bitmaps becuase the ICO transparency must
    ##    still be applied.
    ##
    ## Icon (as opposed to group icon) resources only ever have one icon, so we know everything needed to 
    ## construct a valid ICO file.
    @property
    def ico_directory_entry(self):
        # CREATE THE ICO DIRECTORY ENTRY FROM THE BITMAP HEADER.
        directory_entry = IconDirectoryEntry()
        directory_entry.width = self.bitmap_header.width
        directory_entry.height = self.bitmap_header.height // 2
        directory_entry.total_palette_colors = self.bitmap_header.total_palette_colors
        directory_entry.color_planes = self.bitmap_header.color_planes
        directory_entry.bits_per_pixel = self.bitmap_header.bits_per_pixel
        directory_entry.icon_size_in_bytes = len(self.data)
        # Since there is only one directory entry, we know the size of the icon directory
        # (the sum of the sizes of the previous entries plus this one).
        directory_entry.bitmap_start_offset = IconDirectory.LENGTH_IN_BYTES + IconDirectoryEntry.LENGTH_IN_BYTES
        return directory_entry
