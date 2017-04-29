import pytest

from gitpathlib import util


def test_reify():
    memo = []

    class C:
        @util.reify
        def reified(self):
            memo.append('called')
            return 123

    c = C()
    assert memo == []
    assert c.reified == 123
    assert memo == ['called']
    assert c.reified == 123
    assert memo == ['called']
    del c.reified
    assert memo == ['called']
    assert c.reified == 123
    assert memo == ['called', 'called']
    c.reified = 321
    assert c.reified == 321
    assert memo == ['called', 'called']


def test_backend_cache():
    memo = []

    class Obj:
        pass

    class C:
        @util.backend_cache('attr_name')
        def get_attr(self, inst):
            memo.append('called')
            return 123

    obj = Obj()
    c = C()
    assert memo == []
    assert not hasattr(obj, 'attr_name')

    assert c.get_attr(obj) == 123
    assert memo == ['called']
    assert obj.attr_name == 123

    assert c.get_attr(obj) == 123
    assert memo == ['called']

    del obj.attr_name
    assert memo == ['called']
    assert not hasattr(obj, 'attr_name')

    assert c.get_attr(obj) == 123
    assert obj.attr_name == 123
    assert memo == ['called', 'called']

    obj.attr_name = 321
    assert obj.attr_name == 321
    assert c.get_attr(obj) == 321
    assert memo == ['called', 'called']
