import requests
import re
import inspect
import urllib.parse
from .types import BASE_TYPES
from .version import __version__, __major__, __minor__
from typing import Any


def name_to_endpoint(name: str) -> str:
    '''Convert a model name like `a.b[0].c` to its REST endpoint path `a/b/0/c`.'''
    return re.sub(r"\]", "", re.sub(r"\.|\[", "/", name))


class RemoteError(Exception):
    '''An error reported by a slapdash server.'''


def raise_for_response(resp: requests.Response):
    '''Raise an informative exception for a failed request to a slapdash server.'''
    if resp.ok:
        return
    if resp.status_code >= 500:
        raise RemoteError("Server Error: {}".format(resp.text))
    try:
        detail = resp.json()["detail"]
    except (ValueError, KeyError, TypeError):
        detail = resp.text
    if isinstance(detail, list) and detail and isinstance(detail[0], dict):
        detail = detail[0].get("msg", detail[0])
    if resp.status_code == 405:
        detail = f"{resp.url} is read only"
    raise RemoteError(detail)


class ComClient:
    pass


class RequestClient(ComClient):
    _url: str
    _timeout: int

    def __init__(self, hostname: str = "localhost", port: int = 8000, timeout: int = 1):
        if not (hostname.startswith("http://") or hostname.startswith("https://")):
            hostname = "http://" + hostname
        o = urllib.parse.urlparse(hostname)
        if o.port is not None:
            port = o.port
        self._url = f"{o.scheme}://{o.hostname}:{port}/"
        self._timeout = timeout
        self._session = requests.Session()

    def __call__(self, method_name: str, **kwargs):
        req = self._session.get(
            self._url + method_name, timeout=self._timeout, params=kwargs
        )
        try:
            return req.json()
        except requests.exceptions.JSONDecodeError:
            raise RemoteError("Server Error: {}".format(req.text))

    def get_props(self, name: str):
        return self("get_props", name=name)

    def get_param(self, name: str):
        return self("get_param", name=name)

    def set_param(self, name: str, value):
        params = {"value": value}
        resp = self._session.post(self._url + name_to_endpoint(name), timeout=self._timeout, params=params)
        raise_for_response(resp)

    def remote_call(self, method_name: str, **kwargs):
        resp = self._session.post(
            self._url + name_to_endpoint(method_name),
            timeout=self._timeout,
            params=kwargs,
        )
        raise_for_response(resp)
        return resp.json()


class CustomClient:
    _client: ComClient = None

    def __init__(self, client: ComClient):
        self._client = client


class ParamArray(list):
    def __init__(self, client: ComClient, call_name: str, *args, **kwargs):
        self._client = client
        self._name = call_name
        super().__init__(*args, **kwargs)

    def __getitem__(self, index: int):
        name = f"{self._name}[{index}]"
        item = self._client.get_param(name)
        if isinstance(item, dict):
            return make_class(self._client, name, parent=name + ".")
        else:
            return item

    def __setitem__(self, index: int, value):
        name = f"{self._name}[{index}]"
        self._client.set_param(name, value)


class Param:
    def __init__(self, call_name: str, readonly: bool = False, **kwargs):
        self._name = call_name
        self._readonly = readonly

    def __get__(self, obj, owner):
        interface = make_class(obj._client, name=self._name, parent=self._name + ".")

        return interface

    def __set__(self, obj, value):
        if not self._readonly:
            obj._client.set_param(name=self._name, value=value)
        else:
            raise AttributeError(f"{self._name} is read only")


def make_function(client: ComClient, name: str, args: list, doc: str = None, **kwargs):
    def _func(self, *args, **kwargs):
        keywords = inspect.getfullargspec(_func).args[1:]
        kw = {key: val for key, val in zip(keywords, args)}
        kwargs = {**kw, **kwargs}
        kwargs = {
            k: v for k, v in sorted(kwargs.items(), key=lambda i: keywords.index(i[0]))
        }
        return client.remote_call(name, **kwargs)

    _func.__name__ = name
    _func.__doc__ = doc

    signature = inspect.signature(_func)
    parameters = []
    for arg_name, arg_type in [("self", None), *args]:
        try:
            annotation = BASE_TYPES[arg_type]
        except (KeyError, TypeError):
            annotation = inspect.Parameter.empty

        parameters.append(
            inspect.Parameter(
                name=arg_name,
                annotation=annotation,
                kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
            )
        )
    signature = signature.replace(parameters=parameters)
    _func.__signature__ = signature
    return _func


def make_class(client: ComClient, name: str, props=None, parent="", **kwargs):
    customClientClass = type(name, (CustomClient,), {})
    if props is None:
        props = client.get_props(name=name)
        if props is None:
            param = client.get_param(name=name)
            if isinstance(param, (list, tuple)):
                return ParamArray(client, name, param)
            else:
                return param

    for prop_name, prop in props.items():
        if prop["type"] == "method":
            method_name = prop["name"]
            prop["name"] = parent + prop["name"]
            setattr(customClientClass, method_name, make_function(client, **prop))

        else:
            setattr(
                customClientClass,
                prop["name"],
                Param(call_name=parent + prop_name, **prop),
            )

    def __repr__(self):
        return f"<{name}>\n  - " + "\n  - ".join(props.keys())

    setattr(customClientClass, "__repr__", __repr__)

    return customClientClass(client)


class Client:
    def __new__(
        cls,
        hostname: str = "localhost",
        port: int = 8000,
        timeout=1,
        client_type: ComClient = None,
        *args,
        **kwargs,
    ):
        if client_type is not None:
            client = client_type(
                hostname=hostname, port=port, timeout=timeout, *args, **kwargs
            )
        else:
            client = RequestClient(hostname=hostname, port=port, timeout=timeout)

        version = client("version")
        if version != __version__:
            major, minor = [int(v) for v in version.split(".")[:2]]
            if major != __major__:
                raise RuntimeWarning(
                    f"version mismatch: server is using slapdash version `{version}`, but client is using version `{__version__}`"
                )
            elif minor != __minor__:
                print(
                    f"version mismatch: server is using slapdash version `{version}`, but client is using version `{__version__}`"
                )
        name = client("name")
        props = client("get_props")

        return make_class(client, name, props)


class SimpleRequestClient:
    """Allows direct communication without error-checking or convenience attributes,
    through `set(name, value)` and `get(name)` methods."""

    _url: str
    _timeout: int

    def __init__(self, hostname: str = "localhost", port: int = 8000, timeout: int = 1):
        if not (hostname.startswith("http://") or hostname.startswith("https://")):
            hostname = "http://" + hostname
        o = urllib.parse.urlparse(hostname)
        if o.port is not None:
            port = o.port
        self._url = f"{o.scheme}://{o.hostname}:{port}/"
        self._timeout = timeout

    def get(self, obj):
        url = self._url
        timeout = self._timeout
        return object.__getattribute__(self, "__call__")(
            url + "get_param?name=" + obj, timeout
        )

    def set(self, name: str, value: Any) -> None:
        params = {"value": value}
        resp = requests.post(self._url + name_to_endpoint(name), timeout=self._timeout, params=params)
        raise_for_response(resp)

    def __call__(self, method_name: str, timeout=1.0, **kwargs):
        req = requests.get(method_name, timeout=timeout, params=kwargs)
        try:
            return req.json()
        except requests.exceptions.JSONDecodeError:
            raise RemoteError("Server Error: {}".format(req.text))


class SimpleClient:
    def __new__(
        cls, hostname: str = "localhost", port: int = 8000, timeout: float = 1.0
    ):
        client = SimpleRequestClient(hostname=hostname, port=port, timeout=timeout)

        return client
