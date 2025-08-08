"""
Version information for yt-dlp Convenient GUI.

This module follows Semantic Versioning 2.0.0 (https://semver.org/).

Given a version number MAJOR.MINOR.PATCH, increment the:
- MAJOR version when you make incompatible API changes
- MINOR version when you add functionality in a backward compatible manner  
- PATCH version when you make backward compatible bug fixes

Additional labels for pre-release and build metadata are available as extensions
to the MAJOR.MINOR.PATCH format.
"""

# Version components
MAJOR = 1
MINOR = 6
PATCH = 0

# Pre-release identifier (empty string for stable releases)
# Examples: "alpha", "alpha.1", "beta", "beta.2", "rc.1"
PRERELEASE = ""

# Build metadata (empty string if not applicable)
# Examples: "20230313144700", "exp.sha.5114f85"
BUILD_METADATA = ""

def _format_version():
    """Format the version string according to Semantic Versioning 2.0.0."""
    version = f"{MAJOR}.{MINOR}.{PATCH}"
    
    if PRERELEASE:
        version += f"-{PRERELEASE}"
    
    if BUILD_METADATA:
        version += f"+{BUILD_METADATA}"
    
    return version

# The canonical version string
__version__ = _format_version()

# Convenience variables for backward compatibility
VERSION = __version__
APP_VERSION = __version__

# Version tuple for programmatic comparison
VERSION_TUPLE = (MAJOR, MINOR, PATCH)

# Version info dictionary
VERSION_INFO = {
    'major': MAJOR,
    'minor': MINOR,
    'patch': PATCH,
    'prerelease': PRERELEASE,
    'build_metadata': BUILD_METADATA,
    'version': __version__,
    'version_tuple': VERSION_TUPLE
}

def get_version():
    """Get the current version string."""
    return __version__

def get_version_info():
    """Get detailed version information."""
    return VERSION_INFO.copy()

def is_prerelease():
    """Check if this is a pre-release version."""
    return bool(PRERELEASE)

def is_stable():
    """Check if this is a stable release version."""
    return not is_prerelease()
