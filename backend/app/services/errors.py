"""Errors independent of HTTP transport."""


class NotFoundError(Exception):
    pass


class ConflictError(Exception):
    pass


class InvalidRunError(Exception):
    pass


class ResumeDeleteError(Exception):
    pass
