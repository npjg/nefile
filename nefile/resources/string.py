
import string

## String tables are constructed in blocks of 16 strings.
## \author Nathanael Gentry
## \date   10/02/2022
class StringBlock:
    def __init__(self, stream, resource_library):
        self.strings = []
        # 16 strings are always written, even if not all slots are full.
        # Any slots in the block with no string have a zero WORD for the length.
        TOTAL_STRINGS_IN_THIS_BLOCK: int = 16
        for index in range(TOTAL_STRINGS_IN_THIS_BLOCK):
            # READ THE STRING LENGTH.
            string_length = stream.uint16_le()

            # READ THE STRING ENTRY.
            string_slot_filled = string_length > 0
            if string_slot_filled:
                # TODO: Read based on Unicode for Win32.
                string = stream.read(string_length).decode(resource_library.text_encoding)
            else:
                # The lowest four bits of a string's ID determine 
                # the string's position in the block. Thus, to preserve
                # the order of the strings in this block so reference 
                # by ID still works, we will append a None.
                string = None
            self.strings.append(string)
