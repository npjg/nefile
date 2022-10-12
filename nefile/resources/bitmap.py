
import self_documenting_struct as struct
import os

## Reads and writes a Windows BITMAPFILEHEADER.
# TODO: This assumes the resource is a Windows bitmap.
# But this is not in fact guaranteed. Check for the 
# OS/2 signatures too.
class BitmapFileHeader:
    LENGTH_IN_BYTES = 0x0e
    WINDOWS_BITMAP_FILE_HEADER = b'BM'

    def __init__(self, stream = None):
        self.bitmap_length_in_bytes = None
        self.reserved_value1 = 0x0000
        self.reserved_value2 = 0x0000
        self.pixel_data_start_offset = None
        if stream is not None:
            self.decode(stream)

    def decode(self, stream):
        assert stream.read(2) == self.WINDOWS_BITMAP_FILE_HEADER
        self.bitmap_length_in_bytes = struct.unpack.uint32_le(stream)
        self.reserved_value1 = struct.unpack.uint16_le(stream)
        self.reserved_value2 = struct.unpack.uint16_le(stream)
        self.pixel_data_start_offset = struct.unpack.uint32_le(stream)

    def encode(self, stream):
        stream.write(self.WINDOWS_BITMAP_FILE_HEADER)
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

## Reads a complete RT_BITMAP resource.
## \param[in] resource - The resource to be modeled by this class.
## \param[in] resource_table - The full resource table from the executable.
class Bitmap:
    def __init__(self, stream, resource_declaration, resource_library):
        self.resource_id = resource_declaration.id

        # READ THE BITMAP INFO HEADER.
        # Because we want to read the bitmap info header
        # as part of the resource data, the stream must be reset. 
        bitmap_info_header_start = stream.tell()
        self.bitmap_info_header = BitmapInfoHeader(stream)
        stream.seek(bitmap_info_header_start)
        self.data = stream.read(resource_declaration.resource_length_in_bytes)

    ## Exports this resource as a BMP file.
    ## @param[in] filepath - The filepath of the file to export.
    ##            A suffix will be added with the resource type and ID
    ##            to make this filepath unique.
    def export(self, filepath):
        with open(filepath + ".bmp", 'wb') as icon_file:
            self.write_bmp_file(icon_file)

    ## Writes a complete and readable BMP file to the given stream.
    ## @param[in] stream - The stream at the start of the resource data.
    def write_bmp_file(self, stream):
        self.bitmap_file_header.encode(stream)
        stream.write(self.data)

    ## Generates a bitmap file header based on the data contained in this bitmap info header.
    ## A bitmap file header is required to create a readable bitmap written to disk.
    @property
    def bitmap_file_header(self):
        # SET THE PIXEL DATA STARTING OFFSET.
        bitmap_file_header = BitmapFileHeader()
        # Calculate the size of the bitfields.
        # Bitfields are only used with the following compression types.
        BI_BITFIELDS = 0x03        
        BI_ALPHABITFIELDS = 0x06
        if self.bitmap_info_header.compression_method == BI_BITFIELDS:
            bitfield_length = 12
        elif self.bitmap_info_header.compression_method == BI_ALPHABITFIELDS:
            bitfield_length = 16
        else:
            bitfield_length = 0
        # Calculate the palette size.
        use_default_total_palette_count = self.bitmap_info_header.total_palette_colors == 0
        if use_default_total_palette_count:
            total_palette_count = 2 ** self.bitmap_info_header.bits_per_pixel
        else:
            total_palette_count = self.bitmap_info_header.total_palette_colors
        BYTES_PER_PALETTE_ENTRY = 4
        palette_size_in_bytes = total_palette_count * BYTES_PER_PALETTE_ENTRY
        # Calculate the starting offset.
        # Then, we can calculate the starting offset of the bitmap
        # as the sum of all the structures that come before it.
        bitmap_file_header.pixel_data_start_offset = BitmapFileHeader.LENGTH_IN_BYTES + self.bitmap_info_header.header_length + bitfield_length + palette_size_in_bytes

        # SET THE TOTAL BITMAP SIZE.
        # This is the size of the entire file, including all headers.
        bitmap_file_header.bitmap_length_in_bytes = BitmapFileHeader.LENGTH_IN_BYTES + len(self.data)
        return bitmap_file_header
