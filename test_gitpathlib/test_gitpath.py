import tempfile
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
    path = str(tmpdir) + 'testrepo'
    testutil.make_repo(path, contents)
    return pygit2.Repository(path)

@pytest.fixture
def cloned_repo(tmpdir, testrepo):
    path = str(tmpdir) + 'clonedrepo'
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


def test_parts_empty(testrepo):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD')
    tree = testrepo.head.peel(pygit2.Tree).hex
    assert path.parts == (Path(testrepo.path), tree)


def test_parts(testrepo):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', 'dir', 'file')
    tree = testrepo.head.peel(pygit2.Tree).hex
    assert path.parts == (Path(testrepo.path), tree, 'dir', 'file')


def test_parts_slash(testrepo):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', 'dir/file')
    tree = testrepo.head.peel(pygit2.Tree).hex
    assert path.parts == (Path(testrepo.path), tree, 'dir', 'file')


def test_parts_slashdot(testrepo):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', 'dir/./file')
    tree = testrepo.head.peel(pygit2.Tree).hex
    assert path.parts == (Path(testrepo.path), tree, 'dir', 'file')


def test_dotdot(testrepo):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', 'dir/../dir/file')
    tree = testrepo.head.peel(pygit2.Tree).hex
    assert path.parts == (Path(testrepo.path), tree, 'dir', '..', 'dir', 'file')


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
