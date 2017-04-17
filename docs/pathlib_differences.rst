Differences from pathlib
========================

Git paths are *not* filesystem paths, and some operations on them do not make
sense.
Here is a summary of differences between ``GitObject`` and
:class:`pathlib.Path`.

.. testsetup::

    import pathlib

    from gitpathlib import testutil
    cleanup = testutil.setup_doctests()

    from gitpathlib import GitPath

.. testcleanup::

    cleanup()


.. _root-and-equivalence:

The root
--------

Git paths are part of a *tree* inside a repository.
The repository and tree are selected by the *repository_path* and *rev*
arguments to GitPath.

>>> p = GitPath('./repo', 'HEAD', 'dir', 'file')
>>> p
gitpathlib.GitPath('.../repo/', '31b40fb...', 'dir', 'file')

The repository and tree are accessible in the :attr:`~GitPath.drive` and
:attr:`~GitPath.root` properties of ``GitPath``.
In ``pathlib``, these properties hold the Windows drive and root, respectively.

>>> p.drive
'.../repo/.git/'
>>> p.root
'31b40fbbe41b1bc46cb85acb1ccb89a3ab182e98'

The :attr:`~GitPath.anchor` property (the first part of :attr:`~GitPath.parts`
holds a concatenation of the repository and ``root``.
Unlike in ``pathlib``, the two are separated by a semicolon:

>>> p.anchor
'.../repo/.git/:31b40fbbe41b1bc46cb85acb1ccb89a3ab182e98'
>>> p.parts
('.../repo/.git/:31b40fb...', 'dir', 'file')

GitPath objects can only be absolute.
For relative paths within a repository, use ``pathlib.PurePosixPath``.


Path equivalence
----------------

For most path operations, the particular repository does not matter.
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
