from gitpathlib.gp_base import BaseGitPath, hex_oid
from gitpathlib.gp_base import GitPathError, ReadOnlyError, NotABlobError
from gitpathlib.gp_base import ObjectNotFoundError, NotATreeError
from gitpathlib.gp_pygit import PygitBackend
from gitpathlib.gp_subprocess import SubprocessBackend


class GitPath(BaseGitPath):
    __doc__ = BaseGitPath.__doc__


__all__ = [
    'GitPath', 'GitPathError', 'ReadOnlyError', 'ObjectNotFoundError',
    'NotATreeError', 'NotABlobError', 'PygitBackend', 'SubprocessBackend',
    'hex_oid',
]
