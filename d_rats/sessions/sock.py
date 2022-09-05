'''Sock'''
from __future__ import absolute_import
from __future__ import print_function
import socket
from threading import Thread

from d_rats.sessions import base, stateful


class SocketSession(stateful.StatefulSession):
    '''
    Socket Session.

    :param name: Session name
    :param status_cb: Status call back function
    '''
    type = base.T_SOCKET

    IDLE_TIMEOUT = None

    def __init__(self, name, status_cb=None):
        stateful.StatefulSession.__init__(self, name)

        if status_cb:
            self.status_cb = status_cb
        else:
            self.status_cb = self._status

    # pylint: disable=no-self-use
    def _status(self, msg):
        print(("Sock      : Socket Status: %s" % msg))


# pylint: disable=too-many-instance-attributes
class SocketListener():
    '''
    Socket Listener.

    :param session_mgr: SessionManager object
    :param dest: Destination to listen to
    :param sport: Source Port
    :param dport: Destination Port
    :param addr: TCP address, default='0.0.0.0'
    '''

    # pylint: disable=too-many-arguments
    def __init__(self, session_mgr, dest, sport, dport, addr='0.0.0.0'):
        # pylint: disable=invalid-name
        self.sm = session_mgr
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
        '''Stop.'''
        self.enabled = False
        self.thread.join()

    def listener(self):
        '''Listener.'''
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
            # pylint: disable=broad-except
            except Exception as err:
                print("Sock      : Socket exception: %s -%s-" %
                      (type(err),err))
                self.enabled = False
                break

            print("Sock      :",
                  " %i: Incoming socket connection from %s" %
                  (self.dport, addr))

            session = self.sm.start_session(name=name,
                                            dest=self.dest,
                                            cls=SocketSession)

            while session.get_state() != base.ST_CLSD and self.enabled:
                session.wait_for_state_change(1)

            print(("Sock      : %s ended" % name))
            self.dsock.close()
            self.dsock = None

        sock.close()
        print("Sock      : TCP:%i shutdown" % self.dport)
