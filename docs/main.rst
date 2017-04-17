Git Paths
=========

.. module:: gitpathlib

.. testsetup::

    import os
    import pathlib

    import tempfile
    import yaml

    from gitpathlib import testutil

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
    testutil.make_repo('path/to/repo', contents, bare=False)
    testutil.make_repo('repo', contents, bare=False)
    testutil.make_repo('cloned_repo', contents, bare=False)

.. autoclass:: GitPath(repository_path, ref='HEAD', *segments)


General properties
------------------

Git paths are immutable, hashable, comparable and orderable.
They are case-insensitive.

>>> GitPath('./repo') == GitPath('./repo')
True
>>> GitPath('./repo') == GitPath('./repo', 'HEAD', 'dir')
False


Comparison details
..................

``GitPath`` objects are rooted in a particular tree selected by the
*repository_path* and *rev* arguments to the constructor.
How the tree is selected doesn't matter for the comarison -- only
the identity of the tree matters.
For example, if *master* is the current branch, ``rev=HEAD`` and ``rev=master``
are interchangeable:

>>> GitPath('./repo', rev='HEAD') == GitPath('./repo', rev='master')
True

In fact, even the repository does not influence comparisons.
``GitPath`` objects from different repositories can compare equal,
if they are rooted in the same tree:

>>> a = GitPath('./repo')
>>> a
gitpathlib.GitPath('.../repo/', '31b40fb...')
>>> b = GitPath('./cloned_repo')
>>> b
gitpathlib.GitPath('.../cloned_repo/', '31b40fb...')
>>> a == b
True

On the other hand, paths rooted in different trees are considered different,
even if they ultimately refer to the same object.

>>> GitPath('./repo', 'HEAD:dir') == GitPath('./repo', 'HEAD', 'dir')
False


Operators
---------

The slash operator helps create child paths, similarly to :func:`os.path.join`.

>>> p = GitPath('./repo')
>>> p / 'dir'
gitpathlib.GitPath('.../repo/', '31b40fb...', 'dir')
>>> p / 'dir' / 'file'
gitpathlib.GitPath('.../repo/', '31b40fb...', 'dir', 'file')
>>> p / 'dir/file'
gitpathlib.GitPath('.../repo/', '31b40fb...', 'dir', 'file')

>>> q = pathlib.PurePath('dir/file')
>>> p / q
gitpathlib.GitPath('.../repo/', '31b40fb...', 'dir', 'file')

Unlike :class:`Pathlib.Path` objects, ``GitPath`` objects cannot be passed
to functions like :func:`open`, and their string representation is
not useful for programmatic use.


.. _pathlib: https://docs.python.org/3/library/pathlib.html
