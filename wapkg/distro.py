import os
import json
import errno
import shutil
import sqlite3

from uuid import uuid4
from zipfile import ZipFile
from urllib.error import URLError
from urllib.parse import urljoin

from . import remote
from .download import Downloader

from _3rdparty.fileversion import calcversioninfo


class Distribution(object):
    def __init__(self, path):
        self.wd = path
        self.repo = os.path.join(path, '.wadist')
        self.pkgdb = os.path.join(self.repo, 'packages.db')

        self._version_string_cached = False
        self._version_string = None

        if not os.path.exists(self.repo):
            raise RuntimeError('The path specified does not exist (or not a distro)')

        with open(os.path.join(self.repo, 'version'), 'r') as ver:
            if not int(ver.read()) == 1:
                raise RuntimeError('Distribution version mismatch')

        self.clean_cache()

    def get_name(self):
        return self.wd.split(os.sep)[-1]

    # Returns None when no data found
    def get_version_string(self):
        if not self._version_string_cached:
            self._version_string = calcversioninfo(os.path.join(self.wd, 'WA.exe'))
            self._version_string_cached = True

        return self._version_string

    # Returns list of names
    def list_packages(self):
        list = []
        with sqlite3.connect(self.pkgdb) as conn:
            c = conn.cursor()
            for pkg in c.execute('SELECT name FROM packages ORDER BY name'):
                list.append(pkg[0])

        return list

    # Returns None in case of fail, integer otherwise.
    def get_package_revision(self, name):
        with sqlite3.connect(self.pkgdb) as conn:
            c = conn.cursor()
            c.execute('SELECT revision FROM packages WHERE name=?', (name,))
            row = c.fetchone()
            if not row:
                return None
            return row[0]

    # This and following package-related methods return tuple (succeeded, msg).
    # Exceptions may be thrown.
    def install_package_from_file(self, path):
        with ZipFile(path) as zf:
            wapkg = json.loads(zf.read('wapkg.json').decode('utf-8'))
            if not wapkg['version'] == 1:
                return False, 'Unsupported package format'

            if wapkg['name'] in self.list_packages():
                if wapkg['revision'] > self.get_package_revision(wapkg['name']):
                    self.remove_package(wapkg['name'])
                else:
                    return False, 'Package is already installed and updating is not required'

            with sqlite3.connect(self.pkgdb) as conn:
                c = conn.cursor()
                c.execute('INSERT INTO packages (name, revision) VALUES (?, ?)', (wapkg['name'], wapkg['revision']))

                for n in zf.namelist():
                    if n == 'wapkg.json' or n.startswith('.wadist'):
                        continue
                    is_dir = 0
                    if n[-1] == '/':
                        is_dir = 1

                    c.execute('INSERT INTO paths (path, dir, package) VALUES (?, ?, ?)', (n, is_dir, wapkg['name']))
                    zf.extract(n, self.wd)

                conn.commit()

        return True, 'Success'

    def install_package_by_name(self, name, sources, precached_index=None):
        revision_fail = False
        installed_any_reqs = False
        for src in sources:
            index = precached_index
            if not index:
                index = remote.fetch_index(src)
                if not index:
                    continue

            if name not in index['packages']:
                continue

            pkg = remote.select_pkg(index['packages'][name], self.get_version_string())
            if not pkg:
                continue

            if 'requirements' in pkg:
                for req in pkg['requirements']:
                    ok, msg = self.install_package_by_name(req, sources, index)
                    if not installed_any_reqs:
                        installed_any_reqs = ok

            if 'revision' not in pkg:
                if installed_any_reqs:
                    return True, 'Success'
                if 'requirements' in pkg:
                    return False, 'This virtual package is already installed and updating is not required'
                continue

            if name in self.list_packages():
                if pkg['revision'] <= self.get_package_revision(name):
                    revision_fail = True
                    continue

            if 'path' in pkg or 'uri' in pkg:
                if 'path' in pkg:
                    link = urljoin(src, pkg['path'])
                else:
                    link = pkg['uri']

                path = os.path.join(self.repo, 'cache', str(uuid4()))
                hexdigest = None
                if 'sha1' in pkg:
                    hexdigest = pkg['sha1']
                try:
                    Downloader().go(link, path).verify_sha1(hexdigest)
                except URLError:
                    continue

                inst = self.install_package_from_file(path)
                self.clean_cache()
                return inst

        message = 'No suitable package source found'
        if revision_fail:
            message = 'The latest package revision is already installed and there is no newer one found'
        return revision_fail and installed_any_reqs, message

    def remove_package(self, name):
        if name not in self.list_packages():
            return False, 'No such package installed'

        with sqlite3.connect(self.pkgdb) as conn:
            c = conn.cursor()
            for f in c.execute('SELECT path FROM paths WHERE package=? AND dir=0', (name,)):
                p = os.path.join(self.wd, f[0])
                if os.path.exists(p):
                    os.remove(p)

            dirs = []
            for d in c.execute('SELECT path FROM paths WHERE package=? AND NOT dir=0', (name,)):
                dirs.append(d[0])

            depth = 1
            depth_collected = False

            while depth:
                for d in dirs:
                    if not depth_collected:
                        dc = d.count('/')
                        if dc > depth:
                            depth = dc

                    p = os.path.join(self.wd, d)
                    try:
                        if os.path.exists(p):
                            os.rmdir(p)
                    except OSError as e:
                        if not e.errno == errno.ENOTEMPTY:
                            raise

                depth -= 1
                if not depth_collected:
                    depth_collected = True

            c.execute('DELETE FROM paths WHERE package=?', (name,))
            c.execute('DELETE FROM packages WHERE name=?', (name,))
            conn.commit()

        return True, 'Success'

    def clean_cache(self):
        path = os.path.join(self.repo, 'cache')
        for x in os.listdir(path):
            os.unlink(os.path.join(path, x))

    def exterminate(self):
        shutil.rmtree(self.wd)
