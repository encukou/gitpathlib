import os
import functools
import pathlib

import pygit2

from .gp_base import BaseGitPath, NotATreeError, NotABlobError
from .util import reify, backend_cache

GIT_TYPES = {
    pygit2.GIT_OBJ_COMMIT: 'commit',
    pygit2.GIT_OBJ_TREE: 'tree',
    pygit2.GIT_OBJ_BLOB: 'blob',
    pygit2.GIT_OBJ_TAG: 'tag',
}

class PygitBackend:
    def init_root(self, path, repository_path, rev):
        repo = pygit2.Repository(repository_path)
        path._gp_repo = repo
        path._gp_base = repo.revparse_single(rev).peel(pygit2.Tree)


    def init_child(self, parent, child):
        child._gp_repo = parent._gp_repo
        child._gp_base = parent._gp_base
        return child


    @backend_cache('_gp_obj')
    def get_obj(self, path):
        if path is path.parent:
            return path._gp_base
        else:
            return path._gp_repo[self.get_entry(path).id]


    @backend_cache('_gp_entry')
    def get_entry(self, path):
        if path is path.parent:
            return None
        else:
            tree = self.get_obj(path.parent).peel(pygit2.Tree)
            return tree[path.name]

    def hex(self, path):
        return self.get_obj(path).hex


    def exists(self, path):
        if path is path.parent:
            return True
        elif self.exists(path.parent):
            tree = self.get_obj(path.parent).peel(pygit2.Tree)
            return path.name in tree
        else:
            return False

    def listdir(self, path):
        obj = self.get_obj(path)
        if obj.type == pygit2.GIT_OBJ_TREE:
            return tuple(e.name for e in obj)
        raise NotATreeError('Not a tree: {}'.format(self))

    def get_type(self, path):
        obj = self.get_obj(path)
        return GIT_TYPES[self.get_obj(path).type]

    def readlink(self, path):
        if path is path.parent:
            return None
        entry = self.get_entry(path)
        if (entry.type == 'blob' and
                entry.filemode == pygit2.GIT_FILEMODE_LINK):
            return self.read(path).decode('utf-8', errors='surrogateescape')
        return None

    def read(self, path):
        obj = self.get_obj(path)
        if obj.type == pygit2.GIT_OBJ_BLOB:
            return obj.data
        raise NotABlobError('Not a blob: {}'.format(path))

    def lstat(self, path):
        if path is path.parent:
            st_mode = pygit2.GIT_FILEMODE_TREE
        else:
            st_mode = self.get_entry(path).filemode
        obj = self.get_obj(path)
        st_ino = int.from_bytes(obj.id.raw, 'little')
        st_dev = -1
        st_nlink = 1
        st_uid = 0
        st_gid = 0
        print(obj, obj.hex, obj.read_raw())
        if obj.type == pygit2.GIT_OBJ_BLOB:
            st_size = obj.size
        elif obj.type == pygit2.GIT_OBJ_TREE:
            st_size = len(obj)
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
