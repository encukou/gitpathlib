import subprocess
import collections
import functools
import re

from .gp_base import NotATreeError, NotABlobError, get_info

TREE_ENTRY_RE = re.compile(r'^(\d+) (\w+) (\w+)\t(.+)$')
GIT_MODE_TREE = 0o40000


def add_assertions(*assertions):
    """Add assertions to an accessor method

    The SubprocessBackend ooptionally verifies that gitpathlib guarantees
    regarding backend accessor methods are met.

    We can't just do the assertions when functions are called, because
    that would cause infinite loops. Instead, we collect them in the
    ``_assertions`` attribute on the backend, and let the test suite
    run them after each test.

    Collection is only done if the ``_assertions`` attribute exists (and is
    a dict). The test suite creates the attribute automatically.
    """
    def _decorator(func):
        @functools.wraps(func)
        def wrapped(self, path, *args, **kwargs):
            if hasattr(self, '_assertions'):
                for assertion in assertions:
                    self._assertions.setdefault(assertion, []).append((func, path))
            return func(self, path, *args, **kwargs)
        return wrapped
    return _decorator


def existing(path):
    assert get_info(path).exists


def canonical(path):
    assert get_info(path).canonical is path


def resolved(path):
    assert get_info(path).canonical is path
    assert get_info(path).link_target is None


def only_trees(path):
    assert path._gp_backend.get_type(path) == 'tree'


def only_blobs(path):
    assert path._gp_backend.get_type(path) == 'blob'


class SubprocessBackend:
    """GitPath backend based on calling the ``git`` binary
    """

    def init_root(self, path, repository_path, rev):
        """Initialize backend-specific information for a root path

        The *repository_path* and *rev* arguments are the same as for
        :class:`GitPath`.
        """

        path._gp_base = repository_path
        rev = git_stdout(path, 'rev-parse', rev).strip()
        rev = git_stdout(path, 'rev-parse', rev + '^{tree}').strip()
        path._gp_rev = rev
        assert re.match('^[0-9a-f]{40}$', path._gp_rev)

    def init_child(self, parent, child):
        """Initialize backend-specific information for a child path

        The *parent* is the parent path; *child* is the path to initialize.
        When this is called, the child's name is already stored in its
        ``name`` attribute.
        """

    @add_assertions(existing, canonical)
    def hex(self, path):
        """Return the hexadecimal Object ID corresponding to this path.

        Only called on *existing* *canonical* paths.
        """

        try:
            return path._gp_rev
        except AttributeError:
            parent_hex = self.hex(path.parent)
            ref = '{}:{}'.format(parent_hex, path.name)
            rev = git_stdout(path, 'rev-parse', ref).strip()
            path._gp_rev = rev
            return rev

    @add_assertions(existing, resolved, only_trees)
    def has_entry(self, path, name):
        """Return True if *path* is a tree that has an entry named *name*.

        Only called on *existing* *resolved* paths that identify *trees*.
        """

        return name in ls_tree(self, path)

    @add_assertions(existing, resolved, only_trees)
    def listdir(self, path):
        """Return contents of a tree, as tuple of strings.

        Only called on *existing* *resolved* paths that identify *trees*.
        """

        return tuple(ls_tree(self, path))

    @add_assertions(existing, canonical)
    def get_type(self, path):
        """Return the type of the object identified by this path.

        Possible return values are ``'commit'``, ``'tree'``, ``'blob'``, and
        ``'tag'``.

        Only called on *existing* *canonical* paths.
        """

        return git_stdout(path, 'cat-file', '-t', self.hex(path)).strip()

    @add_assertions(existing, canonical, only_blobs)
    def read(self, path):
        """Return the contents of a blob, as a bytestring.

        Only called on *existing* *canonical* paths that identify *blobs*.
        """

        result = call_git(path, 'cat-file', '-p', self.hex(path),
                          stdout=subprocess.PIPE)
        return result.stdout

    @add_assertions(existing, canonical, only_blobs)
    def get_blob_size(self, path):
        """Return the length of a blob or number of entries in a tree.

        Only called on *existing* *canonical* paths that identify *blobs*.
        """

        return int(git_stdout(path, 'cat-file', '-s', self.hex(path)))

    @add_assertions(existing, canonical)
    def get_mode(self, path):
        """Return the file mode of a blob or tree.

        Only called on *existing* *canonical* paths.
        """
        if path is path.parent:
            return GIT_MODE_TREE
        else:
            mode, objtype, sha = ls_tree(self, path.parent)[path.name]
            return mode


def call_git(path, *args, stdout=None):
    env = {
        'HOME': '/dev/null',
        'GIT_DIR': path._gp_root._gp_base,
    }
    print('calling git', *args)
    result = subprocess.run(
        ['git', *args],
        check=True,
        stdout=stdout,
        env=env,
    )
    return result


def git_stdout(path, *args):
    result = call_git(path, *args, stdout=subprocess.PIPE)
    return result.stdout.decode('utf-8')


def ls_tree(backend, path):
    try:
        return path._gp_tree
    except AttributeError:
        entries = collections.OrderedDict()
        result = git_stdout(path, 'ls-tree', backend.hex(path) + '^{tree}')
        for line in result.splitlines(keepends=False):
            mode, objtype, sha, name = TREE_ENTRY_RE.match(line).groups()
            entries[name] = int(mode, 8), objtype, sha
    path._gp_tree = entries
    return entries
