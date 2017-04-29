GitPath backends
================

.. module:: gitpathlib

Interaction with Git repositories is done through “backends”.
All backends share the same API.

.. autoclass:: gitpathlib.PygitBackend

    .. automethod:: PygitBackend.init_root
    .. automethod:: PygitBackend.init_child
    .. automethod:: PygitBackend.hex
    .. automethod:: PygitBackend.has_entry
    .. automethod:: PygitBackend.listdir
    .. automethod:: PygitBackend.get_type
    .. automethod:: PygitBackend.read
    .. automethod:: PygitBackend.get_size
    .. automethod:: PygitBackend.get_mode

.. autoclass:: gitpathlib.SubprocessBackend
