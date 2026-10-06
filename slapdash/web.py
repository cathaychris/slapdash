import re
import os
import inspect
import asyncio
import socketio
import logging
from contextlib import asynccontextmanager
from typing import Tuple, List

from collections.abc import Sequence
from functools import reduce
import operator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from .model import Model
from .types import READONLY, BASE_TYPES
from .version import __version__


logger = logging.getLogger(__name__)


def web_api(
        data_model: Model,
        frontend=None,
        css=None,
        enable_CORS: bool = True,
        info: dict = None,
        *args, **kwargs):
    '''
    Automatically generate a set of REST endpoints for a FastAPI web interface
    '''
    info = {} if info is None else info

    # the socketio ASGI app, to notify clients when params update
    if enable_CORS:
        sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
    else:
        sio = socketio.AsyncServer(async_mode='asgi')

    data_model_emit = data_model.emit
    # the event loop serving the app, set on startup. Model changes can be triggered from
    # other threads (e.g. sync endpoints run in a threadpool, or user threads), so
    # notifications are always scheduled onto this loop.
    server_loop = None

    def emit(message):
        data_model_emit(message)

        async def _notify():
            await sio.emit('notify', {'data': message})

            # allow a user-supplied callback in the interface upon notification
            callback = kwargs.get('web_notify_callback')
            if callback:
                callback_method = getattr(data_model._interface, callback)
                callback_method(message)

        if server_loop is None or server_loop.is_closed():
            return  # server not started yet, so there is nobody to notify
        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None
        if running_loop is server_loop:
            server_loop.create_task(_notify())
        else:
            asyncio.run_coroutine_threadsafe(_notify(), server_loop)

    data_model.emit = emit

    # the REST FastAPI app
    rest_app = FastAPI()

    if enable_CORS:
        rest_app.add_middleware(
            CORSMiddleware,
            allow_credentials=True,
            allow_origins=['*'],
            allow_methods=['*'],
            allow_headers=['*'],
        )

    endpoints: List[str] = []

    # Routes use `response_model=None`: the annotations of the generated endpoints document
    # the API, but are not precise enough (e.g. for nested objects or mixed-type lists) to
    # validate responses against, as FastAPI otherwise does with return annotations.
    def add_endpoint(name):
        '''automatically create an endpoint based on the property name in the data model attributes'''
        url, args = format_url(name)
        if url not in endpoints:
            if props['type'] == 'method':
                # methods need to be POST, because they take arguments passed into the body
                (rest_app.post(url, response_model=None))(method_factory(data_model, name, args))
            else:
                (rest_app.get(url, response_model=None))(get_factory(data_model, name, args))
                if (READONLY not in props) and (not isinstance(props['type'], (dict))):
                    (rest_app.post(url, response_model=None))(set_factory(data_model, name, args))

            # keep a list of endpoints created to we don't generate the same one multiple times
            # for example for attributes which are lists of objects
            endpoints.append(url)

    @rest_app.get('/version', include_in_schema=False)
    # pylint: disable=unused-variable
    def _version() -> str:
        return __version__

    @rest_app.get('/name', include_in_schema=False)
    # pylint: disable=unused-variable
    def _name():
        return data_model.name

    @rest_app.get('/info', include_in_schema=False)
    # pylint: disable=unused-variable
    def _info():
        return info

    @rest_app.get('/get_props', include_in_schema=False)
    # pylint: disable=unused-variable
    def get_props(name: str = None):
        return data_model.props(name)

    @rest_app.get('/get_param', include_in_schema=False)
    # pylint: disable=unused-variable
    def get_param(name: str = None):
        # serializing makes sure that we get a current reading from the interface
        return data_model.serialize(data_model[name])

    for name, props in data_model.flat_props().items():
        if name in [r.path.replace(r'/', '') for r in rest_app.routes] + ['ws', 'docs']:
            logger.warning(f'The name `{name}` is reserved for slapdash, but has been used as a parameter in the model. Unexpected results may occur.')
        add_endpoint(name)

        if isinstance(props['type'], list):
            list_shape = get_shape(props['type'])
            add_endpoint(name + ''.join(['[]' for i in range(len(list_shape))]))

    # user css to add custom stylings to the frontend
    if css is not None:
        @rest_app.get('/custom.css', include_in_schema=False)
        # pylint: disable=unused-variable
        async def styles():
            return FileResponse(css)

    if frontend is None:
        parent_dir_path = os.path.dirname(os.path.realpath(__file__))
        frontend = os.path.join(parent_dir_path, 'frontend')
    # mount the front end on the root endpoint last for lowest routing priority
    rest_app.mount('/', StaticFiles(directory=frontend, html=True))

    @asynccontextmanager
    async def lifespan(_app):
        nonlocal server_loop
        server_loop = asyncio.get_running_loop()
        yield

    # the top level app
    app = FastAPI(lifespan=lifespan)
    # Finally, serve socket.io at /ws/socket.io in front of the REST app. This is done as a
    # middleware rather than a mount, as mounted apps see the full path in newer Starlette.
    app.mount('/', rest_app)
    app.add_middleware(SocketIOMiddleware, sio=sio, socketio_path='ws/socket.io')

    # make top level app docs point at rest_app
    app.openapi = get_custom_openapi(rest_app, name=data_model.name)

    def add_exception_handlers(_app: FastAPI):
        @_app.exception_handler(Exception)
        async def alerting_exception_handler(request: Request, exc: Exception):
            await sio.emit('notify', {'data': {'exception': str(exc), 'type': exc.__class__.__name__}})
            raise

        # errors from invalid input, e.g. an unknown enum value, are reported back to the
        # caller with their message instead of as a generic internal server error
        async def bad_request_handler(request: Request, exc: Exception):
            message = str(exc.args[0]) if len(exc.args) == 1 else str(exc)
            await sio.emit('notify', {'data': {'exception': message, 'type': exc.__class__.__name__}})
            return JSONResponse(status_code=400, content={'detail': f'{exc.__class__.__name__}: {message}'})

        for exc_class in (KeyError, ValueError, TypeError):
            _app.add_exception_handler(exc_class, bad_request_handler)

    # add_exception_handlers(app)
    add_exception_handlers(rest_app)
    app._rest_app = rest_app
    app._sio = sio

    return app


class SocketIOMiddleware:
    '''ASGI middleware serving a socket.io server at `socketio_path`, passing other requests on.'''

    def __init__(self, app, sio: socketio.AsyncServer, socketio_path: str):
        self._asgi = socketio.ASGIApp(sio, other_asgi_app=app, socketio_path=socketio_path)

    async def __call__(self, scope, receive, send):
        await self._asgi(scope, receive, send)


def format_url(name: str):
    '''
    Take an name in object hierarchy format and convert it to a url

    example:
    object.example[3].list[2]

    /object/example/{index1}/list/{index2}

    '''
    # look for instance of eg [123] in url and replace with {index}
    url, indexes = re.subn(r'\[\d*\]', r'/{index}', name)
    # then iterate through each instance of {index} and replace with {indexN}
    # where N is unique
    for i in range(indexes):
        url = re.sub(
            r'\{index\}', '{{index{}}}'.format(i), url, count=1)
    return '/' + url.replace('.', '/'), tuple('index{}'.format(i) for i in range(indexes))


def get_custom_openapi(app: FastAPI, name: str = None):
    def custom_openapi(*args):
        if app.openapi_schema:
            return app.openapi_schema
        openapi_schema = get_openapi(
            title="Slapdash Interface" + ('' if name is None else ': ' + name),
            version=__version__,
            description="REST API for Slapdash interface" + ('' if name is None else ' ' + name),
            routes=app.routes,
        )
        openapi_schema["info"]["x-logo"] = {
            "url": "https://fastapi.tiangolo.com/img/logo-margin/logo-teal.png"
        }
        app.openapi_schema = openapi_schema
        return app.openapi_schema
    return custom_openapi


def get_factory(model: Model, name: str, args: Tuple[str, ...] = ()):
    prop_name = name
    while prop_name.endswith('[]'):
        prop_name = prop_name[:-2]
    props = model.flat_props()[prop_name]

    if props['type'] == 'method':
        return model[name]

    try:
        if isinstance(props['type'], list):
            props_shape = get_shape(props['type'])
            base_type = access_deep_list(props['type'], [0 for r in range(len(props_shape))])
            value_type = nested_list_type(BASE_TYPES[base_type], depth=len(props_shape)-1)
        elif isinstance(props['type'], dict):
            value_type = str
        else:
            value_type = BASE_TYPES[props['type']]
    except (KeyError, TypeError):
        value_type = str

    # try:
    #     value_type = BASE_TYPES[props['type']]
    # except (KeyError, TypeError):
    #     value_type = str

    def _func(**kwargs):
        if len(kwargs) > 0:
            iname, indexes = re.subn(r'\[\d*\]', r'[index]', name)
            for i in range(indexes):
                iname = re.sub(
                    r'\[index\]', '[index{}]'.format(i), iname, count=1)
            for key, value in kwargs.items():
                iname = iname.replace(key, str(value))
            return model.serialize(model[iname])
        return model.serialize(model[name])
    _func.__name__ = name
    _func.__annotations__ = {'return': value_type}

    signature = inspect.signature(_func)
    signature = signature.replace(parameters=tuple(inspect.Parameter(
        name=name, kind=inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=int) for name in args))
    _func.__signature__ = signature
    return _func


def set_factory(model: Model, name: str, args: Tuple[str, ...] = ()):
    prop_name = name
    while prop_name.endswith('[]'):
        prop_name = prop_name[:-2]
    props = model.flat_props()[prop_name]

    try:
        if isinstance(props['type'], list):
            props_shape = get_shape(props['type'])
            base_type = access_deep_list(props['type'], [0 for r in range(len(props_shape))])
            if prop_name == name:
                value_type = nested_list_type(BASE_TYPES[base_type], depth=len(props_shape))
            else:
                value_type = BASE_TYPES[base_type]
        elif isinstance(props['type'], dict):
            value_type = str
        else:
            value_type = BASE_TYPES[props['type']]
    except (KeyError, TypeError):
        value_type = str

    if READONLY in props:
        raise AttributeError(
            'cannot create factory for {}, it is read only'.format(name))

    def _func(value, **kwargs):
        if len(kwargs) > 0:
            iname, indexes = re.subn(r'\[\d*\]', r'[index]', name)
            for i in range(indexes):
                iname = re.sub(
                    r'\[index\]', '[index{}]'.format(i), iname, count=1)
            for key, val in kwargs.items():
                iname = iname.replace(key, str(val))
            model[iname] = value
            model_value = model[iname]
        elif isinstance(props['type'], list):
            for index, item in enumerate(value):
                model[f'{name}[{index}]'] = item
            model_value = model[name]
        elif props['type'] == 'enum':
            model[name] = value
            model_value = model[name]
        else:
            model[name] = value
            model_value = model[name]
        return model.serialize(model_value)

    _func.__name__ = name
    _func.__annotations__ = {'value': value_type}

    signature = inspect.signature(_func)
    signature = signature.replace(parameters=(inspect.Parameter(
        name='value', kind=inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=value_type),) + tuple(inspect.Parameter(
            name=name, kind=inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=int) for name in args))
    _func.__signature__ = signature
    return _func


def method_factory(model: Model, name: str, path_args: Tuple[str, ...] = ()):

    def _func(**kwargs):
        iname, indexes = re.subn(r'\[\d*\]', r'[index]', name)
        for i in range(indexes):
            iname = re.sub(
                r'\[index\]', '[index{}]'.format(i), iname, count=1)

        for key in path_args:
            iname = iname.replace(key, str(kwargs[key]))
        method_args = {key: value for key,
                       value in kwargs.items() if key not in path_args}
        return model[iname](**method_args)

    _func.__name__ = model[name].__name__
    _func.__annotations__ = model[name].__annotations__

    # method_spec = inspect.getfullargspec(model[name])
    signature = inspect.signature(model[name])  # allow __wrapped__ properties to pass through

    path_params = tuple(
        inspect.Parameter(name=name,
                          kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                          annotation=int) for name in path_args)

    method_params = tuple(
        inspect.Parameter(name=name,
                          kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                          default=parameter.default,
                          annotation=parameter.annotation)
        for name, parameter in signature.parameters.items() if name != 'self')

    signature = signature.replace(parameters=path_params + method_params)
    _func.__signature__ = signature
    return _func

def get_shape(lst, shape=()):
    """
    returns the shape of nested lists similarly to numpy's shape.

    :param lst: the nested list
    :param shape: the shape up to the current recursion depth
    :return: the shape including the current depth
            (finally this will be the full depth)

    https://stackoverflow.com/questions/51960857/how-can-i-get-a-list-shape-without-using-numpy
    """

    if not isinstance(lst, Sequence) or isinstance(lst, str):
        # base case
        return shape

    # peek ahead and assure all lists in the next depth
    # have the same length (also critical for the dashboard!)
    if isinstance(lst[0], Sequence) and not isinstance(lst, str):
        length = len(lst[0])
        if not all(len(item) == length for item in lst):
            msg = 'not all lists have the same length'
            raise ValueError(msg)

    shape += (len(lst), )

    # recurse
    shape = get_shape(lst[0], shape)

    return shape

def access_deep_list(lst, indexes):
    return reduce(operator.getitem, indexes, lst)

def nested_list_type(base_type, depth: int=0):
    if depth <= 0:
        return base_type
    else:
        return nested_list_type(List[base_type], depth-1)
