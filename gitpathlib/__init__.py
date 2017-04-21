from gitpathlib.gp_base import BaseGitPath
from gitpathlib.gp_pygit import PygitPath


class GitPath(PygitPath):
    __doc__ = BaseGitPath.__doc__


__all__ = ['GitPath']
