from __future__ import absolute_import
from __future__ import print_function
import socket
from threading import Thread

from d_rats.sessions import base, stateful

class SocketSession(stateful.StatefulSession):
    type = base.T_SOCKET

    IDLE_TIMEOUT = None

    def __init__(self, name, status_cb=None):
        stateful.StatefulSession.__init__(self, name)

        if status_cb:
            self.status_cb = status_cb
        else:
            self.status_cb = self._status

    def _status(self, msg):
        print(("Sock      : Socket Status: %s" % msg))

class SocketListener(object):
    def __init__(self, sm, dest, sport, dport, addr='0.0.0.0'):
        self.sm = sm
        self.dest = dest
        self.sport = sport
        self.dport = dport
        self.addr = addr
        self.enabled = True
        self.lsock = None
        self.dsock = None
        self.thread = Thread(target=self.listener)
        self.thread.setDaemon(True)
        self.thread.start()

    def stop(self):
        self.enabled = False
        self.thread.join()

    def listener(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET,
                        socket.SO_REUSEADDR,
                        1)
        sock.settimeout(0.25)
        sock.bind(('0.0.0.0', self.sport))
        sock.listen(0)

        self.lsock = sock

        name = "TCP:%i" % self.dport

        while self.enabled:
            try:
                (self.dsock, addr) = sock.accept()
            except socket.timeout:
                continue
            except Exception as e:
                print(("Sock      : Socket exception: %s" % e))
                self.enabled = False
                break

            print(("Sock      : %i: Incoming socket connection from %s" % (self.dport, addr)))

            s = self.sm.start_session(name=name,
                                      dest=self.dest,
                                      cls=SocketSession)

            while s.get_state() != base.ST_CLSD and self.enabled:
                s.wait_for_state_change(1)

            print(("Sock      : %s ended" % name))
            self.dsock.close()
            self.dsock = None

        sock.close()
        print(("Sock      : TCP:%i shutdown" % self.dport))
