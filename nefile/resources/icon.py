
import self_documenting_struct as struct

from .bitmap import Bitmap

## Models an RT_GROUP_ICON resource.
## \param[in] resource_declaration - The resource to be modeled by this class.
## \param[in] resource_table - The full resource table from the executable.
class GroupIcon:
    def __init__(self, stream, resource_declaration, resource_table):
        self.resource_id = resource_declaration.id

        # FIND THE ICONS THAT ARE IN THIS GROUP.
        # In the executable, the RT_GROUP_ICON resource itself 
        # only holds the icon directory for the icons in the group, so
        # we must look up the icons elsewhere in this resource library.
        self.icons = {}
        self.icon_directory = IconDirectory(stream)
        for directory_entry in self.icon_directory.directory_entries:
            # GET THE REFERENCED ICON.
            from nefile.resource_table import ResourceType
            referenced_icon = resource_table.find_resource_by_id(directory_entry.icon_resource_id, type_id = ResourceType.RT_ICON)
            referenced_icon.is_in_group = True
            self.icons.update({directory_entry.icon_resource_id: referenced_icon})

    ## Exports all icons in this resource into a single ICO file on the filesystem.
    ## ICO files can contain multiple icons, so no information is lost.
    ## \param[in] export_filepath - The filepath of the file to export.
    ##  An ICO extension will be added if it isn't already present.
    def export(self, export_filepath):
        ICO_FILENAME_EXTENSION = '.ico'
        filename_extension_present = (export_filepath[:-4].lower() == ICO_FILENAME_EXTENSION)
        if not filename_extension_present:
            export_filepath += ICO_FILENAME_EXTENSION

        # CALCULATE THE IMAGE OFFSETS.
        icon_image_start_pointers = []
        current_offset = self.icon_directory.length_in_bytes
        for icon in self.icons.values():
            icon_image_start_pointers.append(current_offset)
            current_offset += len(icon.data)

        with open(export_filepath, 'wb') as icon_file:
            # WRITE THE ICON DIRECTORY.
            self.icon_directory.encode(icon_file)
            for directory_entry, image_start_pointer in zip(self.icon_directory.directory_entries, icon_image_start_pointers):
                directory_entry.encode(icon_file, image_start_pointer)
            
            # WRITE THE ICON IMAGES.
            for icon in self.icons.values():
                icon_file.write(icon.data)

## Models the ICONDIR structure.
class IconDirectory:
    # This is the length of the structure assuming 
    # zero icon directory entries.
    MINIMUM_LENGTH_IN_BYTES = 0x06

    def __init__(self, stream):
        self.signature = struct.unpack.uint16_le(stream)
        if self.signature != 0x0000:
            raise ValueError('Icon directory signature is not valid.')
        self.type = struct.unpack.uint16_le(stream)

        # READ THE ICON DIRECTORY ENTRIES.
        # Yes, a list comprehension could be used here. But I find this
        # easier for debugging individual reads.
        self.directory_entries = []
        self.icon_count = struct.unpack.uint16_le(stream)
        for _ in range(self.icon_count):
            directory_entry = IconDirectoryEntry(stream)
            self.directory_entries.append(directory_entry)

    def encode(self, stream):
        stream.write(struct.pack.uint16_le(self.signature))
        stream.write(struct.pack.uint16_le(self.type))
        stream.write(struct.pack.uint16_le(self.icon_count))

    @property
    def length_in_bytes(self):
        directory_entries_length = self.icon_count * IconDirectoryEntry.LENGTH_IN_BYTES
        return self.MINIMUM_LENGTH_IN_BYTES + directory_entries_length

## Models the ICONDIRENTRY structure.
## (Source: https://devblogs.microsoft.com/oldnewthing/20120720-00/?p=7083)
class IconDirectoryEntry:
    # Only for written out.
    LENGTH_IN_BYTES = 0x10

    def __init__(self, stream):
        self.width = struct.unpack.uint8(stream)
        self.height = struct.unpack.uint8(stream)
        # Should be 0 if the image does not use a color palette.
        self.total_palette_colors = struct.unpack.uint16_le(stream)
        self.color_planes = struct.unpack.uint16_le(stream)
        self.bits_per_pixel = struct.unpack.uint16_le(stream)
        self.icon_size_in_bytes = struct.unpack.uint32_le(stream)
        self.icon_resource_id = struct.unpack.uint16_le(stream)

    ## Packs the values in class into a binary stream.
    ## \param[in] image_start_offset - The start pointer to the image
    ##  represented by this directory entry in the file. For icon
    ##  files written, this takes the place of the resource ID.
    def encode(self, stream, image_start_offset):
        stream.write(struct.pack.uint8(self.width))
        stream.write(struct.pack.uint8(self.height))
        stream.write(struct.pack.uint16_le(self.total_palette_colors))
        stream.write(struct.pack.uint16_le(self.color_planes))
        stream.write(struct.pack.uint16_le(self.bits_per_pixel))
        stream.write(struct.pack.uint32_le(self.icon_size_in_bytes))
        stream.write(struct.pack.uint32_le(image_start_offset))

## Models an RT_ICON resource.
## This icon cannot be directly exported. It must be exported as part
## of a RT_GROUP_ICON resource.
## \param[in] resource_declaration - The resource to be modeled by this class.
## \param[in] resource_library - The full resource table from the executable.
class Icon(Bitmap):
    def __init__(self, stream, resource_declaration, resource_library):
        self.is_in_group = False
        super().__init__(stream, resource_declaration, resource_library)

    def export(self, filepath):
        if self.is_in_group:
            # This icon will be exported as part of the group.
            return
        
        ## The reason for this limitation is that
        ## exporting an icon on its own would require creating an icon directory
        ## from scratch, which is doable but a bit beyond the scope of this library.
        ## Icons that don't belong to a group have not been observed in the wild as yet. 
        raise ValueError(f'Cannot export icon {self.resource_id} since it is not part of a group.')
        