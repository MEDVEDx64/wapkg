WAPKG_VERSION_MAJOR = 0
WAPKG_VERSION_MINOR = 4
WAPKG_VERSION_MICRO = 3


def get_version():
    return 'wapkg ' + str(WAPKG_VERSION_MAJOR) + '.' \
           + str(WAPKG_VERSION_MINOR) + '.' \
           + str(WAPKG_VERSION_MICRO)
