import tempfile
import os
from pathlib import Path

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
    return os.path.join(str(tmpdir), 'testrepo') + '/:' + tree

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
    repo = os.path.join(str(tmpdir), 'testrepo/')
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
    assert path.drive == os.path.join(str(tmpdir), 'testrepo/')


def test_root(testrepo, tmpdir):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', 'dir', 'file')
    assert path.root == testrepo.revparse_single('HEAD:').hex
