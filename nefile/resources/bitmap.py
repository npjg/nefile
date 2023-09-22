
import self_documenting_struct as struct
import os

## Writes a Windows BITMAPFILEHEADER.
class BitmapFileHeader:
    LENGTH_IN_BYTES = 0x0e
    WINDOWS_BITMAP_FILE_SIGNATURE = b'BM'

    def __init__(self, stream = None):
        self.bitmap_length_in_bytes = None
        self.reserved_value1 = 0x0000
        self.reserved_value2 = 0x0000
        self.pixel_data_start_offset = None
        if stream is not None:
            self.decode(stream)

    def encode(self, stream):
        stream.write(self.WINDOWS_BITMAP_FILE_SIGNATURE)
        stream.write(struct.pack.uint32_le(self.bitmap_length_in_bytes))
        stream.write(struct.pack.uint16_le(self.reserved_value1))
        stream.write(struct.pack.uint16_le(self.reserved_value2))
        stream.write(struct.pack.uint32_le(self.pixel_data_start_offset))

## Reads the BITMAPINFOHEADER structure (the most common DIB header).
# TODO: This assumes the resource is a Windows bitmap.
# But this is not in fact guaranteed. Check for the 
# OS/2 signatures too.
class BitmapInfoHeader:
    def __init__(self, stream):
        self.header_length = struct.unpack.uint32_le(stream)
        if (self.header_length != 0x28):
            # This doesn't necessarily mean the resource is invalid or there is a bug,
            # just that the bitmap probably uses a BitmapCoreHeader.
            raise ValueError("BitmapInfoHeader doesn't have expected length.")
        self.width = struct.unpack.int32_le(stream)
        self.height = struct.unpack.int32_le(stream)
        self.color_planes = struct.unpack.uint16_le(stream)
        self.bits_per_pixel = struct.unpack.uint16_le(stream)
        self.compression_method = struct.unpack.uint32_le(stream)
        self.image_size = struct.unpack.uint32_le(stream)
        self.horizontal_resolution = struct.unpack.int32_le(stream)
        self.vertical_resolution = struct.unpack.int32_le(stream)
        self.total_palette_colors = struct.unpack.uint32_le(stream)
        self.total_important_colors = struct.unpack.uint32_le(stream)

## Reads the BITMAPCOREHEADER structure (a DIB header that is sometimes used).
## The BITMAPCOREHEADER is part of BITMAPCOREINFO, which also contains
## palette information.
## "Windows applications should use the BITMAPINFO structure instead 
## of BITMAPCOREINFO whenever possible.""
class BitmapCoreHeader:
    def __init__(self, stream):
        self.header_length = struct.unpack.uint32_le(stream)
        if self.header_length != 0x0c:
            # If the BitmapInfoHeader has already been tried, 
            # this probably is a corrupted file or bug.
            raise ValueError("BitmapCoreHeader doesn't have expected length.")
        self.width = struct.unpack.int16_le(stream)
        self.height = struct.unpack.int16_le(stream)
        self.color_planes = struct.unpack.uint16_le(stream)
        self.bits_per_pixel = struct.unpack.uint16_le(stream)

## Reads a complete RT_BITMAP resource.
## \param[in] resource_declaration - The resource to be modeled by this class.
## \param[in] resource_library - The full resource table from the executable.
class Bitmap:
    def __init__(self, stream, resource_declaration, resource_library):
        self.resource_id = resource_declaration.id

        # READ THE BITMAP INFO HEADER.
        bitmap_info_header_start_pointer = stream.tell()
        try:
            # BITMAPINFOHEADERS are used most often, so try that first.
            self.bitmap_header = BitmapInfoHeader(stream)
            self.has_bitmap_core_header = False
        except:
            # BITMAPCOREHEADERs have been seen in the wild, so 
            # try again with that.
            stream.seek(bitmap_info_header_start_pointer)
            self.bitmap_header = BitmapCoreHeader(stream)
            self.has_bitmap_core_header = True

        # READ THE BITMAP DATA.
        # Because we want to read the bitmap info header
        # as part of the resource data, the stream must be reset. 
        stream.seek(bitmap_info_header_start_pointer)
        self.data = stream.read(resource_declaration.resource_length_in_bytes)

    ## Exports this resource as a BMP file to the filesystem
    ## \param[in] filepath - The filepath of the file to export.
    ##  A BMP extension will be added if it isn't already present.
    def export(self, filepath):
        BMP_FILENAME_EXTENSION = '.bmp'
        filename_extension_present = (filepath[:-4].lower() == BMP_FILENAME_EXTENSION)
        if not filename_extension_present:
            filepath += BMP_FILENAME_EXTENSION
        with open(filepath, 'wb') as icon_file:
            self.save_as_bmp(icon_file)
        if self.bitmap_header.header_length == 0x0c:
            print(filepath)
            print()

    ## Writes a complete and viewable BMP file to the given binary stream.
    def save_as_bmp(self, stream):
        self.bitmap_file_header.encode(stream)
        stream.write(self.data)

    ## Generates a bitmap file header for this resource.
    ## This bitmap file header is required to create a 
    ## readable bitmap on disk.
    @property
    def bitmap_file_header(self):
        # SET THE PIXEL DATA STARTING OFFSET.
        bitmap_file_header = BitmapFileHeader()
        # Calculate the size of the bitfields.
        # Bitfields are only used with the following compression types.
        BI_BITFIELDS = 0x03        
        BI_ALPHABITFIELDS = 0x06
        if not self.has_bitmap_core_header:
            if self.bitmap_header.compression_method == BI_BITFIELDS:
                bitfield_length = 12
            elif self.bitmap_header.compression_method == BI_ALPHABITFIELDS:
                bitfield_length = 16
            else:
                bitfield_length = 0

        else:
            # BITMAPCOREHEADER bitmaps don't seem to use compression,
            # so there are no bitfields.
            bitfield_length = 0

        # Calculate the palette size.
        if not self.has_bitmap_core_header:
            use_default_total_palette_count = (self.bitmap_header.total_palette_colors == 0)
            if use_default_total_palette_count:
                total_palette_count = 2 ** self.bitmap_header.bits_per_pixel
            else:
                total_palette_count = self.bitmap_header.total_palette_colors

        else:
             total_palette_count = 2 ** self.bitmap_header.bits_per_pixel
        BYTES_PER_PALETTE_ENTRY = 4
        palette_size_in_bytes = total_palette_count * BYTES_PER_PALETTE_ENTRY
        # Calculate the starting offset.
        # Then, we can calculate the starting offset of the bitmap
        # as the sum of all the structures that come before it.
        bitmap_file_header.pixel_data_start_offset = BitmapFileHeader.LENGTH_IN_BYTES + \
            self.bitmap_header.header_length + bitfield_length + palette_size_in_bytes

        # SET THE TOTAL BITMAP SIZE.
        # This is the size of the entire file, including all headers.
        bitmap_file_header.bitmap_length_in_bytes = BitmapFileHeader.LENGTH_IN_BYTES + len(self.data)
        return bitmap_file_header
