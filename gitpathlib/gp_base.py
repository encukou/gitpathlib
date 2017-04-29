import collections
import functools
import binascii
import pathlib
import fnmatch
import io
import os

from .util import reify


class GitPathError(Exception):
    """Invalid operation on a Git path

    Base for all gitpathlib exceptions.
    """

class ReadOnlyError(GitPathError, PermissionError):
    """Attempt to modify an immutable Git tree"""


class ObjectNotFoundError(GitPathError, FileNotFoundError):
    """Git object not found"""


class NotATreeError(GitPathError, NotADirectoryError):
    """Git object is not a tree"""


class NotABlobError(GitPathError, IsADirectoryError):
    """Git object is not a blob"""


def _raise_readonly(self, *args, **kwargs):
    """Raises ReadOnlyError."""
    raise ReadOnlyError('Cannot modify a GitPath')


def _return_false(self, *args, **kwargs):
    """Returns False."""
    return False


def get_default_backend():
    from .gp_pygit import PygitBackend
    return PygitBackend()


GIT_MODE_LINK = 0o120000


@functools.total_ordering
class BaseGitPath:
    """
    A `pathlib`_-style *path flavor* that allows reading from Git repositories.

    ``GitPath`` objects can be created from a *repository path*. This opens the
    given repository:

    >>> from gitpathlib import GitPath
    >>> GitPath('path/to/repo')
    gitpathlib.GitPath('.../path/to/repo', '31b40fb...')

    A commit ID or a branch (or reference) name can be given as *rev* to open
    a particular commit (or *tree-ish*).
    A large subset of the *extended SHA-1 syntax* accepted by
    `git rev-parse <https://git-scm.com/docs/git-rev-parse#_specifying_revisions>`_
    is accepted for *rev*.

    >>> GitPath('path/to/repo', 'HEAD^')
    gitpathlib.GitPath('.../path/to/repo', '66c3381...')

    Additional path segments will select a given file.

    >>> GitPath('path/to/repo', 'HEAD', 'dir/file')
    gitpathlib.GitPath('.../path/to/repo', '31b40fb...', 'dir', 'file')

    """
    def __init__(self, repository_path, rev='HEAD', *segments, backend=None):
        segments = pathlib.PurePosixPath(*segments).parts
        if segments[:1] == ('/', ):
            segments = segments[1:]
        repository_path = os.path.realpath(repository_path)
        if segments:
            parent = type(self)(repository_path=repository_path, rev=rev,
                                backend=backend)
            for segment in segments[:-1]:
                parent = make_child(parent, segment)
            init_child(parent, self, segments[-1])
        else:
            self._gp_backend = backend = backend or get_default_backend()
            self.drive = str(pathlib.Path(repository_path).resolve())
            self.parent = self
            self.name = ''
            backend.init_root(self, repository_path, rev)

    @reify
    def parts(self):
        """A tuple giving access to the path’s various components

        >>> p = GitPath('path/to/repo', 'HEAD', 'dir', 'file')
        >>> p.parts
        ('.../path/to/repo:31b40fb...', 'dir', 'file')

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
        '/.../path/to/repo'
        """
        raise NotImplementedError('GitPathBase.drive should be set in __new__')

    @reify
    def root(self):
        """A hex ID of the path's root.

        >>> p = GitPath('path/to/repo', 'HEAD', 'dir', 'file')
        >>> p.root
        '31b40fbbe41b1bc46cb85acb1ccb89a3ab182e98'
        """
        return hex_oid(self._gp_root)

    @reify
    def anchor(self):
        """The concatenation of drive and root.

        >>> p = GitPath('path/to/repo', 'HEAD', 'dir', 'file')
        >>> p.anchor
        '/.../path/to/repo:31b40fb...'
        """
        return '{}:{}'.format(self.drive, self.root)

    @reify
    def parents(self):
        """An immutable sequence containing the logical ancestors of the path.

        >>> p = GitPath('path/to/repo', 'HEAD', 'dir', 'subdir', 'file')
        >>> p.parents[0]
        gitpathlib.GitPath('.../repo', '31b40fb...', 'dir', 'subdir')
        >>> p.parents[1]
        gitpathlib.GitPath('.../repo', '31b40fb...', 'dir')
        >>> p.parents[2]
        gitpathlib.GitPath('.../repo', '31b40fb...')
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
        gitpathlib.GitPath('.../repo', '31b40fb...', 'src', 'include', 'eggs.h')

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
        gitpathlib.GitPath('.../repo', '31b40fb...', 'src', 'spam.c')

        >>> p = GitPath('path/to/repo', 'HEAD', 'README')
        >>> p.with_suffix('.txt')
        gitpathlib.GitPath('.../repo', '31b40fb...', 'README.txt')
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

    def __hash__(self):
        return hash((BaseGitPath, eq_key(self)))

    def __eq__(self, other):
        if not isinstance(other, BaseGitPath):
            return NotImplemented
        return eq_key(self) == eq_key(other)

    def __lt__(self, other):
        if not isinstance(other, BaseGitPath):
            return NotImplemented
        return eq_key(self) < eq_key(other)

    def __repr__(self):
        qualname = '{tp.__module__}.{tp.__qualname__}'.format(tp=type(self))
        args = (self.drive, self.root) + self.parts[1:]
        return '{qualname}{args}'.format(
            qualname=qualname,
            args=args,
        )

    def __truediv__(self, other):
        return self.joinpath(other)

    def joinpath(self, *other):
        """Combines the path with each of the other arguments in turn.

        >>> GitPath('./repo').joinpath('README')
        gitpathlib.GitPath('.../repo', '31b40fb...', 'README')
        >>> GitPath('./repo').joinpath(pathlib.PurePosixPath('README'))
        gitpathlib.GitPath('.../repo', '31b40fb...', 'README')
        >>> GitPath('./repo').joinpath('tests', 'runtests.sh')
        gitpathlib.GitPath('.../repo', '31b40fb...', 'tests', 'runtests.sh')

        If an argument in *other* is an absolute path, it resets the path
        to the GitPath's root (mimicking :func:`os.path.join()`‘s behaviour).

        >>> GitPath('./repo').joinpath('tests', '/README')
        gitpathlib.GitPath('.../repo', '31b40fb...', 'README')
        """
        other = pathlib.PurePosixPath(*other)
        if other.is_absolute():
            result = self._gp_root
            parts = other.parts[1:]
        else:
            result = self
            parts = other.parts
        for name in parts:
            result = make_child(result, name)
        return result

    as_posix = NotImplemented
    cwd = pathlib.Path.cwd
    home = pathlib.Path.home

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
        return to_pure_posix_path(self).match(pattern)

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
        if isinstance(other, BaseGitPath):
            if self.root != other.root:
                raise ValueError('Paths have different roots')
            ppp = to_pure_posix_path(other)
        else:
            ppp = pathlib.PurePosixPath('/').joinpath(other)
        return to_pure_posix_path(self).relative_to(ppp)

    def stat(self):
        """Return information about this path (similarly to os.stat()).

        Not all members of the returned structure convey useful information.
        Here is a summary:

        : st_mode: Type and mode of the file
        : st_ino: The hash of the object, as an integer
        : st_dev: -1
        : st_nlink: 1
        : st_uid: 0
        : st_gid: 0
        : st_size:
            Size of a blob (file) in bytes,
            or number of entries in a tree (directory)

        : st_atime: 0
        : st_mtime: 0
        : st_ctime: 0

        Note in particular that timestamps are always zero.
        """
        path = resolve(self, False)
        return path.lstat()

    def lstat(self):
        """Like :meth:`stat()` but, if the path points to a symbolic link,
        return the symbolic link’s information rather than its target’s.
        """
        info = get_info(self)
        if not info.exists:
            raise ObjectNotFoundError(self)
        path = info.canonical
        backend = path._gp_backend
        oid_hex = backend.hex(path)
        inode = int.from_bytes(binascii.unhexlify(oid_hex), 'little')
        if backend.get_type(self) == 'blob':
            st_size = backend.get_blob_size(path)
        else:
            st_size = len(backend.listdir(path))
        return os.stat_result([
            backend.get_mode(path),  # st_mode
            inode,  # st_ino
            -1,  # st_dev
            1,  # st_nlink
            0,  # st_uid
            0,  # st_gid
            st_size,  # st_size
            0,  # st_atime
            0,  # st_mtime
            0,  # st_ctime
        ])

    chmod = _raise_readonly
    lchmod = _raise_readonly
    mkdir = _raise_readonly
    rename = _raise_readonly
    replace = _raise_readonly
    rmdir = _raise_readonly
    symlink_to = _raise_readonly
    touch = _raise_readonly
    unlink = _raise_readonly
    write_bytes = _raise_readonly
    write_text = _raise_readonly

    def resolve(self, strict=False):
        """Make this path absolute, resolving any symlinks.

        A new path object is returned:

        >>> p = GitPath('./slrepo', 'HEAD', 'symlink-to-dir/file')
        >>> p.resolve()
        gitpathlib.GitPath('.../slrepo', '88823a5...', 'dir', 'file')

        “``..``” components are also eliminated (this is the only method to
        do so):

        >>> p = GitPath('./repo', 'HEAD', 'dir/..')
        >>> p.resolve()
        gitpathlib.GitPath('.../repo', '31b40fb...')

        If the path doesn’t exist and strict is ``True``,
        :class:`FileNotFoundError` is raised.
        If *strict* is ``False``, the path is resolved as far as possible
        and any remainder is appended without checking whether it exists.
        If an infinite loop is encountered along the resolution path,
        :class:`RuntimeError` is raised.
        """
        return resolve(self, strict)

    def exists(self):
        """Whether the path points to an existing file or directory:

        >>> GitPath('repo', 'HEAD').exists()
        True
        >>> GitPath('repo', 'HEAD', 'dir/file').exists()
        True
        >>> GitPath('repo', 'HEAD', 'nonexistent-file').exists()
        False

        .. note::

            If the path points to a symlink, ``exists()`` returns whether
            the symlink *points to* an existing file or directory.
        """
        try:
            path = resolve(self, True)
        except ObjectNotFoundError:
            return False
        return get_info(path).exists

    def expanduser(self):
        """Return this path unchanged.

        Git paths are always absolute; they cannot begin with ``~``.
        """
        return self

    def iterdir(self):
        """Yield path objects of the directory contents:

        >>> p = GitPath('project', 'HEAD')
        >>> for child in p.iterdir():
        ...     print(child)
        ...
        gitpathlib.GitPath('.../project', 'f7707d4...', '.gitignore')
        gitpathlib.GitPath('.../project', 'f7707d4...', 'LICENSE')
        gitpathlib.GitPath('.../project', 'f7707d4...', 'README')
        gitpathlib.GitPath('.../project', 'f7707d4...', 'project')
        gitpathlib.GitPath('.../project', 'f7707d4...', 'setup.py')
        """
        backend = self._gp_backend
        path = self.resolve(strict=True)
        if backend.get_type(path) not in ('tree', 'commit', 'tag'):
            raise NotATreeError(self)
        for name in backend.listdir(path):
            yield make_child(self, name)

    def is_dir(self):
        """Whether the path points to a tree (directory)

        Return ``True`` if the path points to a tree (or a symbolic link
        pointing to a tree), ``False`` if it points to another kind
        of object.

        ``False`` is also returned if the path doesn’t exist or is a broken
        link; other errors are propagated.
        """
        exists, resolved = _resolve(self, seen=set())
        if not exists:
            return False
        backend = self._gp_backend
        return backend.get_type(resolved) == 'tree'

    def is_file(self):
        """Whether the path points to a blob (file)

        Return ``True`` if the path points to a blob (or a symbolic link
        pointing to a blob), ``False`` if it points to another kind
        of object.

        ``False`` is also returned if the path doesn’t exist or is a broken
        link; other errors are propagated.
        """
        try:
            resolved = self.resolve(strict=True)
        except ObjectNotFoundError:
            return False
        backend = self._gp_backend
        return backend.get_type(resolved) == 'blob'

    def is_symlink(self):
        """Whether the path points to a symbolic link

        ``False`` is also returned if the path doesn’t exist; other errors
        are propagated.
        """
        info = get_info(self)
        return info.link_target is not None

    is_socket = _return_false
    is_fifo = _return_false
    is_block_device = _return_false
    is_char_device = _return_false

    def glob(self, pattern):
        """Glob the given pattern, yielding all matching files (of any kind).

        Glob the given pattern in the directory represented by this path.

        >>> for p in GitPath('project', 'HEAD').glob('*.py'):
        ...     print(p)
        ...
        gitpathlib.GitPath('.../project', 'f7707d4...', 'setup.py')

        >>> for p in GitPath('project', 'HEAD').glob('*/*.py'):
        ...     print(p)
        ...
        gitpathlib.GitPath('.../project', 'f7707d4...', 'project', '__init__.py')
        gitpathlib.GitPath('.../project', 'f7707d4...', 'project', 'util.py')

        The “``**``” pattern means “this directory and all subdirectories,
        recursively”. In other words, it enables recursive globbing:

        >>> for p in GitPath('project', 'HEAD').glob('**/*.py'):
        ...     print(p)
        ...
        gitpathlib.GitPath('.../project', 'f7707d4...', 'setup.py')
        gitpathlib.GitPath('.../project', 'f7707d4...', 'project', '__init__.py')
        gitpathlib.GitPath('.../project', 'f7707d4...', 'project', 'util.py')
        gitpathlib.GitPath('.../project', 'f7707d4...', 'project', 'tests', 'test_bar.py')
        gitpathlib.GitPath('.../project', 'f7707d4...', 'project', 'tests', 'test_foo.py')

        .. note::

            Using the “``**``” pattern in large directory trees may consume
            an inordinate amount of time.
        """
        return glob(self, pattern)

    def rglob(self, pattern):
        """This is like glob() with “**” added in front of the given pattern

        >>> for p in GitPath('project', 'HEAD').rglob('*.py'):
        ...     print(p)
        ...
        gitpathlib.GitPath('.../project', 'f7707d4...', 'setup.py')
        gitpathlib.GitPath('.../project', 'f7707d4...', 'project', '__init__.py')
        gitpathlib.GitPath('.../project', 'f7707d4...', 'project', 'util.py')
        gitpathlib.GitPath('.../project', 'f7707d4...', 'project', 'tests', 'test_bar.py')
        gitpathlib.GitPath('.../project', 'f7707d4...', 'project', 'tests', 'test_foo.py')
        """
        return glob(self, pattern, rglob=True)

    def group(self):
        """Raises :exc:`KeyError`, since Git objects aren't owned by groups."""
        raise KeyError('Git objects not owned by a group')

    def owner(self):
        """Raises :exc:`KeyError`, since Git objects aren't owned by users."""
        raise KeyError('Git objects not owned by a user')

    def read_bytes(self):
        """Return the binary contents of the pointed-to file as a bytes object:

        >>> p = GitPath('./project') / 'README'
        >>> p.read_bytes()
        b'bla bla'
        """
        backend = self._gp_backend
        resolved = self.resolve(strict=True)
        if backend.get_type(resolved) != 'blob':
            raise NotABlobError(self)
        return backend.read(resolved)

    def read_text(self, encoding='utf-8', errors='strict'):
        """Return the decoded contents of the pointed-to file as a string:

        >>> p = GitPath('./project') / 'README'
        >>> p.read_text()
        'bla bla'

        The optional parameters have the same meaning as in :func:`open()`,
        but they default to ``utf-8`` and ``strict``, respectively.
        """
        if encoding is None:
            encoding = 'utf-8'
        if errors is None:
            errors = 'strict'
        return self.read_bytes().decode(encoding=encoding, errors=errors)

    def open(self, mode='r', buffering=-1, encoding=None, errors=None,
             newline=None):
        """Open the file pointed to by the path.

        This behaves similarly to the built-in :func:`open` function:

        >>> p = GitPath('project', 'HEAD', 'README')
        >>> with p.open() as f:
        ...     f.readline()
        ...
        'bla bla'

        *mode* can only be a subset of modes supported by :func:`open`.
        Git objects are immutable, so they cannot be opened for writing.
        The available modes are ``'rt'`` and ``'rb'``:

        ========= ====================================
        Character Meaning
        ========= ====================================
        ``'r'``   open for reading
        ``'b'``   binary mode
        ``'t'``   text mode (default)
        ========= ====================================

        *buffering* is currently ignored; the whole file is buffered.

        *encoding* and *errors* default to ``'utf8'`` and ``'strict'``,
        respectively.

        """
        if not isinstance(mode, str):
            raise TypeError("invalid mode: %r" % mode)
        modes = set(mode)
        if modes - set("rbt") or len(mode) > len(modes):
            if set('wx') & modes:
                raise ValueError('cannot open Git blob for writing')
            if set('a+') & modes:
                raise ValueError('cannot open Git blob for appending')
            raise ValueError("invalid mode: %r" % mode)
        if 'r' not in modes:
            raise ValueError("unknown mode: %r" % mode)
        text = "t" in modes
        binary = "b" in modes
        if text and binary:
            raise ValueError("can't have text and binary mode at once")
        if encoding is None:
            encoding = 'utf-8'
        elif binary:
            raise ValueError("binary mode doesn't take an encoding argument")
        if errors is None:
            errors = 'strict'
        elif binary:
            raise ValueError("binary mode doesn't take an errors argument")
        if binary and newline is not None:
            raise ValueError("binary mode doesn't take a newline argument")

        result = io.BytesIO(self.read_bytes())
        #result = BufferedReader(result, buffering)
        if binary:
            return result

        result = io.TextIOWrapper(result, encoding, errors, newline, False)
        result.mode = mode
        return result

    def samefile(self, other_path):
        """Return whether this path points to the same file as other_path

        If the other path is not a GiPath, return False.

        Since Git trees are immutable, this compares the object identities
        (hashes).
        This means that files (or even trees) with the same contents are
        considered the same – even across different repositories.

        >>> f1 = GitPath('dupes', 'HEAD', 'file1')
        >>> f1.read_text()
        'same content'
        >>> f2 = GitPath('dupes', 'HEAD', 'file2')
        >>> f2.read_text()
        'same content'
        >>> f3 = GitPath('dupes', 'HEAD', 'different_file')
        >>> f3.read_text()
        'different content'

        >>> f1.samefile(f1)
        True
        >>> f1.samefile(f2)
        True
        >>> f1.samefile(f3)
        False
        """
        if not isinstance(other_path, BaseGitPath):
            return False
        path1 = resolve(self, strict=True)
        path2 = resolve(other_path, strict=True)
        return hex_oid(path1) == hex_oid(path2)


def make_child(path, name):
    child = path.__new__(type(path))
    init_child(path, child, name)
    return child

def init_child(parent, child, name):
    child._gp_backend = backend = parent._gp_backend
    child.parent = parent
    child.drive = parent.drive
    child.name = name
    backend.init_child(parent, child)


def to_pure_posix_path(path):
    return pathlib.PurePosixPath('/', *path.parts[1:])


def resolve(path, strict):
    exists, resolved = _resolve(path, set())
    if strict and not exists:
        raise ObjectNotFoundError(path)
    return resolved

def _resolve(path, seen):
    try:
        return path._gp_resolved
    except AttributeError:
        pass

    info = get_info(path)
    exists = info.exists
    canonical_path = info.canonical
    if info.link_target:
        if canonical_path in seen:
            raise RuntimeError("Symlink loop from '{}'".format(path))
        seen.add(canonical_path)
        target = canonical_path.parent.joinpath(info.link_target)
        other_exists, result = _resolve(target, seen)
        if not other_exists:
            exists = False
    else:
        result = canonical_path

    path._gp_resolved = exists, result
    return exists, result


PathInfo = collections.namedtuple(
    'PathInfo',
    ['exists', 'canonical', 'link_target'])


def get_info(path):
    try:
        return path._gp_info
    except AttributeError:
        result = _get_info(path)
        path._gp_info = result
        return result


def _get_info(path):
    if path.parent is path:
        return PathInfo(True, path, None)

    parent = path.parent
    parent_info = get_info(parent)
    is_canonical = parent_info.canonical is parent
    backend = path._gp_backend
    if not is_canonical:
        parent = resolve(parent_info.canonical, False)
        parent_info = get_info(parent)
    if parent_info.link_target:
        is_canonical = False
        parent = resolve(parent, False)
        parent_info = get_info(parent)
    if parent is path.parent:
        sibling = path
    else:
        sibling = make_child(parent, path.name)
    if path.name == '..':
        return PathInfo(parent_info.exists, parent.parent, None)
    if not parent_info.exists or not backend.has_entry(parent, path.name):
        return PathInfo(False, sibling, None)
    if backend.get_mode(sibling) == GIT_MODE_LINK:
        link_target = backend.read(sibling).decode('utf-8', 'surrogateescape')
    else:
        link_target = None
    return PathInfo(True, sibling, link_target)


def glob(path, pattern, rglob=False):
    pattern = pathlib.PurePosixPath(pattern)
    if pattern.is_absolute():
        raise NotImplementedError('Non-relative patterns are unsupported')
    if rglob:
        parts = ('**', ) + pattern.parts
    elif not pattern.parts:
        raise ValueError('Empty pattern')
    else:
        parts = pattern.parts
    return _glob(path, *parts, seen=set())


def _glob(path, part=None, *more_parts, seen):
    if part is None:
        yield path
        return
    try:
        resolved = path.resolve(strict=False)
    except RuntimeError:
        return
    if not resolved.exists():
        return
    if resolved in seen:
        return
    if path.is_dir():
        if part == '**':
            yield from _glob(path, *more_parts, seen=set())
            for child in path.iterdir():
                yield from _glob(child, '**', *more_parts,
                                 seen=seen | {resolved})
        elif part == '..':
            yield from _glob(make_child(path, '..'), *more_parts, seen=set())
        else:
            for child in path.iterdir():
                if fnmatch.fnmatchcase(child.name, part):
                    yield from _glob(child, *more_parts, seen=set())


def eq_key(gitpath):
    return (gitpath.root, *gitpath.parts[1:])


def good_part_name(name):
    if '/' in name or '\0' in name or not name:
        return False
    else:
        return True


def hex_oid(path):
    """Return the object ID of the object a the path refers to.

    The object ID (hash) is returned as a hexadecimal string.
    """
    info = get_info(path)
    if not info.exists:
        raise ObjectNotFoundError(path)
    return path._gp_backend.hex(info.canonical)
