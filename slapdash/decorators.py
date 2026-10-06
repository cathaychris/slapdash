import json
import asyncio
import contextvars
import types
from typing import Any
import logging
import functools
from enum import Enum
from .types import BASE_TYPES

logger = logging.getLogger(__name__)

# set while `@Saver` reads values to save, so that `trigger_update` does not emit
_saving_settings = contextvars.ContextVar('slapdash_saving_settings', default=False)

_STARTUP_ATTR = '_slapdash_startup'


def on_dashboard_start(obj, coro_factory):
    '''Run the coroutine produced by `coro_factory()` as a task on the dashboard event loop.

    If called from within a running event loop the task starts right away; otherwise it is
    started by `slapdash.run` once its event loop is set up.'''
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        obj.__dict__.setdefault(_STARTUP_ATTR, []).append(coro_factory)
    else:
        create_dashboard_task(coro_factory(), loop)


def start_pending_tasks(interfaces, loop):
    '''Start tasks registered with `on_dashboard_start` on any of `interfaces`.'''
    for interface in interfaces:
        for coro_factory in getattr(interface, '__dict__', {}).pop(_STARTUP_ATTR, []):
            create_dashboard_task(coro_factory(), loop)


def refresh(attr: str, delay: int = 1, delay_attr: str = None):
    '''
    Decorate an attribute with `@refresh` to constantly update it in the GUI
    by having update notifications emitted at a regular interval (an interval
    that can be sourced by another attribute, `delay_attr`, if desired.)
    `attr` and `delay_attr` can be dot-separated to represent parameters
    in subclasses, like `subclass.parameter`.
    '''
    def resolve_itemattr(obj, attr):
        '''Generalize attrgetter to accept items as well, so as to resolve
        e.g. `class.subclass[0].subsubclass[3].attribute`.'''
        for name in attr.split("."):
            try:
                obj = obj[name]
            except TypeError:
                try:
                    obj = getattr(obj, name)
                except AttributeError:
                    subattr, subkey = name.split('[')[0], int(name.split('[')[1][:-1])
                    obj = getattr(obj, subattr)[subkey]
        return obj

    def itemattrgetter(attr):
        """
        Combo itemgetter and attrgetter
        """
        def g(obj):
            return resolve_itemattr(obj, attr)
        return g

    def decorator(cls):
        class Wrapped(cls):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)

                async def start_counter():
                    _delay = delay
                    try:
                        delay_getter = itemattrgetter(delay_attr)
                    except (TypeError, AttributeError):
                        delay_getter = None
                    prev = None
                    while True:
                        if hasattr(self, '__data_model__'):
                            model = self.__data_model__
                            parent_name = model.parent_name

                            value = model[attr]
                            if hasattr(value, 'serialize'):
                                value = value.serialize()
                            if value != prev and prev is not None:
                                self.__data_model__.emit(
                                    {'name': parent_name + attr, 'value': value})
                            prev = value

                            try:
                                # _delay = self.__getattribute__(delay_attr)
                                _delay = delay_getter(self)
                            except (TypeError, AttributeError):
                                pass
                        await asyncio.sleep(_delay)

                on_dashboard_start(self, start_counter)
        for attr_name in ('__module__', '__name__', '__qualname__', '__doc__'):
            setattr(Wrapped, attr_name, getattr(cls, attr_name))
        return Wrapped
    return decorator

def metadata(metadata: dict):

    def decorator(fn):

        if isinstance(fn, types.FunctionType):
            def executor(self, *args, **kwargs):
                return_value = fn(self, *args, **kwargs)
                return return_value
            executor._object_metadata = metadata
            functools.update_wrapper(executor, fn)
            return executor
        if isinstance(fn, property):
            if fn.fset is None:
                @functools.wraps(fn.fget)
                def getter(interface, *args, **kwargs):
                    return fn.fget(interface, *args, **kwargs)
                getter._object_metadata = metadata
                p = property(fget=getter, fset=fn.fset, fdel=fn.fdel)
            else:
                def setter(interface, *args, **kwargs):
                    fn.fset(interface, *args, **kwargs)
                fn.fget._object_metadata = metadata
                p = property(fget=fn.fget, fset=setter, fdel=fn.fdel)
            return p
        logger.error(
            f"Was not able to decorate {fn.__name__} with metadata because it was not a function or property")
        return fn

    return decorator

def trigger_update(target_attr: str):
    '''
    Applied to a model function or function decorated as a property.
    Create a callback triggered on the update of the decorated function,
    which triggers an update notification on the target attribute `target_attr`.
    When applied to a property (either before or after property decoration),
    triggers an update when the property is gotten (when applied to `@property` getters)
    or when the property is set (when applied to `@myproperty.setter` setters).
    Can also be applied to both (separately, by decorating setter and getter).
    Does not emit an update as part of a function call from `@Saver`.
    '''
    def decorator(fn):

        def emit_target_update(interface):
            '''Emits a message with the status of a secondary target.'''
            if not _saving_settings.get():
                if hasattr(interface, '__data_model__'):
                    source_model = interface.__data_model__
                    parent_name = source_model.parent_name

                    if not target_attr.startswith('_') and hasattr(interface, '__data_model__'):
                        try:
                            target_value = source_model[target_attr]
                            if hasattr(target_value, 'serialize'):
                                target_value = target_value.serialize()
                            interface.__data_model__.emit(
                                {'name': parent_name + target_attr, 'value': target_value})
                        except KeyError:  # source_model is {} if decorating a getter and before `emit` has been attached
                            try:
                                logger.info(f"""Was not able to emit a linked update in `{fn.__name__}` with `trigger_update`
                                because {fn.__name__} does not have an `emit` function; this can happen if `trigger_update` is
                                linked to a getter function and called before the data model is constructed.""")
                            except AttributeError: # property object does not have __name__
                                try:
                                    logger.info(f"""Was not able to emit a linked update in `{fn.fget.__name__}` with `trigger_update`
                                    because {fn.fget.__name__} does not have an `emit` function; this can happen if `trigger_update` is
                                    linked to a getter function and called before the data model is constructed.""")
                                except AttributeError:
                                    logger.info(f"""Was not able to emit a linked update in `{fn}` with `trigger_update`
                                    because {fn} does not have an `emit` function; this can happen if `trigger_update` is
                                    linked to a getter function and called before the data model is constructed.
                                    Furthermore, the __name__ attribute of {fn} was not accessible.""")


        if isinstance(fn, types.FunctionType):
            def executor(self, *args, **kwargs):
                '''An executing wrapper that emits a message for a secondary target.'''
                return_value = fn(self, *args, **kwargs)
                # `self` is the calling interface class
                emit_target_update(self)
                return return_value
            functools.update_wrapper(executor, fn)
            return executor
        if isinstance(fn, property):
            # for properties a getter is defined first, and thus fset will be None, so
            # this is how we check whether the getter or setter was decorated
            if fn.fset is None:
                def getter(interface, *args, **kwargs):
                    '''A property getting wrapper that emits a message for a secondary target.'''
                    emit_target_update(interface)
                    return fn.fget(interface, *args, **kwargs)
                p = property(fget=getter, fset=fn.fset, fdel=fn.fdel)
            else:
                def setter(interface, *args, **kwargs):
                    '''A property setting wrapper that emits a message for a secondary target.'''
                    fn.fset(interface, *args, **kwargs)
                    emit_target_update(interface)
                p = property(fget=fn.fget, fset=setter, fdel=fn.fdel)
            return p
        logger.error(
            f"Was not able to decorate {fn.__name__} with `trigger_update` because it was not a function or property")
        return fn

    return decorator

def saver_original_class_name(cls):
    '''Use in code where a DashboardSavingInterface is known to be the wrapper.
    This will extract the name of the class that is wrapped by the Saver.'''
    mro = cls.__class__.__mro__
    name = cls.__class__.__name__
    if 'DashboardSavingInterface' in [m.__name__ for m in mro]:
        try:
            name = mro[1].__name__
        except IndexError:
            pass
    return name

def _get_attr_or_item(this, k):
    '''Get attribute `k` of `this`, falling back to item access (e.g. list indices).'''
    try:
        return getattr(this, k)
    except (AttributeError, TypeError):  # TypeError: non-str attribute name
        if isinstance(this, (list, tuple)) and isinstance(k, str) and k.isdigit():
            k = int(k)  # JSON keys are always strings
        return this[k]

def saver_enum_check(this, k, v):
    '''If the class parameter is an enum, replace the saved string
    setting to the enum member before setting it, thus preserving the enum type.
    Will raise an error if the string is not a member of the enum class.'''
    try:
        subject = _get_attr_or_item(this, k)
    except (KeyError, IndexError, TypeError):  # missing, or object not subscriptable
        subject = None
    if isinstance(subject, Enum):
        return subject.__class__(v)
    else:
        return v

def saver_type_check(this, k, v) -> None:
    '''Check that loaded setting types match class parameter types'''
    subject = _get_attr_or_item(this, k)
    ktype = type(subject)
    if (ktype in BASE_TYPES.values()) and (ktype != type(v)):  # base value type does not match
        raise TypeError(
            f'Cannot override class parameter `{saver_original_class_name(this)}.{k}` (type `{ktype.__name__}`) from settings file using type `{type(v).__name__}`')
    elif isinstance(v, list) and v and isinstance(subject, (list, tuple)) and subject:  # for arrays, check that first value types match
        ktype = type(subject[0])
        if type(v[0]) in BASE_TYPES.values() and (not ktype == type(v[0])):
            raise TypeError(
                f'Cannot override class parameter `{saver_original_class_name(this)}.{k}` (array member type `{ktype.__name__}`) from settings file using array member type `{type(v[0]).__name__}`')

def setattr_or_setitem(this, k, v):
    '''Check if we are setting a list attribute and set
    item-by-item instead of potentially
    overriding subclassed `list` types.'''
    if type(v) is list:
        target = _get_attr_or_item(this, k)
        for ii, vi in enumerate(v):
            target[ii] = vi
    elif isinstance(k, int):
        this[k] = v
    else:
        setattr(this, k, v)

class Saver:
    '''A decorator class to be used to generate saving classes.
    Use as
    ```python
    @Saver('settings.json')
    class Interface:
        ...
    ```
    where settings are loaded immediately upon decoration.
    Settings are then applied AFTER instantiation of the wrapped class.
    If there are actions in the wrapped class that must be run upon
    instantiation, but after settings are applied, run them manually, i.e.
    ```python
    interface = Interface()
    interface.launch_missiles()
    ```
    The loaded settings and the settings path are available to the wrapped class
    as `_settings` and `_settings_path`, respectively.
    '''

    def __init__(self, settings_path):
        '''settings is the decorator argument'''
        self._settings_path = settings_path
        try:
            with open(settings_path, 'r') as f:
                self._settings = json.load(f)
        except FileNotFoundError as e:
            logger.error(f"Missing settings file: {settings_path}")
            raise e
        except json.decoder.JSONDecodeError as e:
            logger.error(f"Invalid settings file: {settings_path}")
            raise e

    def __call__(parent, cls):
        '''cls is what the decorator acts on'''
        class DashboardSavingInterface(cls):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._settings = parent._settings
                self._settings_path = parent._settings_path
                self._apply_settings()

            def _save_setting(self, setting_name):
                '''Programmatically save settings of supplied keywords, using prototype settings.'''
                def nested_set(dic, keys, value):
                    '''Build up a dictionary of saved values, save to JSON'''
                    for key in keys[:-1]:
                        dic = dic.setdefault(key, {})
                    dic[keys[-1]] = value

                def walk_get(object, setting_names):
                    '''Walks through the levels of the Python object to check at each level whether
                    the object is an integer-labeled list, and needs to be treated as an item instead
                    of an attribute. Returns the attribute value for saving in the JSON schema.'''
                    try:
                        next_object = getattr(object, setting_names[0])
                    except AttributeError:
                        next_object = object[int(setting_names[0])]
                    try:
                        return walk_get(next_object, setting_names[1:])
                    except IndexError:
                        if Enum in next_object.__class__.__mro__:
                            return next_object.value
                        else:
                            return next_object  # this is our desired value
                token = _saving_settings.set(True)
                try:
                    value = walk_get(self, setting_name)
                finally:
                    _saving_settings.reset(token)
                nested_set(self._settings, setting_name, value)
                with open(self._settings_path, 'w') as f:
                    json.dump(self._settings, f, indent=4)

            def _apply_settings(self):
                '''Programmatically set supplied settings.'''
                def walk_apply(settings, this, parent: Any = None):
                    '''Walks through JSON settings finds the Python object attributes to set.
                    Accounts for the possibility of lists/arrays appearing, which are integer-keyed,
                    compared to string keys in JSON.
                    In case of conflict, class types will take precedence over JSON types.'''
                    for k, v in settings.items():
                        try:  # v is dict type; if this succeeds, we can go lower
                            v.items()
                            try:
                                walk_apply(v, getattr(this, k), parent=this)
                            except Exception as e:  # noqa with JSON dictionary using key (str) to refer to array index (int)
                                try:
                                    walk_apply(v, this[int(k)], parent=this)
                                except ValueError:  # the first error was legitimate and we should have listened
                                    logger.warning(
                                        f'Could not load attribute `{k}`: {e}')
                                    raise e
                        except AttributeError:  # v not dict type; no lower levels
                            v = saver_enum_check(this, k, v)
                            try:
                                if hasattr(this, k):
                                    logger.info(
                                        f'Will set {saver_original_class_name(this)}.{k} from {getattr(this, k)} to {v}')
                                    try:
                                        saver_type_check(this, k, v)
                                        # can't set attribute = tried to set a READONLY
                                        setattr_or_setitem(this, k, v)
                                    except TypeError:
                                        raise
                                elif isinstance(this, list) and k.isdigit() and int(k) < len(this):  # JSON uses str keys for array indices
                                    k = int(k)
                                    logger.info(
                                        f'Will set {saver_original_class_name(this)}[{k}] from {this[k]} to {v}')
                                    try:
                                        saver_type_check(this, k, v)
                                        setattr_or_setitem(this, k, v)
                                    except TypeError:
                                        raise
                                elif hasattr(this, 'keys'):
                                    # this arises e.g. when you have a dictionary, which always has string keys in json,
                                    # applied to a dictionary with non-string keys in python. solution: set whole dictionary
                                    # OR it can happen with a subclass
                                    equivalent_keys = [
                                        key for key in this.keys() if str(key) == k]
                                    for key in equivalent_keys:
                                        try:
                                            v = saver_enum_check(this, key, v)
                                            saver_type_check(this, key, v)
                                            this[key] = v
                                        except TypeError:
                                            raise
                                    if not equivalent_keys:  # step back and set parent
                                        logger.info(
                                            f'Setting {saver_original_class_name(this)} to {settings}')
                                        this = settings
                                else:
                                    raise ValueError(k)
                            except ValueError:
                                logger.warning(
                                    f'The setting `{k}` is not present in the model and cannot be set.')
                walk_apply(self._settings, self)
                logger.info('Done loading settings')

            def _trigger_save(self, message):
                def iter_leafs(d, keys=()):
                    '''Get settings trees like (['optosigma', 'channels', '0', 'step_sizes', 'backward'], 2890)'''
                    for key, val in d.items():
                        if isinstance(val, dict):
                            yield from iter_leafs(val, [*keys, key])
                        else:
                            yield [*keys, key], val
                valid_settings = list(iter_leafs(self._settings))
                try:
                    valid_settings_names = list(zip(*valid_settings))[0]
                except IndexError:
                    logger.warning(
                        f"Empty settings file: {self._settings_path}")
                    valid_settings_names = []

                updated_settings_name = message['name'].split('.')

                if (updated_settings_name in valid_settings_names):
                    self._save_setting(updated_settings_name)
                elif (updated_settings_name[:-1] in valid_settings_names):
                    self._save_setting(updated_settings_name[:-1])
        return DashboardSavingInterface

def _get_result_and_raise_exceptions(task: asyncio.Task) -> None:
    '''Retrieves `task.result()` to reraise unaccessed exceptions.'''
    try:
        task.result()
    except asyncio.CancelledError:
        pass  # Task cancellation should not be logged as an error.

def create_dashboard_task(coro, loop=None) -> asyncio.Task:
    '''Wraps a task normally called with `create_task` in asyncio
    to properly "catch" exceptions that would normally not get
    retrieved, and thus would be prone to shut down the whole process.
    Supply the same arguments as you would to `loop.create_task(coro)`.'''
    if not loop:
        loop = asyncio.get_running_loop()
    task = loop.create_task(coro)
    task.add_done_callback(_get_result_and_raise_exceptions)
    return task

def run_dashboard_coroutine_threadsafe(coro, loop) -> asyncio.Future:
    '''Wraps a task normally called with `asyncio.run_coroutine_threadsafe`
    to properly "catch" exceptions that would normally not get
    retrieved, and thus would be prone to shut down the whole process.'''
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    future.add_done_callback(_get_result_and_raise_exceptions)
    return future
