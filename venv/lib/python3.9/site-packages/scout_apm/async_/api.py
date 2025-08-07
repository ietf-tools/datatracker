# coding=utf-8

from functools import wraps


class AsyncDecoratorMixin(object):
    """Provide the ability to decorate both sync and async functions."""

    is_async = False

    @classmethod
    def async_(cls, operation, tags=None, **kwargs):
        """
        Instrument an async function via a decorator.

        This will return an awaitable which must be awaited.
        Using this on a synchronous function will raise a
        RuntimeError.

        ``
           @instrument.async_("Foo")
           async def foo():
              ...
        ``
        """
        instance = cls(operation, tags=tags, **kwargs)
        instance.is_async = True
        return instance

    def __call__(self, func):
        if self.is_async:
            # Until https://bugs.python.org/issue37398 has a resolution,
            # manually wrap the async function
            @wraps(func)
            async def decorated(*args, **kwds):
                with self._recreate_cm():
                    return await func(*args, **kwds)

            return decorated
        else:
            return super().__call__(func)
