Git Paths
=========

.. module:: gitpathlib

.. testsetup::

    import os
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

.. autoclass:: GitPath(repository_path, ref='HEAD', *segments)

General properties
------------------

Git paths are immutable and hashable.






.. _pathlib: https://docs.python.org/3/library/pathlib.html
