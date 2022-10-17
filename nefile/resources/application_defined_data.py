
from io import BytesIO

## Models an RT_RCDATA resource. Because the data is application defined,
## the data is merely read; no further parsing can be provided. However,
## this class can be subclassed to further parse the data.
class ApplicationDefinedData:
    def __init__(self, stream, resource_declaration, resource_library):
        # Because a client application will probably want to parse this data,
        # the data is wrapped in a BytesIO stream for easy reading via the 
        # stream interface later on.
        self.data = BytesIO(stream.read(resource_declaration.resource_length_in_bytes))

    def export(self, filepath):
        with open(filepath, 'wb') as data_file:
            data_file.write(self.data.getbuffer())
