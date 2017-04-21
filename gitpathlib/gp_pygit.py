import functools
import pathlib

import pygit2

from .gp_base import BaseGitPath
from .util import reify, inherit_docstring


@functools.total_ordering
class PygitPath(BaseGitPath):
    def _gp_init(self, repository_path, rev):
        repo = pygit2.Repository(repository_path)
        self._gp_repo = repo
        self._gp_base = repo.revparse_single(rev).peel(pygit2.Tree)


    def _gp_make_child(self, name):
        child = super()._gp_make_child(name)
        child._gp_repo = self._gp_repo
        child._gp_base = self._gp_base
        return child


    @reify
    def _gp_obj(self):
        if self is self.parent:
            return self._gp_base
        else:
            tree = self.parent._gp_obj.peel(pygit2.Tree)
            entry = tree[self.name]
            return self._gp_repo[entry.id]


    @reify
    @inherit_docstring(BaseGitPath)
    def hex(self):
        return self._gp_obj.hex
