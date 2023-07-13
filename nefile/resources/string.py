
import self_documenting_struct as struct

import json

## String tables are constructed in blocks of 16 strings.
class StringTable:
    def __init__(self, stream, resource_declaration, resource_library):
        self.strings = []
        # 16 strings are always written, even if not all slots are full.
        # Any slots in the block with no string have a zero WORD for the length.
        TOTAL_STRINGS_IN_THIS_BLOCK: int = 16
        for index in range(TOTAL_STRINGS_IN_THIS_BLOCK):
            # READ THE STRING ENTRY.
            string_length = struct.unpack.uint8(stream)
            string_slot_filled = string_length > 0
            if string_slot_filled:
                # TODO: Read other text encodings (how do we know what the encoding of the current file is?).
                string = stream.read(string_length).decode('latin-1')
            else:
                # The lowest four bits of a string's ID determine 
                # the string's position in the block. Thus, to preserve
                # the order of the strings in this block so reference 
                # by ID still works, we will append a None to indicate a
                # non-existent string in this slot.
                string = None
            self.strings.append(string)

    ## Exports this resource as JSON.
    ## Any blank string slots are exported as nulls in the JSON.
    ## \param[in] filepath - The filepath of the file to export.
    ##            A JSON extension will be added if it isn't already present.
    def export(self, export_filepath):
        JSON_FILENAME_EXTENSION = '.json'
        filename_extension_present = (export_filepath[:-4].lower() == JSON_FILENAME_EXTENSION)
        if not filename_extension_present:
            export_filepath += JSON_FILENAME_EXTENSION
        with open(export_filepath, 'w') as strings_file:
            json.dump(self.strings, strings_file, indent = 2)