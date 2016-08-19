import os
import json
import errno
import sqlite3

from uuid import uuid4
from zipfile import ZipFile
from urllib.request import urlopen
from urllib.error import URLError
from urllib.parse import urljoin

from . import remote


class Distribution(object):
    def __init__(self, path):
        self.wd = path
        self.repo = os.path.join(path, '.wadist')
        self.pkgdb = os.path.join(self.repo, 'packages.db')

        if not os.path.exists(self.repo):
            raise RuntimeError('The path specified does not exist (or not a distro)')

        with open(os.path.join(self.repo, 'version'), 'r') as ver:
            if not int(ver.read()) == 1:
                raise RuntimeError('Distribution version mismatch')

        self.clean_cache()

    def get_name(self):
        return self.wd.split(os.sep)[-1]

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

    def install_package_by_name(self, name, sources):
        for src in sources:
            index = remote.fetch_index(src)
            if not index:
                continue
            if name not in index['packages']:
                continue

            pkg = index['packages'][name]
            if name in self.list_packages():
                if pkg['revision'] <= self.get_package_revision(name):
                    continue

            if 'path' in pkg or 'uri' in pkg:
                link = ''
                path = ''

                if 'path' in pkg:
                    link = urljoin(src, pkg['path'])
                else:
                    link = pkg['uri']
                try:
                    with urlopen(link) as pkg_req:
                        path = os.path.join(self.repo, 'cache', str(uuid4()))
                        with open(path, 'wb') as f:
                            f.write(pkg_req.read())
                except URLError:
                    continue

                inst = self.install_package_from_file(path)
                self.clean_cache()
                return inst

        return False, 'No suitable package source found'

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
