from .css import merge_css_classes
from .text import text_value

SIZE_SM = "sm"
SIZE_MD = "md"
SIZE_LG = "lg"
SIZES = [SIZE_SM, SIZE_MD, SIZE_LG]
DEFAULT_SIZE = SIZE_MD


def parse_size(value, default=None):
    """Return size if it is valid, default size if size is empty, or throws exception."""
    size = text_value(value or default)
    if size not in SIZES:
        valid_sizes = ", ".join(SIZES)
        raise ValueError(f'Invalid value "{size}" for parameter "size" (valid values are {valid_sizes}).')
    return size


def get_size_class(size, prefix, *, default=None, skip=None):
    """Return CSS class for size with given prefix, unless size needs to be skipped."""
    size = parse_size(size, default=default)
    if skip:
        if isinstance(skip, str):
            skip = merge_css_classes(skip).split(" ")
        if size in skip:
            return ""
    return f"{prefix}-{size}"
