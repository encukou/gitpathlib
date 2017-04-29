from gitpathlib.gp_base import BaseGitPath, GitPathError, ReadOnlyError
from gitpathlib.gp_base import ObjectNotFoundError, NotATreeError
from gitpathlib.gp_base import NotABlobError


class GitPath(BaseGitPath):
    __doc__ = BaseGitPath.__doc__


__all__ = [
    'GitPath', 'GitPathError', 'ReadOnlyError', 'ObjectNotFoundError',
    'NotATreeError', 'NotABlobError'
]
