import uvicorn
import asyncio
import signal

from .model import Model
from .web import web_api
from .version import __version__
from .decorators import start_pending_tasks

# shutdown callbacks of running servers, keyed by event loop (see `request_shutdown`)
_shutdown_handlers = {}


def request_shutdown(loop):
    '''Gracefully stop the slapdash server running on `loop`. Safe to call from any thread.'''
    loop.call_soon_threadsafe(_shutdown_handlers[loop])


def run(interface,
        host: str = '0.0.0.0',
        port: int = 8000,
        enable_web: bool = True,
        servers: list = (),
        loop=None,
        web_settings: dict = None,
        *args, **kwargs
        ):
    '''
    Start an instance of the Slapdash server

    Args:
        host (str='0.0.0.0'): The host to use for the dashboard server. Defaults to '0.0.0.0', which binds to all interfaces

        port (int=8000): The port for the web REST interface of the server. Defaults to 8000

        enable_web (bool=True): Disable this in case you will only use your own add-in servers.

        servers (Server | list=()): Any number of server factories that produce functions that spawn servers, which will share the data model produced from `interface`.
            These functions should accept arguments (data_model, info) and will be passed any additional (*args, **kwargs) supplied to `run()`,
            where `info` will include the data model name, slapdash version, web port, and any supplied `web_settings`.
            They should return a server instance with the method `serve()` that mirrors that of `uvicorn.Server`.

        loop (None): Specify an event loop to use to run all servers, in case you would prefer that the dashboard not create its own.

    Optional kwargs used in the web interface:

        frontend (str=None): An absolute path for a folder containing files to serve on the root '/' endpoint of the web interface. Defaults to None, in which case a built in frontend is used.

        css (str=None): An absolute path for a custom css file to override the styles of the built-in web gui.

        enable_CORS (bool=True): Uninhibits cross-origin resource sharing (CORS). CORS is useful for development. Defaults to True.

        web_notify_callback (str=None): The name of a callback function in `interface` that will be called when notifications are triggered via the web interface.

        web_settings (dict={}): Any settings you would like to make available at the `/info` endpoint of the REST API.
    '''

    data_model = Model(interface)
    info = {
        'name': data_model.name,
        'version': __version__,
        'web_port': port,
        'web_settings': {} if web_settings is None else web_settings,
        **kwargs
    }
    if loop is None:
        loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # if wrapped with @Saver, attach DashboardSavingInterface's saving callback to all model changes
    if 'DashboardSavingInterface' in [c.__name__ for c in type(data_model._interface).__mro__]:
        data_model_emit = data_model.emit

        def emit(message):
            data_model_emit(message)
            data_model._interface._trigger_save(message)
        data_model.emit = emit

    if callable(servers):  # accept single server factory or list thereof
        servers = [servers]
    addin_servers = [server_factory(data_model, info, *args, **kwargs) for server_factory in servers]
    info['addin_servers'] = []
    for server in addin_servers:
        server_info = {'name': server.__module__ + '.' + server.__class__.__name__}
        if hasattr(server, '_host') and hasattr(server, '_port'):  # not present for all add-in servers
            server_info.update({'host': server._host, 'port': server._port})
        info['addin_servers'].append(server_info)

    all_servers = list(addin_servers)
    if enable_web:
        wapi = web_api(data_model=data_model, info=info, *args, **kwargs)
        all_servers.append(uvicorn.Server(uvicorn.Config(wapi, host=host, port=port)))

    server_tasks = []
    for server in all_servers:
        # overwrite the signal handlers of uvicorn<0.29 (and alike), otherwise it will
        # bogart SIGINT and SIGTERM, which makes it impossible to escape out of
        try:
            server.install_signal_handlers = lambda: None
        except AttributeError:
            pass
        server_tasks.append(loop.create_task(server.serve()))

    # start background tasks registered before the loop existed, e.g. by `@refresh`
    start_pending_tasks(data_model.iter_interfaces(), loop)

    async def stop_loop():
        # ask uvicorn-like servers to exit cleanly, so that they release their sockets
        for server in all_servers:
            if hasattr(server, 'should_exit'):
                server.should_exit = True
        if server_tasks:
            await asyncio.wait(server_tasks, timeout=5)
        current = asyncio.current_task()
        for task in asyncio.all_tasks(loop):
            if task is not current:
                task.cancel()
        loop.stop()
        print('Slapdash server shutting down')

    stopping = False

    def shutdown():
        nonlocal stopping
        if not stopping:
            stopping = True
            loop.create_task(stop_loop())

    _shutdown_handlers[loop] = shutdown

    def custom_exception_handler(loop, context):
        # if any background task creates an unhandled exception, shut down the entire loop
        # it's possible we don't want to do this, maybe make this optional in the future
        loop.default_exception_handler(context)

        # here we exclude most kinds of exceptions from triggering this kind of shutdown
        exc = context.get('exception')
        if exc is None:
            return  # e.g. warnings about unclosed resources
        if type(exc) not in [RuntimeError, KeyboardInterrupt, asyncio.CancelledError]:
            if enable_web:
                async def emit_exception():
                    await wapi._sio.emit('notify', {'data': {'exception': str(exc),
                                                    'type': exc.__class__.__name__}})
                loop.create_task(emit_exception())
        else:
            shutdown()

    loop.set_exception_handler(custom_exception_handler)

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, shutdown)
        except (NotImplementedError, RuntimeError):
            pass

    print('Starting Slapdash server')
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        _shutdown_handlers.pop(loop, None)
        _cancel_all_tasks(loop)
        loop.close()


def _cancel_all_tasks(loop):
    '''Cancel leftover tasks and let them finish, like `asyncio.run` does on exit.'''
    tasks = [task for task in asyncio.all_tasks(loop) if not task.done()]
    for task in tasks:
        task.cancel()
    if tasks:
        loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
    loop.run_until_complete(loop.shutdown_asyncgens())
