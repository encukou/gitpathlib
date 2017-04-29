import subprocess
import collections
import re

from .gp_base import NotATreeError, NotABlobError

TREE_ENTRY_RE = re.compile(r'^(\d+) (\w+) (\w+)\t(.+)$')
GIT_MODE_TREE = 0o40000

class SubprocessBackend:
    """GitPath backend based on calling the ``git`` binary
    """

    def init_root(self, path, repository_path, rev):
        path._gp_base = repository_path
        rev = git_stdout(path, 'rev-parse', rev).strip()
        rev = git_stdout(path, 'rev-parse', rev + '^{tree}').strip()
        path._gp_rev = rev
        assert re.match('^[0-9a-f]{40}$', path._gp_rev)

    def init_child(self, parent, child):
        child._gp_base = parent._gp_base

    def hex(self, path):
        try:
            return path._gp_rev
        except AttributeError:
            parent_hex = self.hex(path.parent)
            ref = '{}:{}'.format(parent_hex, path.name)
            rev = git_stdout(path, 'rev-parse', ref).strip()
            path._gp_rev = rev
            return rev

    def has_entry(self, path, name):
        return name in ls_tree(self, path)

    def listdir(self, path):
        return tuple(ls_tree(self, path))

    def get_type(self, path):
        return git_stdout(path, 'cat-file', '-t', self.hex(path)).strip()

    def read(self, path):
        result = call_git(path,
                          'cat-file',
                          '-p', self.hex(path),
                          stdout=subprocess.PIPE)
        return result.stdout

    def get_size(self, path):
        if self.get_type(path) == 'blob':
            return int(git_stdout(path, 'cat-file', '-s', self.hex(path)))
        elif self.get_type(path) == 'tree':
            return len(ls_tree(self, path))
        else:
            return 0

    def get_mode(self, path):
        if path is path.parent:
            return GIT_MODE_TREE
        else:
            mode, objtype, sha = ls_tree(self, path.parent)[path.name]
            return mode


def call_git(path, *args, stdout=None):
    env = {
        'HOME': '/dev/null',
        'GIT_DIR': path._gp_base,
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
