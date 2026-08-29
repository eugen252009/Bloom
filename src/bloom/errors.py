class BloomError(Exception):
    """An expected Bloom failure with a stable process exit code."""

    exit_code = 1


class RegistryError(BloomError):
    exit_code = 3


class ArtifactValidationError(BloomError):
    exit_code = 4


class AbiError(BloomError):
    exit_code = 5


class VBufError(BloomError):
    exit_code = 6


class PrimitiveError(BloomError):
    exit_code = 7


class OutputError(BloomError):
    exit_code = 8


class ResourceError(BloomError):
    exit_code = 7
