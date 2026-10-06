import asyncio
import json

import pytest

import slapdash
from slapdash.decorators import Saver


@slapdash.refresh('counter', 0.05)
class Refreshing:
    def __init__(self):
        self._counter = 0

    @property
    def counter(self) -> int:
        self._counter += 1
        return self._counter


def test_refresh_without_loop():
    '''`@refresh` can be applied without an event loop (raised on python 3.14 before)'''
    refreshing = Refreshing()
    assert refreshing.counter == 1
    assert len(refreshing._slapdash_startup) == 1


def test_refresh_emits(serve, notifications):
    '''the refreshed attribute is regularly re-read and pushed to web clients'''
    _, server = serve(Refreshing())
    receive = notifications(server.port)
    first = receive('counter')
    assert receive('counter') > first


def test_refresh_nested(serve, notifications):
    '''refresh tasks of sub-components are also started'''
    class Parent:
        def __init__(self):
            self.child = Refreshing()

    _, server = serve(Parent())
    receive = notifications(server.port)
    assert receive('child.counter') >= 1


def test_refresh_in_running_loop():
    async def main():
        refreshing = Refreshing()
        assert '_slapdash_startup' not in vars(refreshing)
        slapdash.Model(refreshing)
        await asyncio.sleep(0.2)
        return refreshing._counter
    # the refresh task reads the counter regularly
    assert asyncio.run(main()) > 2


def test_set_notification(serve, notifications):
    '''changes made through the REST API (handled in a worker thread) are pushed to web clients'''
    class Simple:
        value = 1

    client, server = serve(Simple())
    receive = notifications(server.port)
    client.value = 2
    assert receive('value') == 2


def test_trigger_update(serve, notifications):
    class Linked:
        _x = 1

        @property
        def x(self) -> int:
            return self._x

        @x.setter
        @slapdash.trigger_update('double')
        def x(self, value: int):
            self._x = value

        @property
        def double(self) -> int:
            return 2 * self._x

        @slapdash.trigger_update('double')
        def reset(self):
            self._x = 0

    client, server = serve(Linked())
    receive = notifications(server.port)
    client.x = 4
    assert receive('double') == 8
    client.reset()
    assert receive('double') == 0


def test_metadata_decorator():
    metadata = {'min': 0, 'max': 10, 'units': 'V'}

    class Interface:
        _v = 1

        @slapdash.metadata(metadata)
        @property
        def v(self) -> int:
            return self._v

        @slapdash.metadata({'displayName': 'Do it'})
        def method(self):
            return 1

    model = slapdash.Model(Interface())
    assert model.props()['v']['metadata'] == metadata
    assert model.props()['method']['metadata'] == {'displayName': 'Do it'}
    assert Interface().method() == 1


def test_create_dashboard_task():
    async def main():
        async def work():
            return 42
        task = slapdash.create_dashboard_task(work(), None)
        return await task
    assert asyncio.run(main()) == 42


class Sub:
    value = 0.0


class Saved:
    a_int = 0
    other = 0

    def __init__(self):
        self.array = [1, 2, 3]
        self.sub = Sub()


def make_saved(tmp_path, settings):
    path = tmp_path / 'settings.json'
    path.write_text(json.dumps(settings))
    return Saver(path)(Saved)(), path


def test_saver_saves_changes(tmp_path, serve):
    '''changes to saved settings are written back to the settings file'''
    interface, path = make_saved(tmp_path, {'a_int': 1, 'sub': {'value': 0.5}, 'array': [1, 2, 3]})
    client, _ = serve(interface)

    client.a_int = 7
    client.sub.value = 2.5
    client.array[1] = 5
    client.other = 3  # not part of the settings, so not saved

    assert json.loads(path.read_text()) == {'a_int': 7, 'sub': {'value': 2.5}, 'array': [1, 5, 3]}


def test_saver_index_keys(tmp_path):
    '''list items can be addressed by (string) index in the settings file'''
    interface, _ = make_saved(tmp_path, {'array': {'1': 9}})
    assert interface.array == [1, 9, 3]


def test_saver_unknown_settings(tmp_path, caplog):
    interface, _ = make_saved(tmp_path, {'missing': 1, 'array': {'7': 1}})
    assert interface.array == [1, 2, 3]
    assert 'The setting `missing` is not present' in caplog.text
    assert 'The setting `7` is not present' in caplog.text


def test_saver_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        Saver(tmp_path / 'nope.json')
