import os
import functools
import pathlib

import pygit2

from .gp_base import BaseGitPath
from .util import reify, inherit_docstring

GIT_TYPES = {
    pygit2.GIT_OBJ_COMMIT: 'commit',
    pygit2.GIT_OBJ_TREE: 'tree',
    pygit2.GIT_OBJ_BLOB: 'blob',
    pygit2.GIT_OBJ_TAG: 'tag',
}

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
            return self._gp_repo[self._gp_entry.id]


    @reify
    def _gp_entry(self):
        if self is self.parent:
            return None
        else:
            tree = self.parent._gp_obj.peel(pygit2.Tree)
            return tree[self.name]


    @reify
    def _gp_exists(self):
        if self is self.parent:
            return True
        elif self.parent._gp_exists:
            tree = self.parent._gp_obj.peel(pygit2.Tree)
            return self.name in tree
        else:
            return False


    @reify
    def _gp_read_link(self):
        obj = self._gp_obj
        if (obj.type == pygit2.GIT_OBJ_BLOB and
                self._gp_entry.filemode == pygit2.GIT_FILEMODE_LINK):
            return obj.data.decode('utf-8', errors='surrogateescape')
        return None

    @reify
    @inherit_docstring(BaseGitPath)
    def hex(self):
        self = self.resolve(strict=True)
        return self._gp_obj.hex


    @inherit_docstring(BaseGitPath)
    def stat(self):
        self = self.resolve(strict=True)
        git_type = GIT_TYPES[self._gp_obj.type]
        if self is self.parent:
            st_mode = pygit2.GIT_FILEMODE_TREE
        else:
            st_mode = self._gp_entry.filemode
        st_ino = int.from_bytes(self._gp_obj.id.raw, 'little')
        st_dev = -1
        st_nlink = 1
        st_uid = 0
        st_gid = 0
        if git_type == 'blob':
            st_size = self._gp_obj.size
        elif git_type == 'tree':
            st_size = len(self._gp_obj)
        else:
            st_size = 0
        st_atime = 0
        st_mtime = 0
        st_ctime = 0
        return os.stat_result([
            st_mode,
            st_ino,
            st_dev,
            st_nlink,
            st_uid,
            st_gid,
            st_size,
            st_atime,
            st_mtime,
            st_ctime,
        ])
