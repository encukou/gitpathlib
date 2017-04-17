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
    assert path.hex == testrepo.head.peel().hex


def test_parent(testrepo):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD^')
    assert path.hex == testrepo.head.peel().parents[0].hex


def test_components(testrepo):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', 'dir', 'file')
    assert path.hex == testrepo.revparse_single('HEAD:dir/file').hex


def test_parts_empty(testrepo):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD')
    assert path.parts == (testrepo.path, 'HEAD')


def test_parts(testrepo):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', 'dir', 'file')
    assert path.parts == (testrepo.path, 'HEAD', 'dir', 'file')


def test_parts_slash(testrepo):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', 'dir/file')
    assert path.parts == (testrepo.path, 'HEAD', 'dir', 'file')


def test_parts_slashdot(testrepo):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', 'dir/./file')
    assert path.parts == (testrepo.path, 'HEAD', 'dir', 'file')


def test_dotdot(testrepo):
    path = gitpathlib.GitPath(testrepo.path, 'HEAD', 'dir/../dir/file')
    assert path.parts == (testrepo.path, 'HEAD', 'dir', '..', 'dir', 'file')
