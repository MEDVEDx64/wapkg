import json

from urllib.request import urlopen
from urllib.error import URLError
from urllib.parse import urljoin

VERSION_REQUIRED = 3


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
