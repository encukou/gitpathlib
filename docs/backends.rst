GitPath backends
================

.. module:: gitpathlib

Interaction with Git repositories is done through “backends”:

.. autoclass:: gitpathlib.PygitBackend
.. autoclass:: gitpathlib.SubprocessBackend

All backends share the same API.


Path initialization methods
---------------------------

There are two path initialization methods:

.. automethod:: SubprocessBackend.init_root
.. automethod:: SubprocessBackend.init_child


Accessor methods
----------------

The rest of the backend methods provide information about objects in a Git
repository.

``gitpathlib`` provides some guarantees about when these accessor methods are
called; these are:

* An *existing* path is one that refers to an existing object in the repo.
* A *canonical* path has no ``'..'`` :attr:`~GitPath.parts`, and none of its
  :attr:`~GitPath.parents` refer to :meth:`symlinks <GitPath.is_symlink>`.
* A *resolved* path is *canonical*, and it does not refer to
  a :meth:`symlink <GitPath.is_symlink>`.

The accessor methods are:

.. automethod:: SubprocessBackend.hex
.. automethod:: SubprocessBackend.has_entry
.. automethod:: SubprocessBackend.listdir
.. automethod:: SubprocessBackend.get_type
.. automethod:: SubprocessBackend.read
.. automethod:: SubprocessBackend.get_blob_size
.. automethod:: SubprocessBackend.get_mode
