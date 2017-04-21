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
