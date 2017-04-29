import tempfile
import os
from pathlib import Path, PurePosixPath
import binascii

import pytest
import pygit2
import yaml

import gitpathlib
from gitpathlib import testutil

from gitpathlib.gp_pygit import PygitBackend
from gitpathlib.gp_subprocess import SubprocessBackend


@pytest.fixture
def testrepo(tmpdir):
    contents = yaml.safe_load("""
        - tree:
            same:
                file: |
                    Here are the contents of a file
            same2:
                file: |
                    Here are the contents of a file
            extra:
                file: |
                    Here are the contents of a file
                extra:
                    Here are the contents of a file
            diff-filename:
                different: |
                    Here are the contents of a file
            diff-content:
                file: |
                    Here are different contents
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
                    file-utf8: ċóňťëñŧş ☺
                    file-utf16: [binary, [255, 254, 11, 1, 243, 0, 72, 1, 101,
                                          1, 235, 0, 241, 0, 103, 1, 95, 1, 32,
                                          0, 58, 38]]
                    file-binary: [binary, [115, 111, 109, 101, 0, 100, 97, 116,
                                           97, 255, 255]]
                    file-lines: "unix\\nwindows\\r\\nmac\\rnone"
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

@pytest.fixture(params=['pygit2', '/usr/bin/git'])
def get_path(request, testrepo):
    if request.param == 'pygit2':
        backend = PygitBackend()
    elif request.param == '/usr/bin/git':
        backend = SubprocessBackend()
        backend._assertions = {}
    else:
        raise ValueError(request.param)
    def _get_path(*args, **kwargs):
        kwargs.setdefault('backend', backend)
        return gitpathlib.GitPath(testrepo.path, *args, **kwargs)
    yield _get_path

    if request.param == '/usr/bin/git':
        for assertion, paths in backend._assertions.items():
            print('Assertion:', assertion.__name__)
            for func, path in set(paths):
                print('   ', path.root[:7], path.parts[1:],
                      'in', func.__name__)
                assertion(path)

@pytest.fixture
def part0(testrepo, tmpdir):
    tree = testrepo.head.peel(pygit2.Tree).hex
    return os.path.join(str(tmpdir), 'testrepo') + ':' + tree

@pytest.fixture
def cloned_repo(tmpdir, testrepo):
    path = os.path.join(str(tmpdir), 'clonedrepo')
    return pygit2.clone_repository(testrepo.path, path)


def test_head(testrepo, get_path):
    path = get_path()
    assert path.hex == testrepo.head.peel(pygit2.Tree).hex


def test_parent(testrepo, get_path):
    path = get_path('HEAD^')
    parent = testrepo.head.peel(pygit2.Commit).parents[0]
    assert path.hex == parent.peel(pygit2.Tree).hex


def test_components(testrepo, get_path):
    path = get_path('HEAD', 'dir', 'file')
    assert path.hex == testrepo.revparse_single('HEAD:dir/file').hex


def test_parts_empty(get_path, part0):
    path = get_path('HEAD')
    assert path.parts == (part0, )


def test_parts(get_path, part0):
    path = get_path('HEAD', 'dir', 'file')
    assert path.parts == (part0, 'dir', 'file')


def test_parts_slash(get_path, part0):
    path = get_path('HEAD', 'dir/file')
    assert path.parts == (part0, 'dir', 'file')


def test_parts_slashdot(get_path, part0):
    path = get_path('HEAD', 'dir/./file')
    assert path.parts == (part0, 'dir', 'file')


def test_dotdot(get_path, part0):
    path = get_path('HEAD', 'dir/../dir/file')
    assert path.parts == (part0, 'dir', '..', 'dir', 'file')


def test_hash(get_path):
    path1 = get_path('HEAD')
    path2 = get_path('master')
    assert hash(path1) == hash(path2)


def test_eq(get_path):
    path1 = get_path('HEAD')
    path2 = get_path('master')
    assert path1 == path2


def test_eq_dir(get_path):
    path1 = get_path('HEAD', 'dir')
    path2 = get_path('HEAD', 'dir')
    assert path1 == path2


def test_ne(get_path):
    path1 = get_path('HEAD', 'dir')
    path2 = get_path('HEAD', 'dir', 'file')
    assert path1 != path2


def test_eq_across_repos(testrepo, cloned_repo):
    path1 = gitpathlib.GitPath(testrepo.path)
    path2 = gitpathlib.GitPath(cloned_repo.path)
    assert path1 == path2


def test_ne_different_roots(get_path):
    path1 = get_path('HEAD', 'dir', 'file')
    path2 = get_path('HEAD:dir', 'file')
    assert path1 != path2


def test_slash(testrepo, get_path):
    path = get_path() / 'dir'
    assert path.hex == testrepo.revparse_single('HEAD:dir').hex


def test_slash_multiple(testrepo, get_path):
    path = get_path() / 'dir' / 'file'
    assert path.hex == testrepo.revparse_single('HEAD:dir/file').hex


def test_slash_combined(testrepo, get_path):
    path = get_path() / 'dir/file'
    assert path.hex == testrepo.revparse_single('HEAD:dir/file').hex


def test_slash_pathlib(testrepo, get_path):
    path = get_path() / Path('dir/file')
    assert path.hex == testrepo.revparse_single('HEAD:dir/file').hex


def test_slash_absolute_str(testrepo, get_path):
    path = get_path('HEAD', 'dir') / '/dir/file'
    assert path.hex == testrepo.revparse_single('HEAD:dir/file').hex


def test_slash_absolute_path(testrepo, get_path):
    path = get_path('HEAD', 'dir') / Path('/dir/file')
    assert path.hex == testrepo.revparse_single('HEAD:dir/file').hex


def test_no_open(testrepo, get_path):
    with pytest.raises(TypeError):
        open(get_path('HEAD', 'dir', 'file'))


def test_str_and_repr(testrepo, get_path, tmpdir):
    path = get_path('HEAD', 'dir', 'file')
    repo = os.path.join(str(tmpdir), 'testrepo')
    hex = testrepo.revparse_single('HEAD:').hex
    expected = "gitpathlib.GitPath('{repo}', '{hex}', 'dir', 'file')".format(
        repo=repo, hex=hex)
    assert str(path) == expected
    assert repr(path) == expected


def test_no_bytes(get_path):
    with pytest.raises(TypeError):
        path = get_path('HEAD', 'dir', 'file')
        bytes(path)


def test_drive(get_path, tmpdir):
    path = get_path('HEAD', 'dir', 'file')
    assert path.drive == os.path.join(str(tmpdir), 'testrepo')


def test_root(testrepo, get_path):
    path = get_path('HEAD', 'dir', 'file')
    assert path.root == testrepo.revparse_single('HEAD:').hex


def test_anchor(testrepo, get_path, tmpdir):
    path = get_path('HEAD', 'dir', 'file')
    repodir = os.path.join(str(tmpdir), 'testrepo')
    tree = testrepo.revparse_single('HEAD:').hex
    assert path.anchor == repodir + ':' + tree


def test_parents(get_path):
    root = get_path()
    path = root / 'dir' / 'file'
    parents = path.parents
    assert parents == (root / 'dir', root)


def test_parents_dotdot(get_path):
    root = get_path()
    path = root / 'dir' / '..' / 'file'
    parents = path.parents
    assert parents == (root / 'dir' / '..', root / 'dir', root)


def test_parent(get_path):
    root = get_path()
    path = root / 'dir'
    assert path.parent == root


def test_parent_dotdot(get_path):
    root = get_path()
    path = root / 'dir' / '..' / 'file'
    assert path.parent == root / 'dir' / '..'


def test_name(get_path):
    path = get_path() / 'dir'
    assert path.name == 'dir'


def test_name_root(get_path):
    path = get_path()
    assert path.name == ''


def test_suffix_and_friends_0(get_path):
    path = get_path('HEAD', 'archive')
    assert path.suffix == ''
    assert path.suffixes == []
    assert path.stem == 'archive'


def test_suffix_and_friends_1(get_path):
    path = get_path('HEAD', 'archive.tar')
    assert path.suffix == '.tar'
    assert path.suffixes == ['.tar']
    assert path.stem == 'archive'


def test_suffix_and_friends_2(get_path):
    path = get_path('HEAD', 'archive.tar.gz')
    assert path.suffix == '.gz'
    assert path.suffixes == ['.tar', '.gz']
    assert path.stem == 'archive.tar'


def test_suffix_and_friends_3(get_path):
    path = get_path('HEAD', 'archive.tar.gz.xz')
    assert path.suffix == '.xz'
    assert path.suffixes == ['.tar', '.gz', '.xz']
    assert path.stem == 'archive.tar.gz'


def test_as_posix_not_callable(get_path):
    path = get_path()
    with pytest.raises(TypeError):
        path.as_posix()


def test_as_uri_not_callable(get_path):
    path = get_path()
    with pytest.raises(ValueError):
        path.as_uri()


def test_is_absolute(get_path):
    path = get_path()
    assert path.is_absolute()


def test_is_reserved(get_path):
    path = get_path()
    assert not path.is_reserved()


def test_joinpath(testrepo, get_path):
    path = get_path().joinpath('dir')
    assert path.hex == testrepo.revparse_single('HEAD:dir').hex


def test_joinpath_multiple(testrepo, get_path):
    path = get_path().joinpath('dir', 'file')
    assert path.hex == testrepo.revparse_single('HEAD:dir/file').hex


def test_joinpath_combined(testrepo, get_path):
    path = get_path().joinpath('dir/file')
    assert path.hex == testrepo.revparse_single('HEAD:dir/file').hex


def test_joinpath_pathlib(testrepo, get_path):
    path = get_path().joinpath(Path('dir/file'))
    assert path.hex == testrepo.revparse_single('HEAD:dir/file').hex


def test_joinpath_absolute_str(testrepo, get_path):
    path = get_path('HEAD', 'dir').joinpath('/dir/file')
    assert path.hex == testrepo.revparse_single('HEAD:dir/file').hex


def test_joinpath_absolute_path(testrepo, get_path):
    path = get_path('HEAD', 'dir').joinpath(Path('/dir/file'))
    assert path.hex == testrepo.revparse_single('HEAD:dir/file').hex


@pytest.mark.parametrize(
    'pattern',
    [
        'file', '*le', 'dir/*le', '*',
        '/dir/file', '/dir/*le', '*/file', '/dir/file/', '*/*', '/*/*'
    ]
)
def test_match_positive(get_path, pattern):
    path = get_path('HEAD', 'dir', 'file')
    assert path.match(pattern)


@pytest.mark.parametrize(
    'pattern',
    [
        'bogus', 'dir', 'dir/',
        '/dir/fi', '/*/*/*',
    ]
)
def test_match_negative(get_path, pattern):
    path = get_path('HEAD', 'dir', 'file')
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
def test_relative_to_positive(get_path, path, expected):
    path1 = get_path('HEAD', 'dir', 'file')
    path2 = get_path('HEAD', path)
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
def test_relative_to_negative(get_path, rev, path):
    path1 = get_path('HEAD', 'dir')
    path2 = get_path(rev, path)
    with pytest.raises(ValueError):
        path1.relative_to(path2)


def test_with_name_positive(get_path, part0):
    path = get_path('HEAD', 'dir', 'file')
    path = path.with_name('otherfile')
    assert path.parts == (part0, 'dir', 'otherfile')


def test_with_name_noname(get_path):
    path = get_path('HEAD')
    with pytest.raises(ValueError):
        path = path.with_name('otherfile')


@pytest.mark.parametrize('badname', ['', 'bad/name', 'bad\0name'])
def test_with_name_badname(get_path, badname):
    path = get_path('HEAD', 'dir', 'file')
    with pytest.raises(ValueError):
        path = path.with_name(badname)


def test_with_suffix_positive(get_path, part0):
    path = get_path('HEAD', 'dir', 'file.txt')
    path = path.with_suffix('.py')
    assert path.parts == (part0, 'dir', 'file.py')


def test_with_name_noname(get_path):
    path = get_path('HEAD')
    with pytest.raises(ValueError):
        path = path.with_suffix('.py')


@pytest.mark.parametrize('badsuffix', ['', 'py', './py', '.\0?', '.'])
def test_with_name_badsuffix(get_path, badsuffix):
    path = get_path('HEAD', 'dir', 'file')
    with pytest.raises(ValueError):
        path = path.with_suffix(badsuffix)


def test_cwd(get_path):
    path = get_path('HEAD')
    assert path.cwd() == Path.cwd()


def test_home(get_path):
    path = get_path('HEAD')
    assert path.home() == Path.home()


def check_stat(meth, mode, expected_hex, size, exception):
    if exception:
        with pytest.raises(exception):
            meth()
        return
    stat = meth()
    print(oct(stat.st_mode))
    assert stat.st_mode == stat[0] == mode
    assert stat.st_ino == stat[1]
    assert stat.st_ino.to_bytes(20, 'little') == expected_hex
    assert stat.st_dev == stat[2] == -1
    assert stat.st_nlink == stat[3] == 1
    assert stat.st_uid == stat[4] == 0
    assert stat.st_gid == stat[5] == 0
    assert stat.st_size == stat[6] == size
    assert stat.st_atime == stat[7] == 0
    assert stat.st_mtime == stat[8] == 0
    assert stat.st_ctime == stat[9] == 0

@pytest.mark.parametrize(
    ['path', 'mode', 'size', 'exception'],
    [
        ('/', 0o40000, 12, None),
        ('/dir', 0o40000, 6, None),
        ('/dir/file', 0o100644, 32, None),
        ('/executable', 0o100755, 9, None),

        ('/link', 0o100644, 32, None),
        ('/link-to-dir', 0o40000, 6, None),

        ('/broken-link', None, None, gitpathlib.ObjectNotFoundError),
        ('/loop-link-a', None, None, RuntimeError),

        ('/nonexistent-file', None, None, gitpathlib.ObjectNotFoundError),
    ]
)
def test_stat(testrepo, get_path, path, mode, size, exception):
    path = get_path('HEAD', path)
    expected_hex = None if exception else testrepo[path.hex].id.raw
    check_stat(path.stat, mode, expected_hex, size, exception)

@pytest.mark.parametrize(
    ['path', 'mode', 'size', 'exception', 'expected_hex'],
    [
        ('/', 0o40000, 12, None, None),
        ('/dir', 0o40000, 6, None, None),
        ('/dir/file', 0o100644, 32, None, None),
        ('/executable', 0o100755, 9, None, None),

        ('/link', 0o120000, 8, None,
         'dea97c3520a755e4db5694d743aa8599511bbe9c'),
        ('/link-to-dir', 0o120000, 3, None,
         '87245193225f8ff56488ceab0dcd11467fe098d0'),

        ('/broken-link', 0o120000, 16, None,
         'b3394ad552da18d1b3d6a5c7e603520408d35425'),
        ('/loop-link-b', 0o120000, 11, None,
         '2b5652f1154a7aa2f62054230d116332d959d009'),

        ('/nonexistent-file', None, None, gitpathlib.ObjectNotFoundError,
         None),
    ]
)
def test_lstat(testrepo, get_path, path, mode, size, exception, expected_hex):
    path = get_path('HEAD', path)
    if exception:
        expected_hex = None
    else:
        if expected_hex:
            expected_hex = binascii.unhexlify(expected_hex)
        else:
            expected_hex = testrepo[path.hex].id.raw
    check_stat(path.lstat, mode, expected_hex, size, exception)


@pytest.mark.parametrize(
    'meth_name',
    ['chmod', 'mkdir', 'rename', 'replace', 'rmdir', 'symlink_to', 'touch',
     'unlink', 'write_bytes', 'write_text', 'lchmod'])
def test_mutate(get_path, meth_name):
    path = get_path('HEAD')
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
def test_exotic(get_path, meth_name, path):
    path = get_path('HEAD', path)
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
def test_resolve_good(get_path, path, expected, strict):
    path = get_path('HEAD', path)
    expected_path = get_path('HEAD', expected)
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
def test_resolve_ugly(get_path, path, expected, strict):
    path = get_path('HEAD', path)
    expected_path = get_path('HEAD', expected)
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
def test_resolve_bad(get_path, path, strict):
    path = get_path('HEAD', path)
    with pytest.raises(RuntimeError):
        path.resolve(strict)


@pytest.mark.parametrize('path', ['/dir', '/dir/file', 'bla/bla'])
def test_expaduser(get_path, path):
    path = get_path('HEAD', path)
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
def test_exists(get_path, path):
    path = get_path('HEAD', path)
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
def test_not_exists(get_path, path):
    path = get_path('HEAD', path)
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
def test_iterdir(get_path, directory, contents):
    path = get_path('HEAD', directory)
    expected = set(
        get_path('HEAD', directory, content)
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
def test_iterdir_fail(get_path, path, exception):
    path = get_path('HEAD', path)
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
def test_is_dir(get_path, path, expected):
    path = get_path('HEAD', path)
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
def test_is_file(get_path, path, expected):
    path = get_path('HEAD', path)
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
def test_is_symlink(get_path, path, expected):
    path = get_path('HEAD', path)
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
def test_glob(get_path, directory, pattern, matches):
    path = get_path('HEAD', directory)
    expected = {
        get_path('HEAD', match)
        for match in matches
    }
    assert set(path.glob(pattern)) == expected


@pytest.mark.parametrize(
    ['directory', 'pattern', 'exception'],
    [
        ('/', '', ValueError),
        ('/', '/', NotImplementedError),
    ])
def test_glob_bad(get_path, directory, pattern, exception):
    path = get_path('HEAD', directory)
    with pytest.raises(exception):
        list(path.glob(pattern))


@pytest.mark.parametrize(
    ['directory', 'pattern', 'matches'],
    [
        ('/', 'file', {'dir/file', 'dir/subdir/file',
                       'link-to-dir/file', 'link-to-dir/subdir/file',
                       'abs-link-to-dir/file', 'abs-link-to-dir/subdir/file',
                       }),
        ('/', '', {'/', 'dir', 'dir/subdir',
                   'link-to-dir', 'abs-link-to-dir',
                   'link-to-dir/subdir', 'abs-link-to-dir/subdir'}),
        ('/', '.', {'/', 'dir', 'dir/subdir',
                    'link-to-dir', 'abs-link-to-dir',
                    'link-to-dir/subdir', 'abs-link-to-dir/subdir'}),
        ('/', '..', {'/..', 'dir/..', 'dir/subdir/..',
                     'link-to-dir/..', 'abs-link-to-dir/..',
                     'link-to-dir/subdir/..', 'abs-link-to-dir/subdir/..'}),
    ])
def test_rglob(get_path, directory, pattern, matches):
    path = get_path('HEAD', directory)
    expected = {
        get_path('HEAD', match)
        for match in matches
    }
    assert set(path.rglob(pattern)) == expected


@pytest.mark.parametrize(
    ['directory', 'pattern', 'exception'],
    [
        ('/', '/', NotImplementedError),
        ('/', '/dir', NotImplementedError),
    ])
def test_rglob_bad(get_path, directory, pattern, exception):
    path = get_path('HEAD', directory)
    with pytest.raises(exception):
        list(path.rglob(pattern))


def test_group(get_path):
    path = get_path('HEAD')
    with pytest.raises(KeyError):
        path.group()


def test_owner(get_path):
    path = get_path('HEAD')
    with pytest.raises(KeyError):
        path.owner()


@pytest.mark.parametrize(
    ['path', 'expected'],
    [
        ('/dir/file', b'Here are the contents of a file\n'),
        ('/link', b'Here are the contents of a file\n'),
    ])
def test_read_bytes(get_path, path, expected):
    path = get_path('HEAD', path)
    assert path.read_bytes() == expected


@pytest.mark.parametrize(
    ['path', 'exception'],
    [
        ('/dir', gitpathlib.NotABlobError),
        ('/link-to-dir', gitpathlib.NotABlobError),
        ('/nonexistent-file', gitpathlib.ObjectNotFoundError),
        ('/broken-link', gitpathlib.ObjectNotFoundError),
    ])
def test_read_bytes_exc(get_path, path, exception):
    path = get_path('HEAD', path)
    with pytest.raises(exception):
        path.read_bytes()


@pytest.mark.parametrize(
    ['path', 'expected'],
    [
        ('/dir/file', 'Here are the contents of a file\n'),
        ('/link', 'Here are the contents of a file\n'),
    ])
def test_read_text(get_path, path, expected):
    path = get_path('HEAD', path)
    assert path.read_text() == expected


@pytest.mark.parametrize(
    ['path', 'exception'],
    [
        ('/dir', gitpathlib.NotABlobError),
        ('/link-to-dir', gitpathlib.NotABlobError),
        ('/nonexistent-file', gitpathlib.ObjectNotFoundError),
        ('/broken-link', gitpathlib.ObjectNotFoundError),
    ])
def test_read_text_exc(get_path, path, exception):
    path = get_path('HEAD', path)
    with pytest.raises(exception):
        path.read_text()


def test_open(get_path):
    path = get_path('HEAD', 'dir/subdir/file')
    with path.open() as f:
        assert f.read() == 'contents'


def test_open_rt(get_path):
    path = get_path('HEAD', 'dir/subdir/file')
    with path.open(mode='rt') as f:
        assert f.read() == 'contents'


def test_open_utf8(get_path):
    path = get_path('HEAD', 'dir/subdir/file-utf8')
    with path.open() as f:
        assert f.read() == 'ċóňťëñŧş ☺'


def test_open_utf8_explicit(get_path):
    path = get_path('HEAD', 'dir/subdir/file-utf8')
    with path.open(encoding='utf-8') as f:
        assert f.read() == 'ċóňťëñŧş ☺'


def test_open_utf8_bad(get_path):
    path = get_path('HEAD', 'dir/subdir/file-utf16')
    with pytest.raises(UnicodeDecodeError):
        with path.open() as f:
            f.read()


def test_open_utf8_errors(get_path):
    path = get_path('HEAD', 'dir/subdir/file-utf16')
    expected = '��\x0b\x01�\x00H\x01e\x01�\x00�\x00g\x01_\x01 \x00:&'
    with path.open(errors='replace') as f:
        assert f.read() == expected


def test_open_utf16(get_path):
    path = get_path('HEAD', 'dir/subdir/file-utf16')
    with path.open(encoding='utf-16') as f:
        assert f.read() == 'ċóňťëñŧş ☺'


@pytest.mark.parametrize(
    'mode', ['', 'w', 'x', 'a', 'b', 't', '+', 'U', 'rr', 'rbt', 'bt',
             'r+', 'rw', 'rx', 'ra', '?'])
def test_open_bad_mode(get_path, mode):
    path = get_path('HEAD', 'dir/file')
    with pytest.raises(ValueError):
        path.open(mode=mode)


def test_open_binary(get_path):
    path = get_path('HEAD', 'dir/subdir/file-binary')
    with path.open('rb') as f:
        assert f.read() == b'some\x00data\xff\xff'


def test_open_binary_encoding(get_path):
    path = get_path('HEAD', 'dir/subdir/file-binary')
    with pytest.raises(ValueError):
        path.open('rb', encoding='utf-8')


def test_open_binary_errors(get_path):
    path = get_path('HEAD', 'dir/subdir/file-binary')
    with pytest.raises(ValueError):
        path.open('rb', errors='strict')


def test_open_binary_newline(get_path):
    path = get_path('HEAD', 'dir/subdir/file-binary')
    with pytest.raises(ValueError):
        path.open('rb', newline='')


@pytest.mark.parametrize(
    ['newline', 'expected'],
    [
        (None, ['unix\n', 'windows\n', 'mac\n', 'none']),
        ('', ['unix\n', 'windows\r\n', 'mac\r', 'none']),
        ('\n', ['unix\n', 'windows\r\n', 'mac\rnone']),
        ('\r\n', ['unix\nwindows\r\n', 'mac\rnone']),
        ('\r', ['unix\nwindows\r', '\nmac\r', 'none']),
    ])
def test_open_newline(get_path, newline, expected):
    path = get_path('HEAD', 'dir/subdir/file-lines')
    with path.open('rb') as f:
        assert f.read() == b'unix\nwindows\r\nmac\rnone'
    with path.open(newline=newline) as f:
        print(f)
        assert f.readlines() == expected


@pytest.mark.parametrize(
    ['rev1', 'path1', 'rev2', 'path2', 'expected'],
    [
        ('HEAD^^', 'same/file', 'HEAD', 'dir/file', True),
        ('HEAD^^', 'same/file', 'HEAD^^', 'same2/file', True),
        ('HEAD', 'dir/file', 'HEAD', 'dir', False),
        ('HEAD^^', 'same', 'HEAD^^', 'same2', True),
        ('HEAD^^', 'same', 'HEAD', 'dir', False),
        ('HEAD^^', 'same', 'HEAD^^', 'extra', False),
        ('HEAD^^', 'same', 'HEAD^^', 'diff-filename', False),
        ('HEAD^^', 'same', 'HEAD^^', 'diff-content', False),
        ('HEAD', 'dir/file', 'HEAD', 'link', True),
        ('HEAD', 'link-to-dir', 'HEAD', 'dir', True),
        ('HEAD', 'link', 'HEAD', 'link', True),
    ])
def test_samefile(get_path, rev1, path1, rev2, path2, expected):
    path1 = get_path(rev1, path1)
    path2 = get_path(rev2, path2)
    assert path1.samefile(path2) == expected


@pytest.mark.parametrize(
    ['path', 'exception'],
    [
        ('nonexistent-file', gitpathlib.ObjectNotFoundError),
        ('broken-link', gitpathlib.ObjectNotFoundError),
        ('self-loop-link', RuntimeError),
    ])
def test_samefile_bad_path(get_path, path, exception):
    path1 = get_path('HEAD', 'dir')
    path2 = get_path('HEAD', path)
    with pytest.raises(exception):
        path1.samefile(path2)


@pytest.mark.parametrize(
    'other',
    [
        'a string',
        Path('/dir'),
        Path('dir'),
        3j-8,
    ])
def test_samefile_otherobject(get_path, other):
    path = get_path('HEAD', 'dir')
    assert path.samefile(other) == False
