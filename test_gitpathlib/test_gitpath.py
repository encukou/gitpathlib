import tempfile
import os
from pathlib import Path, PurePosixPath

import pytest
import pygit2
import yaml

import gitpathlib
from gitpathlib import testutil


@pytest.fixture
def testrepo(tmpdir):
    contents = yaml.safe_load("""
        - tree:
            dir:
                file: |
                    Here are old contents of a file
        - tree:
            dir:
                file: |
                    Here are the contents of a file
                link-up: [link, ..]
                link-dot: [link, .]
                link-self-rel: [link, ../dir]
                link-self-abs: [link, /dir]
                subdir:
                    file: contents
                    link-back: [link, ../..]
            link: [link, dir/file]
            broken-link: [link, nonexistent-file]
            link-to-dir: [link, dir]
            abs-link: [link, /dir/file]
            abs-link-to-dir: [link, /dir/]
            abs-broken-link: [link, /nonexistent-file]
            self-loop-link: [link, self-loop-link]
            abs-self-loop-link: [link, /self-loop-link]
            loop-link-a: [link, loop-link-b]
            loop-link-b: [link, loop-link-a]
            executable: [executable, '#!/bin/sh']
    """)
    path = os.path.join(str(tmpdir), 'testrepo')
    testutil.make_repo(path, contents)
    return pygit2.Repository(path)

@pytest.fixture
def part0(testrepo, tmpdir):
    tree = testrepo.head.peel(pygit2.Tree).hex
    return os.path.join(str(tmpdir), 'testrepo') + ':' + tree

@pytest.fixture
def cloned_repo(tmpdir, testrepo):
    path = os.path.join(str(tmpdir), 'clonedrepo')
    return pygit2.clone_repository(testrepo.path, path)


def test_head(testrepo):
    path = gitpathlib.GitPath(testrepo.path)
    assert path.hex == testrepo.head.peel(pygit2.Tree).hex


def test_parent(testrepo):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD^')
    parent = testrepo.head.peel(pygit2.Commit).parents[0]
    assert path.hex == parent.peel(pygit2.Tree).hex


def test_components(testrepo):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', 'dir', 'file')
    assert path.hex == testrepo.revparse_single('HEAD:dir/file').hex


def test_parts_empty(testrepo, part0):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD')
    assert path.parts == (part0, )


def test_parts(testrepo, part0):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', 'dir', 'file')
    assert path.parts == (part0, 'dir', 'file')


def test_parts_slash(testrepo, part0):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', 'dir/file')
    assert path.parts == (part0, 'dir', 'file')


def test_parts_slashdot(testrepo, part0):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', 'dir/./file')
    assert path.parts == (part0, 'dir', 'file')


def test_dotdot(testrepo, part0):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', 'dir/../dir/file')
    assert path.parts == (part0, 'dir', '..', 'dir', 'file')


def test_hash(testrepo):
    path1 = gitpathlib.GitPath(testrepo.path, 'HEAD')
    path2 = gitpathlib.GitPath(testrepo.path, 'master')
    assert hash(path1) == hash(path2)


def test_eq(testrepo):
    path1 = gitpathlib.GitPath(testrepo.path, 'HEAD')
    path2 = gitpathlib.GitPath(testrepo.path, 'master')
    assert path1 == path2


def test_eq_dir(testrepo):
    path1 = gitpathlib.GitPath(testrepo.path, 'HEAD', 'dir')
    path2 = gitpathlib.GitPath(testrepo.path, 'HEAD', 'dir')
    assert path1 == path2


def test_ne(testrepo):
    path1 = gitpathlib.GitPath(testrepo.path, 'HEAD', 'dir')
    path2 = gitpathlib.GitPath(testrepo.path, 'HEAD', 'dir', 'file')
    assert path1 != path2


def test_eq_across_repos(testrepo, cloned_repo):
    path1 = gitpathlib.GitPath(testrepo.path)
    path2 = gitpathlib.GitPath(cloned_repo.path)
    assert path1 == path2


def test_ne_different_roots(testrepo):
    path1 = gitpathlib.GitPath(testrepo.path, 'HEAD', 'dir', 'file')
    path2 = gitpathlib.GitPath(testrepo.path, 'HEAD:dir', 'file')
    assert path1 != path2


def test_slash(testrepo):
    path = gitpathlib.GitPath(testrepo.path) / 'dir'
    assert path.hex == testrepo.revparse_single('HEAD:dir').hex


def test_slash_multiple(testrepo):
    path = gitpathlib.GitPath(testrepo.path) / 'dir' / 'file'
    assert path.hex == testrepo.revparse_single('HEAD:dir/file').hex


def test_slash_combined(testrepo):
    path = gitpathlib.GitPath(testrepo.path) / 'dir/file'
    assert path.hex == testrepo.revparse_single('HEAD:dir/file').hex


def test_slash_pathlib(testrepo):
    path = gitpathlib.GitPath(testrepo.path) / Path('dir/file')
    assert path.hex == testrepo.revparse_single('HEAD:dir/file').hex


def test_slash_absolute_str(testrepo):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', 'dir') / '/dir/file'
    assert path.hex == testrepo.revparse_single('HEAD:dir/file').hex


def test_slash_absolute_path(testrepo):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', 'dir') / Path('/dir/file')
    assert path.hex == testrepo.revparse_single('HEAD:dir/file').hex


def test_no_open(testrepo):
    with pytest.raises(TypeError):
        open(gitpathlib.GitPath(testrepo.path, 'HEAD', 'dir', 'file'))


def test_str_and_repr(testrepo, tmpdir):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', 'dir', 'file')
    repo = os.path.join(str(tmpdir), 'testrepo')
    hex = testrepo.revparse_single('HEAD:').hex
    expected = "gitpathlib.GitPath('{repo}', '{hex}', 'dir', 'file')".format(
        repo=repo, hex=hex)
    assert str(path) == expected
    assert repr(path) == expected


def test_no_bytes(testrepo):
    with pytest.raises(TypeError):
        path = gitpathlib.GitPath(testrepo.path, 'HEAD', 'dir', 'file')
        bytes(path)


def test_drive(testrepo, tmpdir):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', 'dir', 'file')
    assert path.drive == os.path.join(str(tmpdir), 'testrepo')


def test_root(testrepo, tmpdir):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', 'dir', 'file')
    assert path.root == testrepo.revparse_single('HEAD:').hex


def test_anchor(testrepo, tmpdir):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', 'dir', 'file')
    repodir = os.path.join(str(tmpdir), 'testrepo')
    tree = testrepo.revparse_single('HEAD:').hex
    assert path.anchor == repodir + ':' + tree


def test_parents(testrepo):
    root = gitpathlib.GitPath(testrepo.path)
    path = root / 'dir' / 'file'
    parents = path.parents
    assert parents == (root / 'dir', root)


def test_parents_dotdot(testrepo):
    root = gitpathlib.GitPath(testrepo.path)
    path = root / 'dir' / '..' / 'file'
    parents = path.parents
    assert parents == (root / 'dir' / '..', root / 'dir', root)


def test_parent(testrepo):
    root = gitpathlib.GitPath(testrepo.path)
    path = root / 'dir'
    assert path.parent == root


def test_parent_dotdot(testrepo):
    root = gitpathlib.GitPath(testrepo.path)
    path = root / 'dir' / '..' / 'file'
    assert path.parent == root / 'dir' / '..'


def test_name(testrepo):
    path = gitpathlib.GitPath(testrepo.path) / 'dir'
    assert path.name == 'dir'


def test_name_root(testrepo):
    path = gitpathlib.GitPath(testrepo.path)
    assert path.name == ''


def test_suffix_and_friends_0(testrepo):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', 'archive')
    assert path.suffix == ''
    assert path.suffixes == []
    assert path.stem == 'archive'


def test_suffix_and_friends_1(testrepo):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', 'archive.tar')
    assert path.suffix == '.tar'
    assert path.suffixes == ['.tar']
    assert path.stem == 'archive'


def test_suffix_and_friends_2(testrepo):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', 'archive.tar.gz')
    assert path.suffix == '.gz'
    assert path.suffixes == ['.tar', '.gz']
    assert path.stem == 'archive.tar'


def test_suffix_and_friends_3(testrepo):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', 'archive.tar.gz.xz')
    assert path.suffix == '.xz'
    assert path.suffixes == ['.tar', '.gz', '.xz']
    assert path.stem == 'archive.tar.gz'


def test_as_posix_not_callable(testrepo):
    path = gitpathlib.GitPath(testrepo.path)
    with pytest.raises(TypeError):
        path.as_posix()


def test_as_uri_not_callable(testrepo):
    path = gitpathlib.GitPath(testrepo.path)
    with pytest.raises(ValueError):
        path.as_uri()


def test_is_absolute(testrepo):
    path = gitpathlib.GitPath(testrepo.path)
    assert path.is_absolute()


def test_is_reserved(testrepo):
    path = gitpathlib.GitPath(testrepo.path)
    assert not path.is_reserved()


def test_joinpath(testrepo):
    path = gitpathlib.GitPath(testrepo.path).joinpath('dir')
    assert path.hex == testrepo.revparse_single('HEAD:dir').hex


def test_joinpath_multiple(testrepo):
    path = gitpathlib.GitPath(testrepo.path).joinpath('dir', 'file')
    assert path.hex == testrepo.revparse_single('HEAD:dir/file').hex


def test_joinpath_combined(testrepo):
    path = gitpathlib.GitPath(testrepo.path).joinpath('dir/file')
    assert path.hex == testrepo.revparse_single('HEAD:dir/file').hex


def test_joinpath_pathlib(testrepo):
    path = gitpathlib.GitPath(testrepo.path).joinpath(Path('dir/file'))
    assert path.hex == testrepo.revparse_single('HEAD:dir/file').hex


def test_joinpath_absolute_str(testrepo):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', 'dir').joinpath('/dir/file')
    assert path.hex == testrepo.revparse_single('HEAD:dir/file').hex


def test_joinpath_absolute_path(testrepo):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', 'dir').joinpath(Path('/dir/file'))
    assert path.hex == testrepo.revparse_single('HEAD:dir/file').hex


@pytest.mark.parametrize(
    'pattern',
    [
        'file', '*le', 'dir/*le', '*',
        '/dir/file', '/dir/*le', '*/file', '/dir/file/', '*/*', '/*/*'
    ]
)
def test_match_positive(testrepo, pattern):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', 'dir', 'file')
    assert path.match(pattern)


@pytest.mark.parametrize(
    'pattern',
    [
        'bogus', 'dir', 'dir/',
        '/dir/fi', '/*/*/*',
    ]
)
def test_match_negative(testrepo, pattern):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', 'dir', 'file')
    assert not path.match(pattern)


@pytest.mark.parametrize(
    ['path', 'expected'],
    [
        ('dir', 'file'),
        ('/dir', 'file'),
        ('/', 'dir/file'),
        ('', 'dir/file'),
        ('dir/file', '.'),
    ]
)
def test_relative_to_positive(testrepo, path, expected):
    path1 = gitpathlib.GitPath(testrepo.path, 'HEAD', 'dir', 'file')
    path2 = gitpathlib.GitPath(testrepo.path, 'HEAD', path)
    assert path1.relative_to(path2) == PurePosixPath(expected)


@pytest.mark.parametrize(
    ['rev', 'path'],
    [
        ('HEAD', 'dir/file'),
        ('HEAD:dir', 'file'),
        ('HEAD', 'diff'),
        ('HEAD:dir', '.'),
    ]
)
def test_relative_to_negative(testrepo, rev, path):
    path1 = gitpathlib.GitPath(testrepo.path, 'HEAD', 'dir')
    path2 = gitpathlib.GitPath(testrepo.path, rev, path)
    with pytest.raises(ValueError):
        path1.relative_to(path2)


def test_with_name_positive(testrepo, part0):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', 'dir', 'file')
    path = path.with_name('otherfile')
    assert path.parts == (part0, 'dir', 'otherfile')


def test_with_name_noname(testrepo):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD')
    with pytest.raises(ValueError):
        path = path.with_name('otherfile')


@pytest.mark.parametrize('badname', ['', 'bad/name', 'bad\0name'])
def test_with_name_badname(testrepo, badname):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', 'dir', 'file')
    with pytest.raises(ValueError):
        path = path.with_name(badname)


def test_with_suffix_positive(testrepo, part0):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', 'dir', 'file.txt')
    path = path.with_suffix('.py')
    assert path.parts == (part0, 'dir', 'file.py')


def test_with_name_noname(testrepo):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD')
    with pytest.raises(ValueError):
        path = path.with_suffix('.py')


@pytest.mark.parametrize('badsuffix', ['', 'py', './py', '.\0?', '.'])
def test_with_name_badsuffix(testrepo, badsuffix):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', 'dir', 'file')
    with pytest.raises(ValueError):
        path = path.with_suffix(badsuffix)


def test_cwd(testrepo):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD')
    assert path.cwd() == Path.cwd()


def test_home(testrepo):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD')
    assert path.home() == Path.home()


@pytest.mark.parametrize(
    ['path', 'mode', 'size', 'g_type'],
    [
        ('/', 0o40000, 12, 'tree'),
        ('/dir', 0o40000, 6, 'tree'),
        ('/dir/file', 0o100644, 32, 'blob'),
        ('/executable', 0o100755, 9, 'blob'),

        ('/link', 0o100644, 32, 'blob'),
        ('/link-to-dir', 0o40000, 6, 'blob'),

        ('/broken-link', None, None, None),
    ]
)
def test_stat_root(testrepo, path, mode, size, g_type):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', path)

    if mode is None:
        with pytest.raises(gitpathlib.ObjectNotFoundError):
            stat = path.stat()
        return

    stat = path.stat()
    print(oct(stat.st_mode))
    assert stat.st_mode == stat[0] == mode
    assert stat.st_ino == stat[1]
    assert stat.st_ino.to_bytes(20, 'little') == testrepo[path.hex].id.raw
    assert stat.st_dev == stat[2] == -1
    assert stat.st_nlink == stat[3] == 1
    assert stat.st_uid == stat[4] == 0
    assert stat.st_gid == stat[5] == 0
    assert stat.st_size == stat[6] == size
    assert stat.st_atime == stat[7] == 0
    assert stat.st_mtime == stat[8] == 0
    assert stat.st_ctime == stat[9] == 0


@pytest.mark.parametrize(
    'meth_name',
    ['chmod', 'mkdir', 'rename', 'replace', 'rmdir', 'symlink_to', 'touch',
     'unlink', 'write_bytes', 'write_text', 'lchmod'])
def test_mutate(testrepo, meth_name):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD')
    meth = getattr(path, meth_name)
    with pytest.raises(PermissionError):
        meth()
    with pytest.raises(PermissionError):
        meth(0)
    with pytest.raises(PermissionError):
        meth('/foo')
    with pytest.raises(PermissionError):
        meth(b'foo')


@pytest.mark.parametrize(
    'meth_name',
    ['is_socket', 'is_fifo', 'is_block_device', 'is_char_device'])
@pytest.mark.parametrize(
    'path',
    ['/', '/dir', '/link', '/dir/file', '/nonexistent-file',
     '/broken-link'])
def test_exotic(testrepo, meth_name, path):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', path)
    meth = getattr(path, meth_name)
    assert meth() == False


@pytest.mark.parametrize('strict', (True, False))
@pytest.mark.parametrize(
    ['path', 'expected'],
    [
        ('.', '/'),
        ('/', '/'),
        ('/.', '/'),
        ('/./.', '/'),
        ('/dir', '/dir'),
        ('/dir/file', '/dir/file'),
        ('/dir/.', '/dir'),
        ('/dir/..', '/'),
        ('/dir/../.', '/'),
        ('/dir/./..', '/'),
        ('/dir/../dir', '/dir'),
        ('/dir/./.././dir', '/dir'),
        ('/dir/link-up', '/'),
        ('/dir/./link-up/.', '/'),
        ('/dir/link-dot', '/dir'),
        ('/dir/link-self-rel', '/dir'),
        ('/dir/link-self-abs', '/dir'),
        ('/link', '/dir/file'),
        ('/link-to-dir', '/dir'),
        ('/link-to-dir/.', '/dir'),
        ('/link-to-dir/file', '/dir/file'),
        ('/abs-link', '/dir/file'),
        ('/abs-link-to-dir', '/dir'),
        ('/abs-link-to-dir/.', '/dir'),
        ('/abs-link-to-dir/file', '/dir/file'),
    ])
def test_resolve_good(testrepo, path, expected, strict):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', path)
    expected_path = gitpathlib.GitPath(testrepo.path, 'HEAD', expected)
    assert path.resolve(strict) == expected_path


@pytest.mark.parametrize('strict', (True, False))
@pytest.mark.parametrize(
    ['path', 'expected'],
    [
        ('/broken-link', '/nonexistent-file'),
        ('/broken-link/more/stuff', '/nonexistent-file/more/stuff'),
        ('/broken-link/more/../stuff', '/nonexistent-file/stuff'),
        ('/link-to-dir/../broken-link/stuff', '/nonexistent-file/stuff'),
        ('/abs-broken-link', '/nonexistent-file'),
        ('/abs-broken-link/more', '/nonexistent-file/more'),
        ('/dir/nonexistent/..', '/dir'),
        ('/dir/nonexistent/.', '/dir/nonexistent'),
        #('/dir/file/..', '/dir'),  # XXX - what to do here?
    ])
def test_resolve_ugly(testrepo, path, expected, strict):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', path)
    expected_path = gitpathlib.GitPath(testrepo.path, 'HEAD', expected)
    if strict:
        with pytest.raises(gitpathlib.ObjectNotFoundError):
            path.resolve(strict)
    else:
        assert path.resolve(strict) == expected_path


@pytest.mark.parametrize('strict', (True, False))
@pytest.mark.parametrize(
    'path',
    [
        '/self-loop-link',
        '/self-loop-link/more',
        '/abs-self-loop-link',
        '/abs-self-loop-link/more',
        '/loop-link-a',
        '/loop-link-a',
        '/loop-link-b/more',
        '/loop-link-b/more',
    ])
def test_resolve_bad(testrepo, path, strict):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', path)
    with pytest.raises(RuntimeError):
        path.resolve(strict)


@pytest.mark.parametrize('path', ['/dir', '/dir/file', 'bla/bla'])
def test_expaduser(testrepo, path):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', path)
    assert path.expanduser() == path


@pytest.mark.parametrize(
    'path',
    [
        '/',
        '/dir',
        '/dir/file',
        '/link',
        '/link-to-dir/file',
        '/dir/file/..',
    ])
def test_exists(testrepo, path):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', path)
    assert path.exists()


@pytest.mark.parametrize(
    'path',
    [
        '/nonexistent-file',
        '/broken-link',
        '/dir/nonexistent-file',
        '/dir/../nonexistent-file',
        '/dir/nonexistent/..',
    ])
def test_not_exists(testrepo, path):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', path)
    assert not path.exists()


@pytest.mark.parametrize(
    ['directory', 'contents'],
    [
        ('/', {'dir', 'link', 'broken-link', 'link-to-dir', 'abs-link',
               'abs-link-to-dir', 'abs-broken-link', 'self-loop-link',
               'abs-self-loop-link', 'loop-link-a', 'loop-link-b',
               'executable'}),
        ('/dir', {'file', 'link-up', 'link-dot', 'link-self-rel',
                  'link-self-abs', 'subdir'}),
    ])
def test_iterdir(testrepo, directory, contents):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', directory)
    expected = set(
        gitpathlib.GitPath(testrepo.path, 'HEAD', directory, content)
        for content in contents
    )
    assert set(path.iterdir()) == set(expected)


@pytest.mark.parametrize(
    ['path', 'exception'],
    [
        ('/dir/file', gitpathlib.NotATreeError),
        ('/link', gitpathlib.NotATreeError),
        ('/nonexistent-file', gitpathlib.ObjectNotFoundError),
        ('/broken-link', gitpathlib.ObjectNotFoundError),
    ])
def test_iterdir_fail(testrepo, path, exception):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', path)
    with pytest.raises(exception):
        assert set(path.iterdir())


@pytest.mark.parametrize(
    ['path', 'expected'],
    [
        ('/', True),
        ('/dir', True),
        ('/dir/file', False),
        ('/link', False),
        ('/link-to-dir', True),
        ('/nonexistent-file', False),
        ('/broken-link', False),
        ('/dir/nonexistent/..', False),
        ('/dir/file/..', True),  # XXX - what to do here?
    ])
def test_is_dir(testrepo, path, expected):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', path)
    assert path.is_dir() == expected


@pytest.mark.parametrize(
    ['path', 'expected'],
    [
        ('/', False),
        ('/dir', False),
        ('/dir/file', True),
        ('/link', True),
        ('/link-to-dir', False),
        ('/nonexistent-file', False),
        ('/broken-link', False),
        ('/dir/nonexistent/..', False),
        ('/dir/file/..', False),
    ])
def test_is_file(testrepo, path, expected):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', path)
    assert path.is_file() == expected


@pytest.mark.parametrize(
    ['path', 'expected'],
    [
        ('/', False),
        ('/dir', False),
        ('/dir/file', False),
        ('/link', True),
        ('/link-to-dir', True),
        ('/nonexistent-file', False),
        ('/broken-link', True),
        ('/dir/nonexistent/..', False),
        ('/dir/file/..', False),
        ('/link-to-dir/subdir/..', False),
    ])
def test_is_symlink(testrepo, path, expected):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', path)
    assert path.is_symlink() == expected


@pytest.mark.parametrize(
    ['directory', 'pattern', 'matches'],
    [
        ('/', 'dir', {'dir'}),
        ('/', '*link', {'link', 'broken-link', 'abs-link', 'abs-broken-link',
                        'self-loop-link', 'abs-self-loop-link'}),
        ('/', '**/file', {'dir/file', 'dir/subdir/file',
                          'link-to-dir/file', 'link-to-dir/subdir/file',
                          'abs-link-to-dir/file', 'abs-link-to-dir/subdir/file',
                          }),
        ('/', '**', {'/', 'dir', 'dir/subdir',
                     'link-to-dir', 'abs-link-to-dir',
                     'link-to-dir/subdir', 'abs-link-to-dir/subdir'}),
        ('/', '**/..', {'/..', 'dir/..', 'dir/subdir/..',
                        'link-to-dir/..', 'abs-link-to-dir/..',
                        'link-to-dir/subdir/..', 'abs-link-to-dir/subdir/..'}),
        ('/file', '*', {}),
        ('/dir', '../ex*e', {'dir/../executable'}),
    ])
def test_glob(testrepo, directory, pattern, matches):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', directory)
    expected = {
        gitpathlib.GitPath(testrepo.path, 'HEAD', match)
        for match in matches
    }
    assert set(path.glob(pattern)) == expected


@pytest.mark.parametrize(
    ['directory', 'pattern', 'exception'],
    [
        ('/', '', ValueError),
        ('/', '/', NotImplementedError),
    ])
def test_glob_bad(testrepo, directory, pattern, exception):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', directory)
    with pytest.raises(exception):
        list(path.glob(pattern))


def test_group(testrepo):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD')
    with pytest.raises(KeyError):
        path.group()


def test_owner(testrepo):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD')
    with pytest.raises(KeyError):
        path.owner()


@pytest.mark.parametrize(
    ['path', 'expected'],
    [
        ('/dir/file', b'Here are the contents of a file\n'),
        ('/link', b'Here are the contents of a file\n'),
    ])
def test_read_bytes(testrepo, path, expected):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', path)
    assert path.read_bytes() == expected


@pytest.mark.parametrize(
    ['path', 'exception'],
    [
        ('/dir', gitpathlib.NotABlobError),
        ('/link-to-dir', gitpathlib.NotABlobError),
        ('/nonexistent-file', gitpathlib.ObjectNotFoundError),
        ('/broken-link', gitpathlib.ObjectNotFoundError),
    ])
def test_read_bytes_exc(testrepo, path, exception):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', path)
    with pytest.raises(exception):
        path.read_bytes()


@pytest.mark.parametrize(
    ['path', 'expected'],
    [
        ('/dir/file', 'Here are the contents of a file\n'),
        ('/link', 'Here are the contents of a file\n'),
    ])
def test_read_text(testrepo, path, expected):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', path)
    assert path.read_text() == expected


@pytest.mark.parametrize(
    ['path', 'exception'],
    [
        ('/dir', gitpathlib.NotABlobError),
        ('/link-to-dir', gitpathlib.NotABlobError),
        ('/nonexistent-file', gitpathlib.ObjectNotFoundError),
        ('/broken-link', gitpathlib.ObjectNotFoundError),
    ])
def test_read_text_exc(testrepo, path, exception):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', path)
    with pytest.raises(exception):
        path.read_text()
