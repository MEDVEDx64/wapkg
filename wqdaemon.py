#!/usr/bin/env python3

# WapkgQuack (wq) service daemon
# for asynchronous GUI interaction, etc.

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
                if wqargs[1] not in self._repo.list_distributions():
                    send_text('No such distro installed: ' + wqargs[1])
                    return

                packages_installed = False
                for pkg in wqargs[2:]:
                    ok, msg = self._repo.get_distribution(
                        wqargs[1]).install_package_by_name(pkg, self._repo.get_sources())
                    if ok:
                        packages_installed = True
                    else:
                        send_text('package installation error (' + pkg + '): ' + msg)

                if packages_installed:
                    send_packages_changed(wqargs[1])

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
