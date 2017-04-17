Git Paths
=========

.. module:: gitpathlib

.. testsetup::

    import pathlib

    from gitpathlib import testutil
    cleanup = testutil.setup_doctests()

.. testcleanup::

    cleanup()


.. autoclass:: GitPath(repository_path, ref='HEAD', *segments)


General properties
------------------

Git paths are immutable, hashable, comparable and orderable.
They are case-insensitive.

>>> GitPath('./repo') == GitPath('./repo')
True
>>> GitPath('./repo') == GitPath('./repo', 'HEAD', 'dir')
False


Paths with equivalent roots and same path segments are considered equivalent.
The :ref:`Root and Path equivalence <root-and-equivalence>` sections
explain this further.


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


Accessing individual parts
--------------------------

To access the individual “parts” (components) of a path, use the following
property:

.. autoattribute:: GitPath.parts


Methods and properties
----------------------

Git paths provide the following methods and properties:

.. autoattribute:: GitPath.drive
.. autoattribute:: GitPath.root
.. autoattribute:: GitPath.anchor
.. autoattribute:: GitPath.parents

.. attribute:: GitPath.parent

    The logical parent of the path.

    >>> p = GitPath('./repo', 'HEAD', 'dir', 'file')
    >>> p.parent
    gitpathlib.GitPath('.../repo/', '31b40fb...', 'dir')

    You cannot go past an anchor, or empty path:

    >>> p = GitPath('./repo')
    >>> p
    gitpathlib.GitPath('.../repo/', '31b40fb...')
    >>> p.parent
    gitpathlib.GitPath('.../repo/', '31b40fb...')

    .. note::

        This is a purely lexical operation, hence the following behavior:

        >>> p = GitPath('./repo', 'HEAD', 'dir', '..')
        >>> p
        gitpathlib.GitPath('.../repo/', '31b40fb...', 'dir', '..')
        >>> p.parent
        gitpathlib.GitPath('.../repo/', '31b40fb...', 'dir')

        If you want to walk an arbitrary filesystem path upwards, it is
        recommended to first call :meth:`GitPath.resolve` so as to resolve
        symlinks and eliminate ".." components.

.. attribute:: GitPath.name

    A string representing the final path component, excluding the drive and root, if any:

    >>> GitPath('./repo', 'HEAD', 'dir', 'file.txt').name
    'file.txt'

    The name of the path's root is empty:

    >>> GitPath('./repo', 'HEAD').name
    ''

.. autoattribute:: GitPath.suffix
.. autoattribute:: GitPath.suffixes
.. autoattribute:: GitPath.stem

.. .. automethod:: GitPath.joinpath
.. .. automethod:: GitPath.match
.. .. automethod:: GitPath.relative_to
.. .. automethod:: GitPath.with_name
.. .. automethod:: GitPath.with_suffix

Methods and properties that exist only for compatibility with :mod:`pathlib`
are listed in :ref:`unimplemented`.


.. _pathlib: https://docs.python.org/3/library/pathlib.html
