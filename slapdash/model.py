import inspect
import types
import itertools
import re
from typing import Any, Union
from enum import Enum

from .types import READONLY, BASE_TYPES
from .metadata import sanitize_metadata_entry


READONLY = 'readonly'
BASE_TYPES = {
    'str': str,
    'int': int,
    'float': float,
    'bool': bool,
    'enum': str
}


class ModelList:
    _interface = None
    _parent: Any = None
    _name: str = None
    _root: Any = None
    __index__: int = 0

    def __init__(self, interface, parent=None, name=''):
        if not parent:
            root = self._root
        else:
            root = parent._root

        try: # has a __data_model__ (not a vanilla list)
            interface.__data_model__ = self
        except AttributeError:
            interface = UserList(interface)
            interface.__data_model__ = self
            try:
                if type(parent._interface) == UserList:
                    parent._interface.__origsetitem__(int(name), interface)
                else:
                    parent._interface.__origsetattr__(name, interface)
            except AttributeError: # read-only
                pass

        # a sanity check that only works for arrays up to depth 2
        # try:
        #     obj = root._interface
        #     if parent:
        #         for pn in parent.parent_name.split('.')[:-1]:
        #             try:
        #                 obj = getattr(obj, pn)
        #             except AttributeError:
        #                 obj = obj[int(pn)]
        #     try:
        #         obj = getattr(obj, name)
        #     except AttributeError:
        #         lastobj = obj
        #         obj = obj[int(name)]
        #     if id(interface) != id(obj):
        #         raise ValueError(f'Memory objects for {parent.parent_name+name} not the same: passed interface {id(interface)} (type {type(interface)}) =/= descended object {id(obj)} (type {type(obj)})')
        # except AttributeError:
        #     pass

        if type(parent) == ModelList:
            self._interface = UserList(parent._interface[int(name)])
        else:
            self._interface = interface
        self._parent = parent
        self._name = name
        self._root = root

        self._attach_emit()
        if parent is not None:
            self.__index__ = parent.__index__

    def __getitem__(self, index):
        if isinstance(index, str):
            index = int(index)
        return Model(self._interface[index], parent=self, name=str(index))

    def __setitem__(self, index, value):
        parent = self._parent
        if isinstance(index, str):
            index = int(index)
        obj = self[index]
        if isinstance(obj, Model):
            for subkey, subval in value.items():
                obj[subkey] = subval
        elif isinstance(obj, ModelList):
            for index, item in enumerate(value):
                obj[index] = item
        elif isinstance(obj, ModelEnum):
            new_enum = obj._get_from_name(value)
            self._interface[index] = new_enum
        elif isinstance(parent, ModelList):
            # for deep lists, we need to set from the outermost list
            args = [int(self._name)]
            while isinstance(parent._parent, ModelList):
                args.append(int(parent._name))
                parent = parent._parent
            superparent = parent

            pif = superparent._interface
            for arg in args[::-1]:
                pif = pif[arg]
            pif[index] = value
        else:
            self._interface[index] = value

    # this is a somewhat strange __contains__
    # it checks if an index is value, not if a value is
    # contained in the list
    def __contains__(self, index):
        if isinstance(index, str):
            index = int(index)
        if isinstance(index, int):
            return index >= 0 and index < len(self._interface)
        return False

    @property
    def parent_name(self):
        if self._parent is None:
            # None during debugging during model buildup
            if self._name == '' or self._name is None:
                return ''
            else:
                return self._name + '.'
        else:
            return self._parent.parent_name + self._name + '.'

    def _attach_emit(self):
        # overload the __setitem__ method of the passed in interface
        # to provide notifications via emit(),
        # where setting now happens prior to notification
        if self._interface.__class__.__setitem__.__name__ != '__notifysetitem__':
            temp_setitem = self._interface.__class__.__setitem__
            self._interface.__class__.__origsetitem__ = temp_setitem

            def __notifysetitem__(interface, index, value):
                temp_setitem(interface, index, value)
                if hasattr(interface, '__data_model__'):
                    parent_name = interface.__data_model__.parent_name
                    serialized_value = Model.serialize(self, Model(value))
                    interface.__data_model__.emit({'name': f'{parent_name}{index}', 'value': serialized_value})

            self._interface.__class__.__setitem__ = __notifysetitem__

    def serialize(self):
        return [Model.serialize(self, Model(item)) for item in self._interface]

    def emit(self, message):
        if self._parent is not None:
            self._parent.emit(message)


class UserList(list):
    '''A subclassing of `list` to allow custom `__setitem__` behavior
    and to contain a `__data_model__` attribute.'''
    def __init__(self, __list):
        super().__init__(__list)


class ModelEnum:
    _interface = None
    _parent: Any = None
    _name: str = None

    def __init__(self, interface, parent=None, name=''):
        interface.__data_model__ = self
        self._interface = interface
        self._parent = parent
        self._name = name
        self._value_map = {str(item.value): item for item in type(interface)}
        self._member_map = {v: k for k, v in self._value_map.items()}
        self._enums = list(self._value_map.keys())

    def serialize(self):
        # used to get the prop from a client
        # p = client.enum_prop
        return self._member_map[self._interface]

    def _get_from_name(self, name):
        # used to set the prop from a client
        # client.enum_prop = name
        # Raises a KeyError if name is not a valid enum
        try:
            return self._value_map[name]
        except KeyError:
            raise KeyError(f"Key '{name}' is not in {[v.value for v in self._value_map.values()]}")

    def emit(self, message):
        if self._parent is not None:
            self._parent.emit(message)


class Model:
    '''Creates a data model to access an arbitrary python object

    When initialized, this explores the passed in object 'interface' and creates a hierachical dictionary of that objects attributes.
    '''

    _interface: Any = None
    _root: Any = None
    _parent: Any = None
    _name: str = None
    _props: dict = {}
    _name_dict: dict = {}
    _lock: bool = False
    __index__: int = 0

    def __new__(cls, interface, parent=None, name=None):
        if isinstance(interface, tuple(BASE_TYPES.values())) and not isinstance(interface, Enum):
            return interface
        elif inspect.ismethod(interface):
            return interface
        elif isinstance(interface, (list, tuple)):
            try: # don't render streaming data arrays as ModelLists
                if parent._interface._metadata[name]['isDataStream']: # deprecated metadata key
                    return interface
            except (KeyError, AttributeError):
                pass
            try: # preferred metadata key
                if parent._interface._metadata[name]['renderAs'] == 'graph':
                    return interface
            except (KeyError, AttributeError):
                pass
            return ModelList(interface, parent, name)
        elif isinstance(interface, Enum):
            return ModelEnum(interface, parent, name)
        return super(Model, cls).__new__(cls)

    def __init__(self, interface, parent=None, name='', *args, **kwargs):
        if type(interface) == type(None):
            raise AttributeError(f'Interface `{name}` (parent `{parent.name}`) is None and cannot be built. Check that returned data types are consistent.')
        interface.__data_model__ = self
        self._interface = interface
        self._parent = parent
        self._name = name
        self._props = {}
        if not self._parent:
            self._root = self
        else:
            self._root = self._parent._root

        if parent is not None:
            self.__index__ = parent.__index__
        self._build_attributes(interface)
        if parent is not None:
            parent.__index__ = self.__index__

        self._name_dict = {value['index']: name for name,
                           value in self.flat_props().items()}
        self._lock = True

    def __repr__(self):
        return str(self.serialize())

    def __contains__(self, key):
        return key in self._props.keys()

    def __setitem__(self, key, value):
         # e.g. for calls to arr[index1][index2] (n times, n>=1)
        if key not in self._props.keys():
            self._set(key, value)
        else:
            obj = self[key]
            if isinstance(obj, Model):
                for subkey, subval in value.items():
                    obj[subkey] = subval
            elif isinstance(obj, ModelList):
                for index, item in enumerate(value):
                    obj[index] = item
            elif isinstance(obj, ModelEnum):
                # The problem here is that the object (an Enum instance)
                # cannot coincide with its serialized version (a string)
                new_enum = obj._get_from_name(value)
                self._interface.__setattr__(key, new_enum)
            else:
                self._interface.__setattr__(key, value)

    def __getitem__(self, key):
        if key is None or key == '':
            return self
        if key not in self._props.keys():
            return self._get(key)
        return Model(self._interface.__getattribute__(key), parent=self, name=key)

    @property
    def _index(self):
        _index = self.__index__
        self.__index__ += 1
        return _index

    @property
    def name(self) -> str:
        if inspect.ismethod(self._interface.__repr__):
            return str(self._interface)
        else:
            return self._interface.__class__.__name__

    @property
    def parent_name(self):
        if self._parent is None:
            if self._name == '':
                return ''
            else:
                return self._name + '.'
        else:
            return self._parent.parent_name + self._name + '.'

    def props(self, name: Union[str, int] = None):
        if name is None:
            return self._props
        if hasattr(self[self._lookup(name)], '_props'):
            return self[self._lookup(name)]._props
        else:
            return None

    def flat_props(self, name: Union[str, int] = None):
        return self._flatten_props(self.props(name))

    def _flatten_props(self, props, parent=''):
        flat_props = {}
        for name, prop in props.items():
            if isinstance(prop['type'], dict):
                flat_props = {**flat_props, **
                              self._flatten_props(prop['type'], f'{parent}{name}.')}
            elif isinstance(prop['type'], (list, tuple)):
                for index, item in enumerate(prop['type']):
                    if isinstance(item, dict):
                        flat_props = {
                            **flat_props, **self._flatten_props(item, f'{parent}{name}[{index}].')}
            flat_props[parent + name] = prop
        return flat_props

    def flatten(self, parent=''):
        flat = {}
        for key in self._props.keys():
            value = self[key]
            if isinstance(value, Model):
                flat = {**flat, **value.flatten(f'{parent}{key}.')}
            elif isinstance(value, ModelList):
                for index, item in enumerate(value):
                    if isinstance(item, Model):
                        flat = {
                            **flat,
                            **item.flatten(f'{parent}{key}[{index}].')}
            else:
                flat[parent + key] = value
        return flat

    def serialize(self, interface=None, props=None):
        if interface is not None:
            if isinstance(interface, (Model, ModelList, ModelEnum)):
                return interface.serialize()
            elif inspect.ismethod(interface):
                return f"{props['name']}({', '.join((name for name, annotation in props['args']))})"
            else:
                return interface
        else:
            # when we serialize, make sure to grab a current value from the interface
            return {key: self.serialize(self[key], self._props[key]) for key in self._props.keys()}

    def _build_attributes(self, interface):
        if self._lock:
            raise RuntimeError(
                "cannot access _build_attributes after __init__")

        # overload the __setattr__ method of the passed in interface
        # to provide notifications via emit(),
        # where setting now happens prior to notification
        if interface.__class__.__setattr__.__name__ != '__notifysetattr__':
            temp_setattr = interface.__class__.__setattr__
            interface.__class__.__origsetattr__ = temp_setattr

            def __notifysetattr__(interface, name, value):
                temp_setattr(interface, name, value)
                if not name.startswith('_') and hasattr(interface, '__data_model__'):
                    parent_name = interface.__data_model__.parent_name
                    try: # I think some different cases here can depend on how dynamically the model is initialized
                        serialized_value = interface.__data_model__.serialize(interface.__data_model__[name])
                    except KeyError:
                        serialized_value = self.serialize(self[name])
                    interface.__data_model__.emit({'name': parent_name + name, 'value': serialized_value})

            try:
                interface.__class__.__setattr__ = __notifysetattr__
            except TypeError:
                print('can not overload function __setattr__')

        cls_dict = (cls.__dict__ for cls in type(
            interface).__mro__ if cls is not object)
        members = itertools.chain(interface.__dict__, *cls_dict)
        for name in members:
            if not name.startswith('_'):
                # include decorator metadata prior to Model build-up in case it changes outcome
                extra_metadata = {}
                try:
                    name_class = getattr(interface.__class__, name)
                    if hasattr(name_class, '_object_metadata'): # metadata added by decorator
                        extra_metadata = name_class._object_metadata
                    elif type(name_class) == property:
                        if hasattr(name_class.fget, '_object_metadata'):
                            extra_metadata = getattr(name_class.fget, '_object_metadata')
                    if extra_metadata:
                        if hasattr(interface, '_metadata'):
                            try:
                                interface._metadata[name].update(extra_metadata)
                            except KeyError:
                                interface._metadata[name] = extra_metadata
                        else:
                            interface._metadata = {name: extra_metadata}
                # variables created in __init__ will not be in __class__, but cannot be decorated anyway
                except AttributeError:
                    pass
                
                value = interface.__getattribute__(name)
                obj = Model(value, parent=self, name=name)
                self._props[name] = {
                    'name': name,
                    'type': self._get_type(obj),
                    **self._get_properties(interface, name),
                    'index': self._index
                }

                if hasattr(interface, '_metadata') and name in interface._metadata:
                    _metadata = sanitize_metadata_entry(interface, name, interface._metadata[name], prop=obj)
                    self._props[name]['metadata'] = _metadata[name]

    def _get_type(self, interface):
        if isinstance(interface, tuple(BASE_TYPES.values())):
            return type(interface).__name__
        elif inspect.ismethod(interface):
            return type(interface).__name__
        elif isinstance(interface, ModelList):
            return [self._get_type(item) for item in interface]
        elif isinstance(interface, ModelEnum):
            return 'enum'
        elif isinstance(interface, Model):
            return interface._props
        elif isinstance(interface, (list, tuple)):
            return 'array'
        else:
            raise TypeError(f'{interface} is an unknown type')

    def _get_properties(self, obj, name):
        '''finds optional properties of an objects attributes

        if an attribute is a @property without a setter, then it is is given the prop 'readonly'

        if an attribute is a @property or a function with a defined __doc__ string then it is given the prop doc
        '''
        props = {}
        # CM: I suspect that the loop is at this point equivalent to
        # attr = getattr(obj, name)
        for cls in type(obj).__mro__:
            # print(name, issubclass(cls, type(self)))
            if cls is not object:
                if name in cls.__dict__: # a hard-coded class attribute
                    attr = cls.__dict__[name]
                    if isinstance(attr, property):
                        if attr.fset is None:
                            props[READONLY] = True
                    if isinstance(attr, types.FunctionType):
                        props[READONLY] = True
                        props['args'] = tuple(((key.name, key.annotation.__name__ if key.annotation is not inspect._empty else None)
                                               for key in inspect.signature(attr).parameters.values()))[1:]
                    if isinstance(attr, (property, types.FunctionType)):
                        if attr.__doc__ is not None:
                            props['doc'] = attr.__doc__
                    elif not isinstance(attr, tuple(list(BASE_TYPES.values()) + [UserList, Enum, tuple, list])):
                        if attr.__doc__ is not None:
                            props['doc'] = attr.__doc__
                    if isinstance(attr, Enum):
                        props['enums'] = ModelEnum(attr)._enums
                    if isinstance(attr, property) and isinstance(attr.fget(obj), Enum):
                        props['enums'] = ModelEnum(attr.fget(obj))._enums
                else: # an attribute initialized during instantiation
                    attr = getattr(obj, name)
                    if isinstance(attr, property):
                        if attr.fset is None:
                            props[READONLY] = True
                    if isinstance(attr, types.FunctionType):
                        props[READONLY] = True
                        props['args'] = tuple(((key.name, key.annotation.__name__ if key.annotation is not inspect._empty else None)
                                               for key in inspect.signature(attr).parameters.values()))[1:]
                    if isinstance(attr, (property, types.FunctionType)):
                        if attr.__doc__ is not None:
                            props['doc'] = attr.__doc__
                    elif not isinstance(attr, tuple(list(BASE_TYPES.values()) + [UserList, Enum, tuple, list])):
                        if attr.__doc__ is not None:
                            props['doc'] = attr.__doc__
                    if isinstance(attr, Enum):
                        props['enums'] = ModelEnum(attr)._enums
                    if isinstance(attr, property) and isinstance(attr.fget(obj), Enum):
                        props['enums'] = ModelEnum(attr.fget(obj))._enums
        return props

    def _lookup(self, value: Union[str, int]) -> str:
        if isinstance(value, int):
            return self._name_dict[value]
        elif isinstance(value, str):
            return value
        raise TypeError('lookup value must be str or int')

    def _get(self, name: Union[str, int]):
        return self._value_by_name(self._lookup(name))

    def _set(self, name: Union[str, int], value: Any):
        self._value_by_name(self._lookup(name), value)

    def _value_by_name(self, name: str, value: Any = None):
        obj = self
        attributes = re.sub(r'\[(\d+)\]', r'.\1', name).split('.')
        for attribute in attributes[:-1]:
            obj = obj[attribute]

        if attributes[-1] not in obj:
            raise KeyError(name)
        if value is None:
            return obj[attributes[-1]]
        else:
            obj[attributes[-1]] = value

    def emit(self, message):
        if self._parent is not None:
            self._parent.emit(message)
