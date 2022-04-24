#!/usr/bin/python
# pylint: disable=invalid-name
'''
plugin_test.

This is a test and demonstration of using the d-rats plugin feature.
'''

import argparse
import gettext
import logging
import time

from xmlrpc.client import Fault
from xmlrpc.client import ServerProxy

# This makes pylance happy with out overriding settings
# from the invoker of the classes and methods in this module.
if not '_' in locals():
    _ = gettext.gettext


# pylint wants at least 2 public methods
# pylint: disable=too-few-public-methods
class PluginProxy:
    '''
    Plugin Proxy Client.

    :param server: D-rats plugin server address
    :type server: str
    :param port: D-Rats plugin server port
    :type port: int
    '''

    def __init__(self, server, port):
        pluginsrv = "http://%s:%i" % (server, port)
        self.server = ServerProxy(pluginsrv)

    def wait_for_result(self, ident, count=10, delay=5):
        '''
        Wait for result.

        :param ident: identification of RPC job
        :type ident: int
        :param count: Number of times to poll for result, default 10
        :type count: int
        :param delay: Delay time in seconds
        :type delay: float
        :returns: Result of call
        :rtype: dict
        '''
        while count > 0:
            count -= 1
            time.sleep(delay)
            result = self.server.get_result(ident)
            if result:
                break
        return result


def main():
    '''Plugin test Main module.'''

    gettext.install("D-RATS")
    lang = gettext.translation("D-RATS",
                               localedir="locale",
                               fallback=True)
    lang.install()
    # pylint: disable=global-statement
    global _
    _ = lang.gettext


    # pylint: disable=too-few-public-methods
    class LoglevelAction(argparse.Action):
        '''
        Custom Log Level action.

        This allows entering a log level command line argument
        as either a known log level name or a number.
        '''

        def __init__(self, option_strings, dest, nargs=None, **kwargs):
            if nargs is not None:
                raise ValueError("nargs is not allowed")
            argparse.Action.__init__(self, option_strings, dest, **kwargs)

        def __call__(self, parser, namespace, values, option_strings=None):
            level = values.upper()
            level_name = logging.getLevelName(level)
            # Contrary to documentation, the above returns for me
            # an int if given a name or number of a known named level and
            # str if given a number for a level with out a name.
            if isinstance(level_name, int):
                level_name = level
            elif level_name.startswith('Level '):
                level_name = int(level)
            setattr(namespace, self.dest, level_name)

    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description=_('PLUGIN_TEST'))

    # While loglevel actually returns an int, it needs to be set to the
    # default type of str for the action routine to handle both named and
    # numbered levels.
    parser.add_argument('--loglevel',
                        action=LoglevelAction,
                        default='INFO',
                        help=_('LOGLEVEL TO TEST WITH'))

    # Future option, right now d-rats is only listening on localhost
    parser.add_argument("-s", "--server",
                        default='localhost',
                        help="D-rats CLIENT PLUGIN SERVER NAME")

    # Future option, right now d-rats is only listening on port 9100
    parser.add_argument("-p", "--port",
                        default=9100,
                        help="D-rats CLIENT PLUGIN SERVER PORT")

    parser.add_argument("--stationid",
                        default='NOCALL',
                        help="Station ID to use for test")

    args = parser.parse_args()

    logging.basicConfig(format="%(asctime)s:%(levelname)s:%(name)s:%(message)s",
                        datefmt="%m/%d/%Y %H:%M:%S",
                        level=args.loglevel)

    logger = logging.getLogger("Plugin_Test")

    proxy = PluginProxy(args.server, args.port)

    ports = proxy.server.list_ports()
    logger.info("ports %s", ports)

    try:
        rpc_job = proxy.server.submit_rpcjob(args.stationid, 'RPCGetVersion')
        logger.info("rpc_job %i", rpc_job)

        result = proxy.wait_for_result(rpc_job)

        for key, value in result.items():
            print("key %s value %s" % (key, value))
    except Fault as err:
        logger.info("Plugin call failed: %s", err)


if __name__ == "__main__":
    main()

# Things to test eventually.
# "send_chat"
# "wait_for_chat"
# "list_ports" (x)
# "send_file"
# "submit_rpcjob" (1 of 8)
# "get_result"
#   'RPCFileListJob(destination, description)
#   'RPCFormListJob',
#   'RPCPullFileJob',
#   'RPCDeleteFileJob',
#   'RPCPullFormJob',
#   'RPCPositionReport',
#   'RPCGetVersion', (x)
#   'RPCCheckMail'
