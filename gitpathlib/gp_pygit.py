import functools
import pathlib

import pygit2

from .gp_base import BaseGitPath, NotATreeError, NotABlobError

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
        """Initialize backend-specific information for a root path

        The *repository_path* and *rev* arguments are the same as for
        :class:`GitPath`.
        """

        repo = pygit2.Repository(repository_path)
        path._gp_repo = repo
        path._gp_base = repo.revparse_single(rev).peel(pygit2.Tree)

    def init_child(self, parent, child):
        """Initialize backend-specific information for a child path

        The *parent* is the parent path; *child* is the path to initialize.
        When this is called, the child's name is already stored in its
        ``name`` attribute.
        """

        child._gp_repo = parent._gp_repo
        child._gp_base = parent._gp_base
        return child

    def hex(self, path):
        """Return the hexadecimal Object ID corresponding to this path.
        """

        return get_obj(path).hex

    def has_entry(self, path, name):
        """Return True if *path* is a tree that has an entry named *name*.
        """

        tree = get_obj(path).peel(pygit2.Tree)
        return name in tree

    def listdir(self, path):
        """Return a tuple of the contents of tree, as strings.

        If the path does not identify a tree, raise :exc:`NotATreeError`.
        """

        obj = get_obj(path)
        if obj.type == pygit2.GIT_OBJ_TREE:
            return tuple(e.name for e in obj)
        raise NotATreeError('Not a tree: {}'.format(self))

    def get_type(self, path):
        """Return the type of the object identified by this path.

        Possible return values are ``'commit'``, ``'tree'``, ``'blob'``, and
        ``'tag'``.
        """

        obj = get_obj(path)
        return GIT_TYPES[get_obj(path).type]

    def read(self, path):
        """Return the contents of a blob, as a bytestring.

        If the path does not identify a blob, raise :exc:`NotABlobError`.
        """

        obj = get_obj(path)
        if obj.type == pygit2.GIT_OBJ_BLOB:
            return obj.data
        raise NotABlobError('Not a blob: {}'.format(path))

    def get_size(self, path):
        """Return the length of a blob or number of entries in a tree.
        """

        obj = get_obj(path)
        if obj.type == pygit2.GIT_OBJ_BLOB:
            return obj.size
        elif obj.type == pygit2.GIT_OBJ_TREE:
            return len(obj)
        else:
            return 0

    def get_mode(self, path):
        """Return the file mode of a blob.
        """

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
