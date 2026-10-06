from .types import BASE_TYPES
import inspect
import logging
logger = logging.getLogger(__name__)

# 'type' describes what the property may be
# 'prop_type' describes what the property may be applied TO

METADATA_SPECS = {
    'min': {
        'type': ['int', 'float'],
        'prop_type': ['int', 'float'],
        'description': "Minimum value settable in the user interface"
    },
    'max': {
        'type': ['int', 'float'],
        'prop_type': ['int', 'float'],
        'description': "Maximum value settable in the user interface"
    },
    'step': {
        'type': ['int', 'float'],
        'prop_type': ['int', 'float'],
        'description': "Increment of the value set by input or keyboard arrows"
    },
    'units': {
        'type': ['str', 'list', 'tuple'],
        'prop_type': ['int', 'float', 'str', 'list', 'ModelList', 'UserList', 'tuple', 'group'],
        'description': "Meta text displayed in the input/text box"
    },
    'doc': {
        'type': ['str'],
        'prop_type': ['method', 'bool', 'int', 'float', 'str', 'list', 'ModelList', 'UserList', 'group'],
        'description': "An attribute docstring that may appear as a tooltip"
    },
    'renderAs': {
        'type': ['str'],
        'prop_type': ['str', 'int', 'float', 'method', 'tuple', 'list'],
        'valid_values': ['slider', 'image', 'graph', 'textarea'],
        'description': "Requests the GUI to render the element in a particular way"
    },
    # 'isImage': {
    #     'type': ['bool'],
    #     'prop_type': ['str'],
    #     'description': "Enables displaying an image encoded in a base64 string"
    # },
    # 'isSlider': {
    #     'type': ['bool'],
    #     'prop_type': ['int', 'float'],
    #     'description': "Enables displaying a slider for a single number"
    # },
    # 'isDataStream': {
    #     'type': ['bool'],
    #     'prop_type': ['str', 'method', 'tuple'],
    #     'description': "Enables displaying a line series from a text data stream"
    # },
    'mapping': {
        'type': ['list'],
        'prop_type': ['bool'],
        'description': "Map bool value to human-readable status"
    },
    'displayName': {
        'type': ['str'],
        'prop_type': ['method', 'int', 'float', 'str', 'list', 'ModelList', 'UserList'],
        'description': "Rename a property for GUI display, perhaps to a non-Pythonic string"
    },
    'collapsed': {
        'type': ['bool'],
        'prop_type': ['method', 'group', 'list', 'ModelList', 'UserList'],
        'description': "Default collapse state"
    }
}


def sanitize_metadata(interface):
    """Implements metadata sanity check
    Metadata can only be assigned to properties according to the schema
    defined by METADATA_SPECS. The following checks are performed, in order:

    - Metadata can only be assigned to a property that actually exists in the Model
    - Metadata name must be one of the implemented ones
    - Metadata value type must comply with the spec
    - Metadata must be assigned to an property whose type complies with the spec
    - If there are discrete allowable values, the value must be in that list

    Any exception to this will throw a warning at Dashboard creation, and the corresponding
    entry is ignored and removed from the _metadata dictionary
    """
    metadata = interface._metadata
    sanitized = {}
    for prop_name, mdata in metadata.items():
        sanitized.update(sanitize_metadata_entry(interface, prop_name, mdata))
    return sanitized


def sanitize_metadata_entry(interface, prop_name, mdata, prop=None):
    sanitized = {}
    try:
        prop = getattr(interface, prop_name) if prop is None else prop
        prop_type = get_prop_type(prop)
        sanitized[prop_name] = {}
        for key, value in mdata.items():
            if (check_valid(key, prop_name) and check_type(key, value, prop_name)
                    and check_prop_type(key, prop_type, prop_name) and check_value(key, value, prop_name)):
                sanitized[prop_name][key] = value
        logger.info(f"Validated metadata for property `{prop_name}`")
    except AttributeError:
        logger.warning(
            f'The property `{prop_name}` is not present in the model. Metadata cannot be set.')
    return sanitized


def get_prop_type(prop):
    if isinstance(prop, tuple(BASE_TYPES.values())):
        return type(prop).__name__
    elif inspect.ismethod(prop):
        return 'method'
    elif isinstance(prop, (list, tuple)):
        return type(prop[0]).__name__ if len(prop) else type(prop).__name__
    else:
        return 'group'


def check_valid(key, prop_name):
    valid = key in METADATA_SPECS
    if not valid:
        logger.warning(
            f"Metadata `{key}` in property `{prop_name}` is not a valid metadata")
    return valid


def check_type(key, value, prop_name):
    valid = type(value).__name__ in METADATA_SPECS[key]['type']
    if not valid:
        logger.warning(
            f"Metadata `{key}` in property `{prop_name}` has value `{value}`, which is not of type `{METADATA_SPECS[key]['type']}`")
    return valid


def check_prop_type(key, prop_type, prop_name):
    valid = prop_type in METADATA_SPECS[key]['prop_type']
    if not valid:
        logger.warning(
            f"Metadata `{key}` in property `{prop_name}` assigned to property of type `{prop_type}`, which is not of type `{METADATA_SPECS[key]['prop_type']}`")
    return valid


def check_value(key, value, prop_name):
    try:
        valid = value in METADATA_SPECS[key]['valid_values']
    except KeyError:
        return True
    if not valid:
        logger.warning(
            f"Metadata `{key}` in property`{prop_name}` has value `{value}`, which is not one of the allowed values `{METADATA_SPECS[key]['valid_values']}`")
    return valid
