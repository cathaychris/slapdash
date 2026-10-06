import pytest
from enum import Enum, auto
import slapdash
from slapdash.client import RemoteError


class SomeRepr:
    def __repr__(self):
        return "I am a talking object!"


class Some:
    pass


class Color(Enum):
    RED = 'red'
    GREEN = 'green'
    BLUE = 'blue'


class Auto(Enum):
    A = auto()
    B = auto()
    C = auto()


class Mixed(Enum):
    value_int = 10
    value_int_alias = 10
    value_float = 1.65
    value_bool = True
    value_bool_alias = 1
    value_str = 'some string'
    value_class = Some
    value_instance = SomeRepr()
    value_bad_instance = Some()


class EnumPlugin:
    color = Color.GREEN
    _col = Color.GREEN

    @property
    def color_prop(self):
        return self._col

    @color_prop.setter
    def color_prop(self, value):
        self._col = value

    auto = Auto.A
    mix = Mixed.value_int


def test_enum_props():
    model = slapdash.Model(EnumPlugin())
    props = model.props()
    assert props['color']['type'] == 'enum'
    assert props['color']['enums'] == ['red', 'green', 'blue']
    assert props['color_prop']['enums'] == ['red', 'green', 'blue']
    assert props['auto']['enums'] == ['1', '2', '3']
    assert model.serialize()['color'] == 'green'


def test_enum_model_set():
    plugin = EnumPlugin()
    model = slapdash.Model(plugin)
    model['color'] = 'blue'
    assert plugin.color == Color.BLUE
    with pytest.raises(KeyError):
        model['color'] = 'BLUE'


def test_enum_names(serve):
    '''setting the prop with the enum name (instead of its value) fails'''
    plugin = EnumPlugin()
    client, _ = serve(plugin)
    with pytest.raises(RemoteError, match='KeyError|not in'):
        client.color = 'RED'
    assert plugin.color == Color.GREEN


def test_enum_values(serve):
    '''you can get/set the prop with the str version of its value'''
    plugin = EnumPlugin()
    client, _ = serve(plugin)

    client.color = 'red'
    assert plugin.color == Color.RED
    assert client.color == 'red'

    assert plugin.auto == Auto.A
    assert client.auto == '1'


def test_mixed_enum(serve):
    '''test improbable enum with mixed-type values'''
    plugin = EnumPlugin()
    client, _ = serve(plugin)

    client.mix = '1.65'
    # the plugin attribute is set with the true enum object
    assert plugin.mix == Mixed.value_float
    # the client returns str(enum.value)
    assert client.mix == '1.65'

    client.mix = '10'
    assert plugin.mix == Mixed.value_int
    assert plugin.mix == Mixed.value_int_alias  # this alias is OK
    assert client.mix == '10'

    client.mix = 'True'
    assert plugin.mix == Mixed.value_bool
    assert client.mix == 'True'

    client.mix = 'some string'
    assert plugin.mix == Mixed.value_str

    # this works, because str(Some) = "<class '__main__.Some'>" is reproducible
    client.mix = str(Some)
    assert plugin.mix == Mixed.value_class
    assert client.mix == f"<class '{__name__}.Some'>"

    # this works, because str(SomeRepr()) = "I am a talking object!" is reproducible
    client.mix = str(SomeRepr())
    assert plugin.mix == Mixed.value_instance
    assert client.mix == "I am a talking object!"

    # This is a nasty case... the object has a valid str representation like
    # '<__main__.Some object at 0x7f8f95c0d430>', so it is shown in the web interface,
    # but setting it requires knowing the id of the particular object in the Enum class
    with pytest.raises(RemoteError):
        client.mix = str(Some())

    with pytest.raises(RemoteError):
        client.mix = '1'  # boolean alias fails because it is "hidden" by True
