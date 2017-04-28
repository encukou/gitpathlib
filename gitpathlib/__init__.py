from gitpathlib.gp_base import BaseGitPath, GitPathError, ReadOnlyError
from gitpathlib.gp_base import ObjectNotFoundError, NotATreeError
from gitpathlib.gp_pygit import PygitPath


class GitPath(PygitPath):
    __doc__ = BaseGitPath.__doc__


__all__ = [
    'GitPath', 'GitPathError', 'ReadOnlyError', 'ObjectNotFoundError',
    'NotATreeError'
]
