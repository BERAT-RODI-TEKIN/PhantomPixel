"""Exception hierarchy. Everything the user can fix derives from StegoError."""


class StegoError(Exception):
    """Base class for all expected, user-facing errors."""


class CapacityError(StegoError):
    """The secret does not fit into the cover image."""


class NoDataError(StegoError):
    """The image does not contain PhantomPixel data."""


class PasswordRequiredError(StegoError):
    """The data is password-protected but no password was given."""


class WrongPasswordError(StegoError):
    """Wrong password, or the protected data was damaged."""


class CorruptedDataError(StegoError):
    """Hidden data was found but its integrity check failed."""
