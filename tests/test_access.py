import slapdash
from slapdash.testing import create_server


class AccessCounter:
    def __init__(self):
        self._access_counter = 0

    @property
    def access_counter(self) -> int:
        self._access_counter += 1
        return self._access_counter


def test_access_counter():
    access_counter = AccessCounter()

    assert access_counter._access_counter == 0
    model = slapdash.Model(access_counter)
    assert access_counter._access_counter == 1
    assert model['access_counter'] == 2
    assert access_counter._access_counter == 2
    assert model['access_counter'] == 3
    assert access_counter._access_counter == 3


def test_access_props():
    access_counter = AccessCounter()

    assert access_counter._access_counter == 0
    model = slapdash.Model(access_counter)
    assert access_counter._access_counter == 1
    assert model.props('access_counter') is None
    assert access_counter._access_counter == 1


def test_access_server():
    '''properties are only read when their value is requested, e.g. not when inspecting the model'''
    access_server = AccessCounter()
    assert access_server._access_counter == 0
    with create_server(access_server) as server:
        assert access_server._access_counter == 1
        access_client = slapdash.Client('127.0.0.1', port=server.port)
        assert access_server._access_counter == 1
        assert access_client.access_counter == 2
        assert access_server._access_counter == 2
