class BaseClientError(Exception):
    pass


class ValidationDateError(BaseClientError):
    pass


class ValidationTextError(BaseClientError):
    pass
