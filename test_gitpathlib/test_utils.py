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
