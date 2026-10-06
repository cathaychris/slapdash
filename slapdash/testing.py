import threading
import socket
import time
from contextlib import closing
import asyncio
from .main import run, request_shutdown


class create_server:
    '''Run a slapdash server in a background thread, for use in tests.

    ```python
    with create_server(MyInterface()) as server:
        client = slapdash.Client(port=server.port)
    ```

    If no `port` is given, a free port is chosen. Entering the context waits until the
    web server accepts connections.'''

    def __init__(self, interface, port: int = None, startup_timeout: float = 10, **kwargs):
        self.port = get_random_port() if port is None else port
        kwargs.setdefault('host', '127.0.0.1')
        self._wait_for_web = kwargs.get('enable_web', True)
        self._startup_timeout = startup_timeout
        self.__loop = asyncio.new_event_loop()
        self.__thread = threading.Thread(
            target=run, args=(interface,), kwargs={'loop': self.__loop, 'port': self.port, **kwargs}, daemon=True)

    def __enter__(self):
        self.__thread.start()
        if self._wait_for_web:
            self._wait_until_listening()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.__thread.is_alive():
            try:
                request_shutdown(self.__loop)
            except (KeyError, RuntimeError):  # server not set up yet, or loop already closed
                pass
        self.__thread.join(timeout=10)

    def _wait_until_listening(self):
        deadline = time.monotonic() + self._startup_timeout
        while time.monotonic() < deadline:
            if not self.__thread.is_alive():
                raise RuntimeError('slapdash server thread exited during startup')
            try:
                with socket.create_connection(('127.0.0.1', self.port), timeout=0.1):
                    return
            except OSError:
                time.sleep(0.02)
        raise TimeoutError(f'slapdash server did not start listening on port {self.port}')


def get_random_port():
    # https://stackoverflow.com/a/45690594
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(('localhost', 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]
