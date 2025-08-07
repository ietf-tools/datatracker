# coding=utf-8

# Try use the C extension, but if it isn't available, provide a dummy
# implementation.

try:
    from scout_apm.core._objtrace import disable, enable, get_counts, reset_counts
except ImportError:  # pragma: no cover

    def enable():
        pass

    def disable():
        pass

    def get_counts():
        return (0, 0, 0, 0)

    def reset_counts():
        pass

    is_extension = False
else:  # pragma: no cover
    is_extension = True
