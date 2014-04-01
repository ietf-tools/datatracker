class DajaxiceError(Exception):
    pass


class FunctionNotCallableError(DajaxiceError):
    pass


class DajaxiceImportError(DajaxiceError):
    pass
