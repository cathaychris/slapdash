import contextlib

import pytest
import socketio

import slapdash
from slapdash.testing import create_server


@pytest.fixture
def serve():
    '''Start a slapdash server for an interface and return a connected `Client`.

    `client, server = serve(interface)`; the server is stopped at teardown.'''
    with contextlib.ExitStack() as stack:
        def _serve(interface, **kwargs):
            server = stack.enter_context(create_server(interface, **kwargs))
            return slapdash.Client('127.0.0.1', port=server.port, timeout=5), server
        yield _serve


@pytest.fixture
def notifications():
    '''Connect a socket.io client to a server port and collect its `notify` events.

    `receive(name)` waits for the next notification about `name` and returns its value.'''
    clients = []

    def _connect(port):
        sio = socketio.SimpleClient()
        sio.connect(f'http://127.0.0.1:{port}', socketio_path='/ws/socket.io',
                    transports=['websocket'], wait_timeout=5)
        clients.append(sio)

        def receive(name, timeout=5):
            while True:
                event, data = sio.receive(timeout=timeout)
                if event == 'notify' and data['data'].get('name') == name:
                    return data['data']['value']
        return receive

    yield _connect
    for sio in clients:
        sio.disconnect()
