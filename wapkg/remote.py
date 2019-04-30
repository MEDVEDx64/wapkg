import json

from urllib.request import urlopen
from urllib.error import URLError
from urllib.parse import urljoin

VERSION_REQUIRED = 3
EXTERNAL_LIST = 'https://pastebin.com/raw/aKjmATab'


# Returns repo index dictionary object, or None in case of failure
def fetch_index(repo_url):
    try:
        with urlopen(urljoin(repo_url, 'index.json')) as index_req:
            index = json.loads(index_req.read().decode('utf-8'))
    except URLError:
        return None

    if 'repo' not in index or not index['repo'] == 'wapkg':
        return None
    if not index['version'] == VERSION_REQUIRED:
        if index['version'] > VERSION_REQUIRED:
            print("! Source '" + repo_url + "' requires newer version of wapkg, " +
                  'consider upgrading your software in order to use this repo.')
        return None

    return index


def fetch_external_sources():
    sources = []
    try:
        with urlopen(EXTERNAL_LIST) as lst_req:
            for src in lst_req.read().decode('utf-8').split('\n'):
                src_ = src.strip()
                if len(src_) and not src_.startswith('#'):
                    sources.append(src_)
    except URLError:
        pass

    return sources


# Unwraps the 'switch' content
def select_pkg(pkg, vs):
    if not pkg:
        return None

    if 'switch' in pkg:
        if not vs:
            return None

        switch = pkg['switch']
        for v in switch:
            if vs in v.split(','):
                return switch[v]

        if '*' in switch:
            return switch['*']
        return None

    return pkg


# Returns True if package and all it's dependencies can be successfully installed
def trace_pkg_deps(pkgs_bundle, vs, name):
    pkg = None
    for pkgs in pkgs_bundle:
        if name in pkgs:
            pkg = pkgs[name]
            break

    pkg = select_pkg(pkg, vs)
    if not pkg:
        return False

    if 'requirements' in pkg:
        for req in pkg['requirements']:
            if not trace_pkg_deps(pkgs_bundle, vs, req):
                return False

    return True
