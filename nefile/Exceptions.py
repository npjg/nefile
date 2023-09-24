
## This is raised when there is any error parsing the MZ or NE header,
## except for the instance when the file is actually PE. 
class NotValidNewExecutableError(ValueError):
    pass

## Raised in the special case where the file is detected as PE, not NE.
class IsPortableExecutableError(ValueError):
    pass
