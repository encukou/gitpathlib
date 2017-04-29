import os
import tempfile

import yaml
import pygit2

def make_repo(path, description, bare=True):
    repo = pygit2.init_repository(path, bare=bare)
    parents = []
    for revision in description:
        tree = make_tree(repo, revision['tree'])
        signature = pygit2.Signature('Test', 'test@noreply.invalid', time=0, offset=0)
        commit = repo.create_commit(
            'refs/heads/master',
            signature, signature,
            'Initial commit',
            tree,
            parents,
        )
        parents = [commit]

def make_tree(repo, description):
    builder = repo.TreeBuilder()
    for name, value in description.items():
        if isinstance(value, str):
            item = repo.create_blob(value)
            attr = pygit2.GIT_FILEMODE_BLOB
        elif isinstance(value, list):
            if value[0] == 'link':
                item = repo.create_blob(value[1])
                attr = pygit2.GIT_FILEMODE_LINK
            elif value[0] == 'binary':
                item = repo.create_blob(bytes(value[1]))
                attr = pygit2.GIT_FILEMODE_BLOB
            elif value[0] == 'executable':
                item = repo.create_blob(value[1])
                attr = pygit2.GIT_FILEMODE_BLOB_EXECUTABLE
            else:
                raise ValueError(value[0])
        else:
            item = make_tree(repo, value)
            attr = pygit2.GIT_FILEMODE_TREE
        builder.insert(name, item, attr)
    return builder.write()



def setup_doctests():
    previous_wd = os.getcwd()
    temp_dir = tempfile.TemporaryDirectory()
    os.chdir(temp_dir.name)

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
    make_repo('path/to/repo', contents, bare=False)
    make_repo('repo', contents, bare=False)
    make_repo('cloned_repo', contents, bare=False)

    contents = yaml.safe_load("""
        - tree:
            dir:
                file: |
                    Here are the contents of a file
            symlink-to-dir: [link, dir]
    """)
    make_repo('slrepo', contents, bare=False)

    contents = yaml.safe_load("""
        - tree:
            .gitignore: __pycache__/
            README: bla bla
            LICENSE: ⚖
            setup.py: import setuptools
            project:
                __init__.py: __all__ = ...
                util.py: import six
                tests:
                    test_foo.py: import pytest
                    test_bar.py: import pytest
    """)
    make_repo('project', contents, bare=False)

    contents = yaml.safe_load("""
        - tree:
            file1: same content
            file2: same content
            different_file: different content
    """)
    make_repo('dupes', contents, bare=False)

    def cleanup():
        temp_dir
        os.chdir(previous_wd)

    return cleanup
