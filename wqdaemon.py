#!/usr/bin/env python3

# WapkgQuack (wq) service daemon
# for asynchronous GUI interaction, etc.

import os

from sys import argv, stdout, exc_info
from wapkg import remote
from socket import *
from select import select
from threading import Thread
from wapkg.repo import Repository
from wapkg.download import DownloadAction

help_message = '''
WapkgQuack service daemon
usage: ''' + argv[0] + ' [port] [listen_addr]'


class WQPacketHandler(object):
    def __init__(self, udp_socket):
        self._addrs = []  # recipients
        self._socket = udp_socket
        self._repo = Repository()
        self._index_cache = []

    def handle(self, packet):
        def send(msg):
            for ad in self._addrs:
                self._socket.sendto(msg.encode('utf-8'), ad)

        def send_text(msg):
            send('quack!text\n' + msg + '\n')

        def send_packages_changed(distro):
            if distro not in self._repo.list_distributions():
                return

            msg = 'quack!packages-changed\ndistro/' + distro + '\n'
            dist_obj = self._repo.get_distribution(distro)
            for pkg in dist_obj.list_packages():
                msg += pkg + ':' + str(dist_obj.get_package_revision(pkg)) + '\n'
            send(msg)

        def send_dists_changed():
            msg = 'quack!dists-changed\n'
            for d in self._repo.list_distributions():
                msg += d + '\n'
            send(msg)

        def send_packages_available(distro):
            if distro not in self._repo.list_distributions():
                return

            packages = {}
            pkgs_bundle = []
            dist_obj = self._repo.get_distribution(distro)
            for index in self._index_cache:
                pkgs = index['packages']
                pkgs_bundle.append(pkgs)
                for pkg in pkgs:
                    rev = -1
                    pkg_ = remote.select_pkg(index['packages'][pkg], dist_obj.get_version_string())
                    if not pkg_:
                        continue
                    if 'revision' in pkg_:
                        rev = pkg_['revision']
                    if pkg in packages:
                        if rev > packages[pkg]:
                            packages[pkg] = rev
                    else:
                        packages[pkg] = rev

            msg = 'quack!packages-available\ndistro/' + distro + '\n'
            for pkg in packages:
                if not remote.trace_pkg_deps(pkgs_bundle, dist_obj.get_version_string(), pkg):
                    continue
                rev = 'virtual'
                if packages[pkg] >= 0:
                    rev = str(packages[pkg])
                msg += pkg + ':' + rev + '\n'

            send(msg)

        def send_dists_available():
            dists = []
            for index in self._index_cache:
                for dist in index['distributions']:
                    if dist not in dists:
                        dists.append(dist)

            msg = 'quack!dists-available\n'
            for dist in dists:
                msg += dist + '\n'

            send(msg)

        def send_action_complete(token):
            send('quack!action-complete\n' + token + '\n')

        def send_sources_changed():
            sources = ''
            for src in self._repo.settings['sources']:
                sources += '\n' + src

            send('quack!sources-changed' + sources + '\n')

        def update_index():
            self._index_cache.clear()
            for src in self._repo.get_sources():
                index = remote.fetch_index(src)
                if index:
                    self._index_cache.append(index)

            send('quack!index-changed\n')

        class DistroDownloadAction(DownloadAction):
            def update_progress(self, current, total):
                send('quack!action-update\n' + self.token + '\n' + str(current) + '\n' + str(total) + '\n')

        def handler_thread():
            try:
                msg, addr = packet
                msg = msg.decode('utf-8').split('\n')[0]
                if not msg.startswith('wq/0.1'):
                    return

                wqargs = []
                for x in msg.split(';')[1:]:
                    if len(x.strip()) > 0:
                        wqargs.append(x)

                req = wqargs[0]

                if req == 'subscribe':
                    ad = wqargs[1], int(wqargs[2])
                    if not ad[0] == addr[0]:
                        return
                    if ad not in self._addrs:
                        self._addrs.append(ad)
                    return

                elif req == 'unsubscribe':
                    ad = wqargs[1], int(wqargs[2])
                    if ad in self._addrs:
                        self._addrs.remove(ad)

                elif req == 'update-index':
                    update_index()

                elif req == 'install':
                    packages_installed = 0
                    recent_package = None
                    dist = self._repo.get_distribution(wqargs[1])

                    for pkg in wqargs[2:]:
                        if os.path.exists(pkg) and os.path.isfile(pkg):
                            send_text("+ Installing package '" + pkg + "'...")
                            ok, msg = dist.install_package_from_file(pkg)
                        else:
                            send_text("+ Downloading and installing '" + pkg + "'...")
                            ok, msg = dist.install_package_by_name(pkg, self._repo.get_sources())
                        if ok:
                            packages_installed += 1
                            recent_package = pkg
                        else:
                            send_text('! Package installation error (' + pkg + '): ' + msg)

                    if packages_installed:
                        if packages_installed > 1:
                            send_text('Installed ' + str(packages_installed) +
                                      " packages into distro '" + wqargs[1] + "'")
                        elif packages_installed == 1:
                            send_text("Installed package '" + recent_package + " into distro '" + wqargs[1] + "'")
                        send_packages_changed(wqargs[1])

                elif req == 'remove':
                    packages_removed = 0
                    recent_package = None
                    for pkg in wqargs[2:]:
                        ok, msg = self._repo.get_distribution(wqargs[1]).remove_package(pkg)
                        if ok:
                            packages_removed += 1
                            recent_package = pkg
                        else:
                            send_text('! Package removal error (' + pkg + '): ' + msg)

                    if packages_removed:
                        if packages_removed > 1:
                            send_text('Removed ' + str(packages_removed) + " packages from distro '" + wqargs[1] + "'")
                        elif packages_removed == 1:
                            send_text("Removed package '" + recent_package + " from distro '" + wqargs[1] + "'")
                        send_packages_changed(wqargs[1])

                elif req == 'dist-install':
                    dists_installed = False
                    suggested_name = None
                    action_token = None
                    installed_as = ''

                    if len(wqargs) > 2:
                        suggested_name = wqargs[2]
                        installed_as = " as '" + suggested_name + "'"

                    if len(wqargs) > 3:
                        action_token = wqargs[3]

                    if os.path.exists(wqargs[1]) and os.path.isfile(wqargs[1]):
                        send_text("+ Installing '" + wqargs[1] + "'...")
                        ok, msg, dn = self._repo.install_dist_from_file(wqargs[1], suggested_name)
                    else:
                        action = None
                        if action_token:
                            action = DistroDownloadAction(action_token)
                        send_text("+ Downloading and installing '" + wqargs[1] + "'...")
                        ok, msg, dn = self._repo.install_dist_by_name(wqargs[1], self._repo.get_sources(),
                                                                      suggested_name, action)
                    if ok:
                        dists_installed = True
                    else:
                        send_text('Distro installation error (' + wqargs[1] + '): ' + msg)

                    if dists_installed:
                        send_text("Installed distro '" + wqargs[1] + "'" + installed_as)
                        send_dists_changed()

                    if action_token:
                        send_action_complete(action_token)

                elif req == 'packages':
                    send_packages_changed(wqargs[1])

                elif req == 'packages-available':
                    send_packages_available(wqargs[1])

                elif req == 'dists':
                    send_dists_changed()

                elif req == 'dists-available':
                    send_dists_available()

                elif req == 'wd':
                    send('quack!wd\n' + self._repo.wd + '\n')

                elif req == 'sources':
                    send_sources_changed()

                elif req == 'push-sources':
                    self._repo.settings['sources'] = []
                    for src in wqargs[1:]:
                        self._repo.settings['sources'].append(src)

                    self._repo.write_settings()
                    send_sources_changed()
                    update_index()

            except:
                send_text('Unexcepted error: ' + str(exc_info()[1]))
                raise

        Thread(target=handler_thread).start()


def main():
    lsn_addr = '127.0.0.1'
    lsn_port = 16723

    try:
        if argv[1] == '-h' or argv[1] == '--help':
            print(help_message)
            return
        lsn_port = int(argv[1])
        lsn_addr = argv[2]
    except IndexError:
        pass

    srv_socket = socket(AF_INET, SOCK_DGRAM)
    handler = WQPacketHandler(srv_socket)

    try:
        srv_socket.bind((lsn_addr, lsn_port))
        srv_socket.setblocking(0)
        print('ready')
        stdout.flush()

        while True:
            if select([srv_socket], [], [], 1)[0]:  # one second timeout
                handler.handle(srv_socket.recvfrom(65536))

    except KeyboardInterrupt:
        pass
    finally:
        srv_socket.close()

if __name__ == '__main__':
    main()
