import shelve  # nosec

__author__ = "danielevertsson"


class ShelfWrapper(object):
    def __init__(self, filename):
        self.filename = filename

    def keys(self):
        db = self._reopen_database()
        return db.keys()

    def __len__(self):
        db = self._reopen_database()
        return db.__len__()

    def has_key(self, key):
        return key in self

    def __contains__(self, key):
        db = self._reopen_database()
        return db.__contains__(key)

    def get(self, key, default=None):
        db = self._reopen_database()
        return db.get(key, default)

    def __getitem__(self, key):
        db = self._reopen_database()
        return db.__getitem__(key)

    def __setitem__(self, key, value):
        db = self._reopen_database()
        db.__setitem__(key, value)

    def __delitem__(self, key):
        db = self._reopen_database()
        db.__delitem__(key)

    def _reopen_database(self):
        return shelve.open(self.filename, writeback=True)  # nosec


def open(filename):
    """
    Open a persistent dictionary for reading and writing.

    The filename parameter is the base filename for the underlying
    database.  As a side-effect, an extension may be added to the
    filename and more than one file may be created.  The optional flag
    parameter has the same interpretation as the flag parameter of
    anydbm.open(). The optional protocol parameter specifies the
    version of the pickle protocol (0, 1, or 2).

    See the module's __doc__ string for an overview of the interface.
    """
    return ShelfWrapper(filename)
