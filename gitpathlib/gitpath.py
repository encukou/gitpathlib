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
    A large subset of the *extended SHA-1 syntax* accepted by
    `git rev-parse <https://git-scm.com/docs/git-rev-parse#_specifying_revisions>`_
    is accepted for *rev*.

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
            return (self.anchor, )
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
    def anchor(self):
        """The concatenation of drive and root.

        >>> p = GitPath('path/to/repo', 'HEAD', 'dir', 'file')
        >>> p.anchor
        '/.../path/to/repo/.git/:31b40fb...'
        """
        return '{}:{}'.format(self._gp_repo.path, self._gp_base.hex)

    @reify
    def parents(self):
        """An immutable sequence containing the logical ancestors of the path.

        >>> p = GitPath('path/to/repo', 'HEAD', 'dir', 'subdir', 'file')
        >>> p.parents[0]
        gitpathlib.GitPath('.../repo/', '31b40fb...', 'dir', 'subdir')
        >>> p.parents[1]
        gitpathlib.GitPath('.../repo/', '31b40fb...', 'dir')
        >>> p.parents[2]
        gitpathlib.GitPath('.../repo/', '31b40fb...')
        """
        if self is self.parent:
            return ()
        else:
            return (self.parent, *self.parent.parents)

    @property
    def suffix(self):
        """The file extension of the final component, if any.

        >>> GitPath('path/to/repo', 'HEAD', 'README.md').suffix
        '.md'
        >>> GitPath('path/to/repo', 'HEAD', 'archive.tar.gz').suffix
        '.gz'
        >>> GitPath('path/to/repo', 'HEAD').suffix
        ''
        """
        stem, dot, suffix = self.name.rpartition('.')
        if dot:
            return dot + suffix
        else:
            return ''

    @property
    def suffixes(self):
        """A list of the path’s file extensions.

        >>> GitPath('path/to/repo', 'HEAD', 'archive.tar.gz').suffixes
        ['.tar', '.gz']
        >>> GitPath('path/to/repo', 'HEAD', 'archive.tar').suffixes
        ['.tar']
        >>> GitPath('path/to/repo', 'HEAD', 'archive').suffixes
        []
        """
        parts = self.name.split('.')
        return ['.' + p for p in parts[1:]]

    @property
    def stem(self):
        """The final path component, without its suffix.

        >>> GitPath('path/to/repo', 'HEAD', 'archive.tar.gz').stem
        'archive.tar'
        >>> GitPath('path/to/repo', 'HEAD', 'archive.tar').stem
        'archive'
        >>> GitPath('path/to/repo', 'HEAD', 'archive').stem
        'archive'
        """
        stem, dot, suffix = self.name.rpartition('.')
        if dot:
            return stem
        else:
            return self.name

    def with_name(self, new_name):
        """Return a new path with the :attr:`name` changed.

        >>> p = GitPath('path/to/repo', 'HEAD', 'src/include/spam.h')
        >>> p.with_name('eggs.h')
        gitpathlib.GitPath('.../repo/', '31b40fb...', 'src', 'include', 'eggs.h')

        If the original path doesn’t have a name, ValueError is raised.
        """
        if self is self.parent:
            raise ValueError('{} has an empty name'.format(self))
        if not good_part_name(new_name):
            raise ValueError('Invalid name {!r}'.format(new_name))
        return self.parent / new_name

    def with_suffix(self, new_suffix):
        """Return a new path with the :attr:`suffix` changed.

        If the original path doesn’t have a suffix, the new suffix is
        appended instead.

        >>> p = GitPath('path/to/repo', 'HEAD', 'src/spam.h')
        >>> p.with_suffix('.c')
        gitpathlib.GitPath('.../repo/', '31b40fb...', 'src', 'spam.c')

        >>> p = GitPath('path/to/repo', 'HEAD', 'README')
        >>> p.with_suffix('.txt')
        gitpathlib.GitPath('.../repo/', '31b40fb...', 'README.txt')
        """
        if self is self.parent:
            raise ValueError('{} has an empty name'.format(self))
        if not new_suffix.startswith('.') or not good_part_name(new_suffix[1:]):
            raise ValueError('Invalid suffix {!r}'.format(new_suffix))
        return self.parent / (self.stem + new_suffix)

    @reify
    def _gp_root(self):
        if self is self.parent:
            return self
        else:
            return self.parent._gp_root

    @reify
    def _gp_pureposixpath(self):
        return pathlib.PurePosixPath('/', *self.parts[1:])

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
        """Combines the path with each of the other arguments in turn.

        >>> GitPath('./repo').joinpath('README')
        gitpathlib.GitPath('.../repo/', '31b40fb...', 'README')
        >>> GitPath('./repo').joinpath(pathlib.PurePosixPath('README'))
        gitpathlib.GitPath('.../repo/', '31b40fb...', 'README')
        >>> GitPath('./repo').joinpath('tests', 'runtests.sh')
        gitpathlib.GitPath('.../repo/', '31b40fb...', 'tests', 'runtests.sh')

        If an argument in *other* is an absolute path, it resets the path
        to the GitPath's root (mimicking :func:`os.path.join()`‘s behaviour).

        >>> GitPath('./repo').joinpath('tests', '/README')
        gitpathlib.GitPath('.../repo/', '31b40fb...', 'README')
        """
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

    as_posix = NotImplemented

    def as_uri(self):
        """Raises ValueError.

        Git paths cannot be converted to ``file:`` URIs.
        """
        raise ValueError('GitPath cannot be meaningfully converted to an URI')

    def is_absolute(self):
        """Returns ``True``.

        For relative paths within a repository,
        use :class:`pathlib.PurePosixPath`.

        There is no “current directory” for Git paths.
        """
        return True

    def is_reserved(self):
        """Returns ``False``.

        While using paths that are reserved on Windows will make a Git
        repository unusable on that system, Git itself does not reserve any
        paths.
        """
        return False

    def match(self, pattern):
        """Match this path against the provided glob-style pattern.

        Return True if matching is successful, False otherwise.

        :ref:`the-root` is never taken into consideration when matching.

        If pattern is relative, matching is done from the right:

        >>> GitPath('./repo', 'HEAD', 'a/b.py').match('*.py')
        True
        >>> GitPath('./repo', 'HEAD', 'a/b/c.py').match('b/*.py')
        True
        >>> GitPath('./repo', 'HEAD', 'a/b/c.py').match('a/*.py')
        False

        If pattern is absolute, the whole path must match:

        >>> GitPath('./repo', 'HEAD', 'a.py').match('/*.py')
        True
        >>> GitPath('./repo', 'HEAD', 'a/b.py').match('/*.py')
        False

        The matching is purely lexical. In particular, it does not distinguish
        between files and directories:

        >>> GitPath('./repo', 'HEAD', 'README').match('/README/')
        True
        """
        return self._gp_pureposixpath.match(pattern)

    def relative_to(self, other):
        """Return a version of this path relative to the other path.

        If it’s impossible, ValueError is raised:

        >>> p = GitPath('./repo', 'HEAD', 'a/b.py')
        >>> p.relative_to('/')
        PurePosixPath('a/b.py')
        >>> p.relative_to('/a')
        PurePosixPath('b.py')
        >>> p.relative_to('/README')
        Traceback (most recent call last):
        ...
        ValueError: '/a/b.py' does not start with '/README'
        """
        if isinstance(other, GitPath):
            if self._gp_base.hex != other._gp_base.hex:
                raise ValueError('Paths have different roots')
            ppp = other._gp_pureposixpath
        else:
            ppp = pathlib.PurePosixPath('/').joinpath(other)
        return self._gp_pureposixpath.relative_to(ppp)


def eq_key(gitpath):
    return (gitpath._gp_base.hex, *gitpath.parts[1:])


def repo_path(repo):
    if repo.is_bare:
        return repo.path
    else:
        return repo.workdir

def good_part_name(name):
    if '/' in name or '\0' in name or not name:
        return False
    else:
        return True
