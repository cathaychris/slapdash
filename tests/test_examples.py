'''Smoke tests that the bundled examples can be loaded and turned into a data model.'''
import inspect
import runpy

import pytest

import slapdash
from slapdash.examples import examples, get_examples


def test_list_examples(capsys):
    from slapdash.examples import list_examples
    list_examples()
    out = capsys.readouterr().out
    assert '- hello_world' in out
    assert '- client_example' in out


@pytest.mark.parametrize('name', [n for n in get_examples() if n != 'client_example'])
def test_example(name, tmp_path, monkeypatch):
    if name == 'metadata_example':
        pytest.importorskip('matplotlib')
    if name == 'dac_example':
        pytest.importorskip('tiqi_ad5371')
    monkeypatch.chdir(tmp_path)
    namespace = runpy.run_path(str(examples / f'{name}.py'), run_name='slapdash_example')
    classes = [obj for obj in namespace.values()
               if inspect.isclass(obj) and obj.__module__ == 'slapdash_example']
    assert classes
    for cls in classes:
        try:
            interface = cls()
        except TypeError:  # requires arguments
            continue
        if isinstance(interface, Exception):
            continue
        model = slapdash.Model(interface)
        model.serialize()
