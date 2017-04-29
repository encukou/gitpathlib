import functools


class reify:
    def __init__(self, wrapped):
        self.wrapped = wrapped
        self.name = self.wrapped.__name__
        functools.update_wrapper(self, wrapped)

    def __get__(self, obj, owner=None):
        if obj is None:
            return self
        val = self.wrapped(obj)
        setattr(obj, self.name, val)
        return val
