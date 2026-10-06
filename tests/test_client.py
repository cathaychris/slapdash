'''End-to-end tests of `slapdash.Client` against the built-in web server.'''
import inspect
from enum import Enum, auto

import pytest

import slapdash
from slapdash.client import RemoteError


class Simple:
    a = 0.0
    b = 1
    c = "test"
    d = False
    mylist = [0, 1]


def test_client(serve):
    simple, _ = serve(Simple())

    assert simple.a == 0.0
    assert simple.b == 1
    assert simple.c == 'test'
    assert simple.d is False
    assert simple.mylist == [0, 1]

    simple.a = 1.0
    assert simple.a == 1.0
    simple.b = 2
    assert simple.b == 2
    simple.c = 'new'
    assert simple.c == 'new'
    simple.d = True
    assert simple.d is True
    simple.mylist[1] = 5
    assert simple.mylist == [0, 5]
    assert simple.mylist[1] == 5

    with pytest.raises(AttributeError):
        simple.e  # noqa: B018


def test_multiple_clients(serve):
    interface = Simple()
    simple, server = serve(interface)
    simple2 = slapdash.Client('127.0.0.1', port=server.port)

    simple.a = 1.5
    assert simple2.a == 1.5
    simple2.c = 'newer'
    assert simple.c == 'newer'
    assert interface.c == 'newer'


def test_invalid_value_raises(serve):
    simple, _ = serve(Simple())
    with pytest.raises(RemoteError):
        simple.b = 'not an int'
    assert simple.b == 1


class ReadOnly:
    _value = 3

    @property
    def value(self) -> int:
        return self._value


def test_readonly(serve):
    client, _ = serve(ReadOnly())
    assert client.value == 3
    with pytest.raises(AttributeError, match='read only'):
        client.value = 4


class Functions:
    def no_arg(self):
        return 0

    def one_arg(self, x: int) -> int:
        return x

    def two_arg(self, x: float, y: float) -> float:
        return x + y

    def no_return(self, x: int) -> None:
        return None

    def no_annotate(self, x, y):
        return x + y


@pytest.mark.parametrize('name', ['no_arg', 'one_arg', 'two_arg', 'no_return', 'no_annotate'])
def test_method_signatures(serve, name):
    '''Methods on the client mirror the signatures of the interface'''
    client, _ = serve(Functions())
    expected = inspect.signature(getattr(Functions(), name)).parameters
    actual = inspect.signature(getattr(client, name)).parameters
    assert list(actual) == list(expected)
    for param_name, param in expected.items():
        assert actual[param_name].annotation == param.annotation


def test_method_calls(serve):
    client, _ = serve(Functions())
    assert client.no_arg() == 0
    assert client.one_arg(4) == 4
    assert client.two_arg(1.5, y=2.0) == 3.5
    assert client.no_return(1) is None
    with pytest.raises(RemoteError):
        client.one_arg('not an int')


class Channel:
    value: float = 0.0

    def double(self) -> float:
        return 2 * self.value


class Device:
    def __init__(self):
        self.channels = [Channel() for i in range(3)]
        self.main = Channel()


def test_nested(serve):
    device = Device()
    client, _ = serve(device)

    client.main.value = 1.5
    assert device.main.value == 1.5
    assert client.main.double() == 3.0

    client.channels[1].value = 2.5
    assert device.channels[1].value == 2.5
    assert client.channels[1].value == 2.5
    assert client.channels[1].double() == 5.0
    assert device.channels[0].value == 0.0


class Color(Enum):
    RED = 'red'
    GREEN = 'green'
    BLUE = 'blue'


class Auto(Enum):
    A = auto()
    B = auto()


class EnumInterface:
    color = Color.GREEN
    auto = Auto.A
    _col = Color.GREEN

    @property
    def color_prop(self):
        return self._col

    @color_prop.setter
    def color_prop(self, value):
        self._col = value


def test_enum(serve):
    '''enums are get/set with the str version of their value'''
    interface = EnumInterface()
    client, _ = serve(interface)

    assert client.color == 'green'
    client.color = 'red'
    assert interface.color == Color.RED
    assert client.color == 'red'

    client.color_prop = 'blue'
    assert interface.color_prop == Color.BLUE
    assert client.color_prop == 'blue'

    assert client.auto == '1'
    client.auto = '2'
    assert interface.auto == Auto.B


def test_enum_invalid_value(serve):
    '''setting an enum by member name (instead of value) fails'''
    interface = EnumInterface()
    client, _ = serve(interface)
    with pytest.raises(RemoteError):
        client.color = 'RED'
    assert interface.color == Color.GREEN


class Simple1:
    a = 0.0


class Simple2:
    def __repr__(self):
        return 'SimpleClass'
    a = 0.0


@slapdash.refresh('a')
class Simple3:
    a = 0.0


@slapdash.refresh('a')
class Simple4:
    def __repr__(self):
        return 'SimpleClass4'
    a = 0.0


@pytest.mark.parametrize('cls, name', [
    (Simple1, 'Simple1'), (Simple2, 'SimpleClass'), (Simple3, 'Simple3'), (Simple4, 'SimpleClass4')])
def test_repr(serve, cls, name):
    '''the client class is named after the interface (or its repr)'''
    client, _ = serve(cls())
    assert client.__class__.__name__ == name


def test_simple_client(serve):
    interface = Simple()
    _, server = serve(interface)
    client = slapdash.client.SimpleClient('127.0.0.1', port=server.port)
    assert client.get('b') == 1
    client.set('b', 3)
    assert interface.b == 3
    client.set('mylist[0]', 7)
    assert interface.mylist == [7, 1]


@pytest.mark.parametrize('hostname', ['localhost', 'http://localhost', 'http://localhost:{port}'])
def test_hostname_formats(serve, hostname):
    _, server = serve(Simple())
    client = slapdash.Client(hostname=hostname.format(port=server.port), port=server.port)
    assert client.b == 1
