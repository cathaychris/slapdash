__version__ = "1.1.0"
__major__, __minor__, __patch__ = (int(v) for v in __version__.split("."))

# This uses Semantic Versioning 2.0.0

# Given a version number MAJOR.MINOR.PATCH, increment the:
# 1. MAJOR version when you make incompatible API changes,
# 2. MINOR version when you add functionality in a backwards compatible manner, and
# 3. PATCH version when you make backwards compatible bug fixes.
# Additional labels for pre-release and build metadata are available as extensions to the MAJOR.MINOR.PATCH format.

# The version update should always accompany a merge into the main branch.
# Note that `Client` refuses to connect to a server with a different MAJOR version.
