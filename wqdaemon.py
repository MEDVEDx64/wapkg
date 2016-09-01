#!/usr/bin/env python3

# WapkgQuack (wq) service daemon
# for asynchronous GUI interaction, etc.

import os

from sys import argv
from socket import *
from select import select
from threading import Thread
from wapkg.repo import Repository
from wapkg.remote import fetch_index

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

        def send_packages_available():
            packages = {}
            for index in self._index_cache:
                for pkg in index['packages']:
                    rev = -1
                    if 'revision' in index['packages'][pkg]:
                        rev = index['packages'][pkg]['revision']
                    if pkg in packages:
                        if rev > packages[pkg]:
                            packages[pkg] = rev
                    else:
                        packages[pkg] = rev

            msg = 'quack!packages-available\n'
            for pkg in packages:
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

        def handler_thread():
            msg, addr = packet
            msg = msg.decode('utf-8')
            if not msg.startswith('wq/0.1'):
                return

            wqargs = msg.split(':')[1:]
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
                self._index_cache.clear()
                for src in self._repo.get_sources():
                    index = fetch_index(src)
                    if index:
                        self._index_cache.append(index)

            elif req == 'install':
                packages_installed = False
                dist = self._repo.get_distribution(wqargs[1])

                for pkg in wqargs[2:]:
                    if os.path.exists(pkg) and os.path.isfile(pkg):
                        ok, msg = dist.install_package_from_file(pkg)
                    else:
                        ok, msg = dist.install_package_by_name(pkg, self._repo.get_sources())
                    if ok:
                        packages_installed = True
                    else:
                        send_text('Package installation error (' + pkg + '): ' + msg)

                if packages_installed:
                    send_packages_changed(wqargs[1])

            elif req == 'remove':
                packages_removed = False
                for pkg in wqargs[2:]:
                    ok, msg = self._repo.get_distribution(wqargs[1]).remove_package(pkg)
                    if ok:
                        packages_removed = True
                    else:
                        send_text('Package removal error (' + pkg + '): ' + msg)

                if packages_removed:
                    send_packages_changed(wqargs[1])

            elif req == 'dist-install':
                dists_installed = False
                suggested_name = None
                if len(wqargs) > 2:
                    suggested_name = wqargs[2]

                if os.path.exists(wqargs[1]) and os.path.isfile(wqargs[1]):
                    ok, msg, dn = self._repo.install_dist_from_file(wqargs[1], suggested_name)
                else:
                    ok, msg, dn = self._repo.install_dist_by_name(wqargs[1], self._repo.get_sources(), suggested_name)
                if ok:
                    dists_installed = True
                else:
                    send_text('Distro installation error (' + wqargs[1] + '): ' + msg)

                if dists_installed:
                    send_dists_changed()

            elif req == 'packages':
                send_packages_changed(wqargs[1])

            elif req == 'packages-available':
                send_packages_available()

            elif req == 'dists':
                send_dists_changed()

            elif req == 'dists-available':
                send_dists_available()

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
        while True:
            if select([srv_socket], [], [], 1)[0]:  # one second timeout
                handler.handle(srv_socket.recvfrom(65536))

    except KeyboardInterrupt:
        pass
    finally:
        srv_socket.close()

if __name__ == '__main__':
    main()
