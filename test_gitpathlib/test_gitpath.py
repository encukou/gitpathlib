import tempfile

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
    path = str(tmpdir) + 'path/to/repo'
    testutil.make_repo(path, contents)
    return pygit2.Repository(path)


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
    assert path.parts == (testrepo.path, tree)


def test_parts(testrepo):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', 'dir', 'file')
    tree = testrepo.head.peel(pygit2.Tree).hex
    assert path.parts == (testrepo.path, tree, 'dir', 'file')


def test_parts_slash(testrepo):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', 'dir/file')
    tree = testrepo.head.peel(pygit2.Tree).hex
    assert path.parts == (testrepo.path, tree, 'dir', 'file')


def test_parts_slashdot(testrepo):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', 'dir/./file')
    tree = testrepo.head.peel(pygit2.Tree).hex
    assert path.parts == (testrepo.path, tree, 'dir', 'file')


def test_dotdot(testrepo):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', 'dir/../dir/file')
    tree = testrepo.head.peel(pygit2.Tree).hex
    assert path.parts == (testrepo.path, tree, 'dir', '..', 'dir', 'file')


def test_hash(testrepo):
    path1 = gitpathlib.GitPath(testrepo.path, 'HEAD')
    path2 = gitpathlib.GitPath(testrepo.path, 'master')
    assert hash(path1) == hash(path2)
