
import self_documenting_struct as struct

from .bitmap import Bitmap

## Models an RT_GROUP_CURSOR resource.
## \param[in] resource_declaration - The resource to be modeled by this class.
## \param[in] resource_table - The full resource table from the executable.
class GroupCursor:
    def __init__(self, stream, resource_declaration, resource_table):
        self.resource_id = resource_declaration.id

        # FIND THE CURSORS THAT ARE IN THIS GROUP.
        # In the executable, the RT_GROUP_CURSOR resource itself 
        # only holds the cursor directory for the cursors in the group, so
        # we must look up the cursors elsewhere in this resource library.
        self.cursors = {}
        self.cursor_directory = CursorDirectory(stream)
        for directory_entry in self.cursor_directory.directory_entries:
            # GET THE REFERENCED CURSOR.
            from nefile.resource_table import ResourceType
            referenced_cursor = resource_table.find_resource_by_id(directory_entry.cursor_resource_id, type_id = ResourceType.RT_CURSOR)
            referenced_cursor.is_in_group = True
            self.cursors.update({directory_entry.cursor_resource_id: referenced_cursor})

    ## Exports all cursors in this resource into a single CUR file on the filesystem.
    ## CUR files can contain multiple cursors, so no information is lost.
    ## \param[in] export_filepath - The filepath of the file to export.
    ##  An CUR extension will be added if it isn't already present.
    def export(self, export_filepath):
        CUR_FILENAME_EXTENSION = '.cur'
        filename_extension_present = (export_filepath[:-4].lower() == CUR_FILENAME_EXTENSION)
        if not filename_extension_present:
            export_filepath += CUR_FILENAME_EXTENSION

        # CALCULATE THE IMAGE OFFSETS.
        cursor_image_start_pointers = []
        current_offset = self.cursor_directory.length_in_bytes
        for cursor in self.cursors.values():
            cursor_image_start_pointers.append(current_offset)
            current_offset += len(cursor.data)

        with open(export_filepath, 'wb') as cursor_file:
            # WRITE THE CURSOR DIRECTORY.
            self.cursor_directory.encode(cursor_file)
            for directory_entry, image_start_pointer, cursor in zip(self.cursor_directory.directory_entries, cursor_image_start_pointers, self.cursors.values()):
                directory_entry.encode(cursor_file, image_start_pointer, cursor.x_hotspot, cursor.y_hotspot)
            
            # WRITE THE CURSOR IMAGES.
            for cursor in self.cursors.values():
                cursor_file.write(cursor.data)

## Models the CURSORDIR structure.
class CursorDirectory:
    # This is the length of the structure assuming 
    # zero cursor directory entries.
    MINIMUM_LENGTH_IN_BYTES = 0x06

    def __init__(self, stream):
        self.signature = struct.unpack.uint16_le(stream)
        if self.signature != 0x0000:
            raise ValueError('Cursor directory signature is not valid.')
        self.type = struct.unpack.uint16_le(stream)

        # READ THE CURSOR DIRECTORY ENTRIES.
        # Yes, a list comprehension could be used here. But I find this
        # easier for debugging individual reads.
        self.directory_entries = []
        self.cursor_count = struct.unpack.uint16_le(stream)
        for _ in range(self.cursor_count):
            directory_entry = CursorDirectoryEntry(stream)
            self.directory_entries.append(directory_entry)

    def encode(self, stream):
        stream.write(struct.pack.uint16_le(self.signature))
        stream.write(struct.pack.uint16_le(self.type))
        stream.write(struct.pack.uint16_le(self.cursor_count))

    @property
    def length_in_bytes(self):
        directory_entries_length = self.cursor_count * CursorDirectoryEntry.LENGTH_IN_BYTES
        return self.MINIMUM_LENGTH_IN_BYTES + directory_entries_length

## Models the CURSORDIRENTRY structure.
class CursorDirectoryEntry:
    # Only for written out.
    LENGTH_IN_BYTES = 0x10

    def __init__(self, stream):
        self.width = struct.unpack.uint16_le(stream)
        # This does not seem to be documented anywhere in the spec,
        # but the true height of the cursor seems to be half what
        # is reported in this field. (For instance, if the cursor
        # is 32x32, the reported dimensions would be 32x64.)
        # I am not sure, but this is probably due to the presence
        # of the mask image. 
        # 
        # To get the generated CUR files to read
        # correctly with modern software, we will divide the reported
        # cursor height in half.
        self._raw_height = struct.unpack.uint16_le(stream)
        self.height = self._raw_height // 2
        # Should be 0 if the image does not use a color palette.
        self.color_planes = struct.unpack.uint16_le(stream)
        self.bits_per_pixel = struct.unpack.uint16_le(stream)
        self.cursor_size_in_bytes = struct.unpack.uint32_le(stream)
        self.cursor_resource_id = struct.unpack.uint16_le(stream)

    ## Packs the values in class into a binary stream.
    ## \param[in] image_start_offset - The start pointer to the image
    ##  represented by this directory entry in the file. For cursor
    ##  files written, this takes the place of the resource ID.
    def encode(self, stream, image_start_offset, x_hotspot, y_hotspot):
        stream.write(struct.pack.uint8(self.width))
        stream.write(struct.pack.uint8(self.height))
        stream.write(struct.pack.uint8(0))
        stream.write(struct.pack.uint8(0))
        stream.write(struct.pack.uint16_le(x_hotspot))
        stream.write(struct.pack.uint16_le(y_hotspot))
        stream.write(struct.pack.uint32_le(self.cursor_size_in_bytes))
        stream.write(struct.pack.uint32_le(image_start_offset))

## Models an RT_CURSOR resource.
## This cursor cannot be directly exported. It must be exported as part
## of a RT_GROUP_CURSOR resource.
## \param[in] resource_declaration - The resource to be modeled by this class.
## \param[in] resource_library - The full resource table from the executable.
class Cursor(Bitmap):
    def __init__(self, stream, resource_declaration, resource_library):
        self.is_in_group = False
        self.x_hotspot = struct.unpack.uint16_le(stream)
        self.y_hotspot = struct.unpack.uint16_le(stream)
        super().__init__(stream, resource_declaration, resource_library)

    def export(self, filepath):
        if self.is_in_group:
            # This cursor will be exported as part of the group.
            return
        
        ## The reason for this limitation is that
        ## exporting an cursor on its own would require creating an cursor directory
        ## from scratch, which is doable but a bit beyond the scope of this library.
        ## Cursors that don't belong to a group have not been observed in the wild as yet. 
        raise ValueError(f'Cannot export cursor {self.resource_id} since it is not part of a group.')
        