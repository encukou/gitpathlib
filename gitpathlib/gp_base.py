import functools
import pathlib
import fnmatch
import io

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
    def __new__(cls, repository_path, rev='HEAD', *segments):
        self = super(BaseGitPath, cls).__new__(cls)
        self.drive = str(pathlib.Path(repository_path).resolve())
        self._gp_init(repository_path, rev)
        self.parent = self
        self.name = ''
        if segments:
            return self.joinpath(*segments)
        else:
            return self

    def _gp_make_child(self, name):
        child = super(BaseGitPath, type(self)).__new__(type(self))
        child.parent = self
        child.drive = self.drive
        child.name = name
        return child

    @property
    def hex(self):
        raise NotImplementedError(
            'GitPathBase.hex must be overridden in a subclass')

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
        return self._gp_root.hex

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

    @reify
    def _gp_pureposixpath(self):
        return pathlib.PurePosixPath('/', *self.parts[1:])

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
            result = result._gp_make_child(name)
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
        if isinstance(other, BaseGitPath):
            if self.root != other.root:
                raise ValueError('Paths have different roots')
            ppp = other._gp_pureposixpath
        else:
            ppp = pathlib.PurePosixPath('/').joinpath(other)
        return self._gp_pureposixpath.relative_to(ppp)

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
        resolved = resolve(self, True, set())
        if not resolved._gp_exists:
            raise ObjectNotFoundError(self)
        return resolved._gp_lstat()

    def lstat(self):
        """Like :meth:`stat()` but, if the path points to a symbolic link,
        return the symbolic link’s information rather than its target’s.
        """
        parent, sibling, link, exists = _preresolve(self, set())
        if not exists:
            raise ObjectNotFoundError(self)
        return sibling._gp_lstat()

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
        return resolve(self, strict, set())

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
            resolved = self.resolve(strict=True)
        except ObjectNotFoundError:
            return False
        return resolved._gp_exists

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
        for element in self.resolve(strict=True)._gp_dir_contents:
            yield self._gp_make_child(element)

    def is_dir(self):
        """Whether the path points to a tree (directory)

        Return ``True`` if the path points to a tree (or a symbolic link
        pointing to a tree), ``False`` if it points to another kind
        of object.

        ``False`` is also returned if the path doesn’t exist or is a broken
        link; other errors are propagated.
        """
        try:
            resolved = self.resolve(strict=True)
        except ObjectNotFoundError:
            return False
        return resolved._gp_type == 'tree'

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
        return resolved._gp_type == 'blob'

    def is_symlink(self):
        """Whether the path points to a symbolic link

        ``False`` is also returned if the path doesn’t exist; other errors
        are propagated.
        """
        parent, sibling, link, exists = _preresolve(self, set())
        return link is not None

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
        pattern = pathlib.PurePosixPath(pattern)
        if pattern.is_absolute():
            raise NotImplementedError('Non-relative patterns are unsupported')
        if not pattern.parts:
            raise ValueError('Empty pattern')
        return glob(self, *pattern.parts, seen=set())

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
        return self.resolve(strict=True)._gp_read()

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


def _preresolve(self, seen):
    """Return a 4-tuple useful for resolve() and readlink-like operations

    Arguments:
        self: The path in question.
        seen: Set of unresolved sylinks seen so far, used for detecting symlink
              loops. Pass an empty set() when calling this function externally.

    The return value is:
    - Resolved parent path
    - "Sibling" -- resolved path (usually a child of the resolved parent)
    - Symlink target as a string, or None
    - Whether the path ("sibling") exists
    """
    if self is self.parent:
        return self, self, None, True

    parent = resolve(self.parent, False, seen)
    if self.name == '..':
        return parent, parent.parent, None, parent._gp_exists
    if parent is self.parent:
        sibling = self
    else:
        sibling = parent._gp_make_child(self.name)
    if not parent._gp_exists or not sibling._gp_exists:
        return parent, sibling, None, False
    return parent, sibling, sibling._gp_read_link, True


def resolve(self, strict, seen):
    try:
        if strict:
            return self._gp_resolved_strict
        else:
            return self._gp_resolved_nonstrict
    except AttributeError:
        pass

    def _resolve():
        parent, sibling, link, exists = _preresolve(self, seen)

        if not exists:
            if strict:
                raise ObjectNotFoundError(str(sibling))
            else:
                return sibling

        if link is not None:
            if self in seen:
                raise RuntimeError("Symlink loop from '{}'".format(self))
            seen.add(self)
            result = resolve(parent.joinpath(link), strict, seen)
            seen.discard(self)
            return result
        return sibling

    result = _resolve()
    if strict:
        self._gp_resolved_strict = result
    else:
        self._gp_resolved_nonstrict = result
    return result


def glob(self, part=None, *more_parts, seen):
    if part is None:
        yield self
        return
    try:
        resolved = self.resolve(strict=False)
    except RuntimeError:
        return
    if not resolved.exists():
        return
    if resolved in seen:
        return
    if self.is_dir():
        if part == '**':
            yield from glob(self, *more_parts, seen=set())
            for child in self.iterdir():
                yield from glob(child, '**', *more_parts, seen=seen | {resolved})
        elif part == '..':
            yield from glob(self._gp_make_child('..'), *more_parts, seen=set())
        else:
            for child in self.iterdir():
                if fnmatch.fnmatchcase(child.name, part):
                    yield from glob(child, *more_parts, seen=set())


def eq_key(gitpath):
    return (gitpath.root, *gitpath.parts[1:])


def good_part_name(name):
    if '/' in name or '\0' in name or not name:
        return False
    else:
        return True
