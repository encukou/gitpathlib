gitpathlib
==========

A read-only implementation of Python's `pathlib`_ that works on Git trees.

.. _pathlib: https://docs.python.org/3/library/pathlib.html

Installation
------------

This library requires `pygit2`_, which can be hard to install.
You may need to get it installed before installing gitpathlib.


In a Python 3 `virtual environment`_, do::

    python -m pip install gitpathlib

To install an editable from a Git checkout::

    python -m pip install -e.

To install without a virtual envitonment, add the ``--user`` option.

.. _pygit2: http://www.pygit2.org/
.. _virtual environment: https://docs.python.org/3/library/venv.html


Basic Usage
-----------

A GitPath can be created from a path to a Git repository, and a commit
(or tree) in it::

    from gitpathlib import GitPath

    head = GitPath('path/to/git/repo', 'HEAD')

It can then be used as a ``Path`` would::

    path = head / 'dir' / 'file.txt'
    with path.open() as f:
        contents = f.read()

GitPath provides read-only access. Creating files, opening them in write
mode, etc. are not supported.


Development
-----------

You're welcome to join this project!

If you spot an issue, please report it at the `Issues page`_ on Github.

If you'd like to start changing the code or documentation, check out the code
locally using::

    git clone https://github.com/encukou/gitpathlib

If you're new to this, please read the `this guide`_ about collaborating
on Github-hosted projects like this one.

If that doesn't make sense, please `e-mail the author <encukou@gmail.com>`_
for clarification. I'd be happy to help you get started.

.. _Issues page: https://github.com/encukou/gitpathlib/issues
.. _this guide: https://guides.github.com/activities/contributing-to-open-source/


Changelog
---------

0.3 (2023-09-18)
................

Update to work with recent git & pygit2


0.2 (2017-04-29)
................

Implement the pathlib API


0.1 (2017-04-18)
................

Initial public version
