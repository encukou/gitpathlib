import pygit2

class GitPath:
    """
    A `pathlib`_-style *path flavor* that allows reading from Git repositories.

    ``GitPath`` objects can be created from a *repository path*. This opens the
    given repository:

    >>> from gitpathlib import GitPath
    >>> GitPath('path/to/repo')
    gitpathlib.GitPath('.../path/to/repo/', 'HEAD')

    A commit ID or a branch (or reference) name can be given as *ref* to open
    a particular commit (or *tree-ish*).

    >>> GitPath('path/to/repo', 'HEAD^')
    gitpathlib.GitPath('.../path/to/repo/', 'HEAD^')

    Additional path segments will select a given file.

    >>> GitPath('path/to/repo', 'HEAD^', 'dir/file')
    gitpathlib.GitPath('.../path/to/repo/', 'HEAD^', 'dir', 'file')

    """
    def __new__(cls, repository_path, ref='HEAD', *segments):
        repo = pygit2.Repository(repository_path)
        parsed_segments = tuple(parse_segments(segments))
        objs = [repo.revparse_single(ref)]
        for segment in parsed_segments:
            if segment == '..':
                objs.pop()
                if not objs:
                    raise ValueError('no parent for ".." in path')
            else:
                objs.append(repo[objs[-1].peel(pygit2.Tree)[segment].id])
        return cls._gp_make(repo, ref, parsed_segments, objs[-1])

    @classmethod
    def _gp_make(cls, repo, refname, segments, obj):
        self = super(cls, GitPath).__new__(cls)
        self._gp_repo = repo
        self._gp_refname = refname
        self._gp_segments = tuple(segments)
        self._gp_obj = obj
        return self

    @property
    def hex(self):
        return self._gp_obj.hex

    @property
    def parts(self):
        return (repo_path(self._gp_repo), self._gp_refname, *self._gp_segments)

    def __repr__(self):
        if type(self) == GitPath:
            qualname = 'gitpathlib.GitPath'
        else:
            qualname = '{tp.__module__}.{tp.__qualname__}'.format(tp=type(self))
        return '{qualname}{args}'.format(
            qualname=qualname,
            args=self.parts,
        )

def parse_segments(segments):
    for segment in segments:
        for part in segment.split('/'):
            if part not in ('', '.'):
                yield part

def repo_path(repo):
    if repo.is_bare:
        return repo.path
    else:
        return repo.workdir
