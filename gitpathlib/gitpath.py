import functools
import pathlib

import pygit2


class reify:
    def __init__(self, wrapped):
        self.wrapped = wrapped
        self.name = self.wrapped.__name__
        functools.update_wrapper(self, wrapped)

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, obj, owner=None):
        if obj is None:
            return self
        val = self.wrapped(obj)
        setattr(obj, self.name, val)
        return val


@functools.total_ordering
class GitPath:
    """
    A `pathlib`_-style *path flavor* that allows reading from Git repositories.

    ``GitPath`` objects can be created from a *repository path*. This opens the
    given repository:

    >>> from gitpathlib import GitPath
    >>> GitPath('path/to/repo')
    gitpathlib.GitPath('.../path/to/repo/', '31b40fb...')

    A commit ID or a branch (or reference) name can be given as *rev* to open
    a particular commit (or *tree-ish*).

    >>> GitPath('path/to/repo', 'HEAD^')
    gitpathlib.GitPath('.../path/to/repo/', '66c3381...')

    Additional path segments will select a given file.

    >>> GitPath('path/to/repo', 'HEAD', 'dir/file')
    gitpathlib.GitPath('.../path/to/repo/', '31b40fb...', 'dir', 'file')

    """
    def __new__(cls, repository_path, rev='HEAD', *segments):
        repo = pygit2.Repository(repository_path)
        base = repo.revparse_single(rev).peel(pygit2.Tree)

        self = super(cls, GitPath).__new__(cls)
        self._gp_repo = repo
        self._gp_base = base
        self.parent = self
        self.name = ''
        if segments:
            return self.joinpath(*segments)
        else:
            return self

    def _gp_make_child(self, name):
        child = super(type(self), GitPath).__new__(type(self))
        child._gp_repo = self._gp_repo
        child._gp_base = self._gp_base
        child.parent = self
        child.name = name
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
    def hex(self):
        return self._gp_obj.hex

    @reify
    def parts(self):
        """A tuple giving access to the path’s various components

        >>> p = GitPath('path/to/repo', 'HEAD', 'dir', 'file')
        >>> p.parts
        ('.../path/to/repo/.git/:31b40fb...', 'dir', 'file')

        (Note that the first part combines the repository location
        and Git object ID of the path's root.
        """
        if self.parent is self:
            return '{}:{}'.format(self._gp_repo.path, self._gp_base.hex),
        else:
            return (*self.parent.parts, self.name)

    @reify
    def drive(self):
        """A string representing the repository location.

        Note that this is not the same as the repository's working directory.

        >>> p = GitPath('path/to/repo', 'HEAD', 'dir', 'file')
        >>> p.drive
        '/.../path/to/repo/.git/'
        """
        return self._gp_repo.path

    @reify
    def root(self):
        """A hex ID of the path's root.

        >>> p = GitPath('path/to/repo', 'HEAD', 'dir', 'file')
        >>> p.root
        '31b40fbbe41b1bc46cb85acb1ccb89a3ab182e98'
        """
        return self._gp_base.hex

    @reify
    def parents(self):
        if self is self.parent:
            return ()
        else:
            return (self.parent, *self.parent.parents)

    @reify
    def _gp_root(self):
        if self is self.parent:
            return self
        else:
            return self.parent._gp_root

    def __hash__(self):
        return hash((GitPath, eq_key(self)))

    def __eq__(self, other):
        if not isinstance(other, GitPath):
            return NotImplemented
        return eq_key(self) == eq_key(other)

    def __lt__(self, other):
        if not isinstance(other, GitPath):
            return NotImplemented
        return eq_key(self) < eq_key(other)

    def __repr__(self):
        if type(self) == GitPath:
            qualname = 'gitpathlib.GitPath'
        else:
            qualname = '{tp.__module__}.{tp.__qualname__}'.format(tp=type(self))
        args = (repo_path(self._gp_repo), self._gp_base.hex) + self.parts[1:]
        return '{qualname}{args}'.format(
            qualname=qualname,
            args=args,
        )

    def __truediv__(self, other):
        return self.joinpath(other)

    def joinpath(self, *other):
        other = pathlib.PurePosixPath(*other)
        if other.is_absolute():
            result = self._gp_root
            parts = other.parts[1:]
        else:
            result = self
            parts = other.parts
        for name in parts:
            result = result._gp_make_child(name)
        return result


def eq_key(gitpath):
    return (gitpath._gp_base.hex, *gitpath.parts[1:])


def repo_path(repo):
    if repo.is_bare:
        return repo.path
    else:
        return repo.workdir
