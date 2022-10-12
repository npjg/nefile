
from PIL import Image

## Models an RT_GROUP_CURSOR resource as a collection of PIL images,
## one for each cursor in the group. The RT_GROUP_CURSOR resource itself 
## only holds the cursor directory for the cursors in the group, so we
## must look up the cursors elsewhere in this resource library.
##
## \param[in] resource - The resource to be modeled by this class
## \param[in] resource_table - The full resource table from the executable
## \author Nathanael Gentry
## \date   09/28/2022
class GroupCursor:
    def __init__(self, stream, resource_library):
        # READ THE FILE SIGNATURE.
        ICO_FILE_SIGNATURE = b'\x00\x00\x01\x00'
        assert stream.read(1) == ICO_FILE_SIGNATURE
        cursor_count = stream.uint16_le()

        self.cursors = []
        for index in range(cursor_count):
            # GET THE REFERENCED CURSOR.
            cursor_directory_entry = GroupCursorDirectoryEntry(stream)
            referenced_cursor = resource_library.find_resource_by_id(cursor_directory_entry.cursor_resource_id)
            self.cursors.append(referenced_cursor)

        ## Need to find the other cursor resources that correspond to this one.
        pass

    @property
    def default_format_string(self):
        pass

## Models the GRPCURSORDIRENTRY structure.
## The GRPCURSORDIRENTRY structure is the same as the usual CURSORDIRENTRY structure,
## except the entry at offset 0x0B specifies the resource ID of the referenced cursor,
## rather than the offset to the cursor in the file.
## The GRPCURSORDIR structure is the same as the usual CURSORDIR structure.
## (Source: https://devblogs.microsoft.com/oldnewthing/20120720-00/?p=7083)
class GroupCursorDirectoryEntry:
    def __init__(self, stream):
        self.width = stream.uint8()
        self.height = stream.uint8()
        # Should be 0 if the image does not use a color palette.
        self.total_palette_colors = stream.uint8()
        # Should always be 0.
        self.reserved = stream.uint8()
        self.color_planes = stream.uint16_le()
        self.bits_per_pixel = stream.uint16_le()
        self.cursor_size_in_bytes = stream.uint32_le()
        self.cursor_resource_id = stream.uint32_le()
        
## Models an RT_CURSOR resource as a PIL image.
## Both PE and NE binaries can have cursors.
## \param[in] resource - The resource to be modeled by this class
## \param[in] resource_table - The full resource table from the executable
## \author Nathanael Gentry
## \date   09/28/2022
class Cursor:
    def __init__(self, stream, resource_library = None):
        # Non-grouped cursor resources from NE binaries are just like RT_BITMAP resources:
        #  - These resouces begin with a BITMAPINFOHEADER structure, not a BITMAPFILEINFO header.
        #  - These resources do NOT begin with CURSORDIR or CURSORDIRENTRY structures.
        #    They are not acually in ICO format, but merely cursor resources.
        #
        # These resources only ever have one cursor, so we are not actually missing any information. 
        self.image = Image(stream)
