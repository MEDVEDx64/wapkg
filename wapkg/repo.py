import os
import sys
import json
import ctypes
import sqlite3

from uuid import uuid4
from zipfile import ZipFile
from urllib.error import URLError
from urllib.parse import urljoin

from . import remote
from .distro import Distribution
from .download import Downloader


class Repository(object):
    def __init__(self, default_sources=None):
        self.wd = '.'
        if not os.path.exists('portable') or not os.path.isfile('portable'):
            if sys.platform == 'win32':
                self.wd = os.path.join(os.getenv('APPDATA'), 'wapkg')
            else:
                self.wd = os.path.join(os.getenv('HOME'), '.wapkg')

        if not os.path.exists(self.wd):
            os.mkdir(self.wd)
        self.sf = os.path.join(self.wd, 'settings.json')
        if not os.path.exists(self.sf):
            with open(self.sf, 'w') as f:
                settings = {
                    'sources': [],
                    'disable_external_sources_list': False
                }
                if default_sources:
                    settings['sources'] = default_sources
                f.write(json.dumps(settings, indent=4))

        for x in os.listdir(self.wd):
            p = os.path.join(self.wd, x)
            if os.path.isfile(p) and x.endswith('.download'):
                os.unlink(p)

        self.settings = {}
        with open(self.sf, 'r') as f:
            self.settings = json.loads(f.read())
        if 'path' in self.settings:
            self.wd = self.settings['path']

        self._extrnl_flag = False

    def list_distributions(self):
        distro = []
        for d in os.listdir(self.wd):
            if os.path.exists(os.path.join(self.wd, d, '.wadist')):
                distro.append(d)

        return distro

    def get_distribution(self, name):
        return Distribution(os.path.join(self.wd, name))

    def get_sources(self):
        if not self._extrnl_flag:
            self._extrnl_flag = True
            if not ('disable_external_sources_list' in self.settings and self.settings['disable_external_sources_list']):
                self.settings['sources'] += remote.fetch_external_sources()

        return self.settings['sources']

    # Returns: succeeded, message, distro name
    def install_dist_from_file(self, path, target_name=None):
        dist_name = None
        with ZipFile(path) as zf:
            wadist = json.loads(zf.read('wadist.json').decode('utf-8'))
            if not wadist['version'] == 1:
                return False, 'Unsupported distribution format', None

            target = wadist['suggestedName']
            if target_name:
                target = target_name
            dist_name = target
            target = os.path.join(self.wd, target)
            if os.path.exists(target):
                return False, 'A distribution with such name already exists', None

            repo = os.path.join(target, '.wadist')
            os.makedirs(os.path.join(repo, 'cache'))
            if sys.platform == 'win32':
                # Setting 'hidden' attribute
                ctypes.windll.kernel32.SetFileAttributesW(repo, 2)
            with open(os.path.join(repo, 'version'), 'w') as vf:
                vf.write('1')
            with sqlite3.connect(os.path.join(repo, 'packages.db')) as conn:
                c = conn.cursor()
                c.execute('CREATE TABLE packages(name char(64) primary key not null,revision uint not null)')
                c.execute('CREATE TABLE paths('
                          'path char(512) not null primary key,'
                          'dir int(1) not null default 0,'
                          'package char(64) not null,'
                          'foreign key (package) references packages(name) on delete cascade'
                          ');')
                conn.commit()

            for n in zf.namelist():
                if n.startswith('wadist'):
                    continue
                zf.extract(n, target)

        return True, 'Success', dist_name

    def install_dist_by_name(self, name, sources, target_name=None, action=None):
        target = name
        if target_name:
            target = target_name
        if os.path.exists(os.path.join(self.wd, target)):
            return False, 'A distribution with such name already exists', None

        for src in sources:
            index = remote.fetch_index(src)
            if not index:
                continue
            if name not in index['distributions']:
                continue

            dist = index['distributions'][name]

            if 'path' in dist or 'uri' in dist:
                if 'path' in dist:
                    link = urljoin(src, dist['path'])
                else:
                    link = dist['uri']
                path = os.path.join(self.wd, str(uuid4()) + '.download')
                hexdigest = None
                if 'sha1' in dist:
                    hexdigest = dist['sha1']
                try:
                    Downloader().go(link, path, action).verify_sha1(hexdigest)
                except URLError:
                    continue

                ok, msg, dn = self.install_dist_from_file(path, target_name)
                os.unlink(path)
                return ok, msg, dn

        return False, 'No suitable distro source found', None

    def write_settings(self):
        with open(self.sf, 'w+') as f:
            f.write(json.dumps(self.settings, sort_keys=True, indent=4))
