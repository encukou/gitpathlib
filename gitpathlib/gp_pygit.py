import functools
import pathlib

import pygit2

from .gp_base import NotATreeError, NotABlobError

GIT_TYPES = {
    pygit2.GIT_OBJ_COMMIT: 'commit',
    pygit2.GIT_OBJ_TREE: 'tree',
    pygit2.GIT_OBJ_BLOB: 'blob',
    pygit2.GIT_OBJ_TAG: 'tag',
}

class PygitBackend:
    """GitPath backend based on the ``pygit2`` library
    """

    def init_root(self, path, repository_path, rev):
        repo = pygit2.Repository(repository_path)
        path._gp_repo = repo
        path._gp_base = repo.revparse_single(rev).peel(pygit2.Tree)

    def init_child(self, parent, child):
        child._gp_repo = parent._gp_repo
        child._gp_base = parent._gp_base
        return child

    def hex(self, path):
        return get_obj(path).hex

    def has_entry(self, path, name):
        tree = get_obj(path).peel(pygit2.Tree)
        return name in tree

    def listdir(self, path):
        obj = get_obj(path)
        return tuple(e.name for e in obj)

    def get_type(self, path):
        obj = get_obj(path)
        return GIT_TYPES[get_obj(path).type]

    def read(self, path):
        obj = get_obj(path)
        return obj.data

    def get_blob_size(self, path):
        obj = get_obj(path)
        return obj.size

    def get_mode(self, path):
        if path is path.parent:
            return pygit2.GIT_FILEMODE_TREE
        else:
            return get_entry(path).filemode


def get_obj(path):
    try:
        return path._gp_obj
    except AttributeError:
        if path is path.parent:
            obj = path._gp_base
        else:
            obj = path._gp_repo[get_entry(path).id]
    path._gp_obj = obj
    return obj


def get_entry(path):
    if path is path.parent:
        return None
    else:
        tree = get_obj(path.parent).peel(pygit2.Tree)
        return tree[path.name]
