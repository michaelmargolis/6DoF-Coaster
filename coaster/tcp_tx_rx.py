# tcp_rx_tx.py  a single-threaded TCP client, Python 2/3 compatible

from __future__ import print_function, unicode_literals

import sys
import socket
import errno
import logging

log = logging.getLogger(__name__)
VERBOSE_LOG = False  # set True for verbose debug logging

PY2 = sys.version_info[0] == 2
if PY2:
    text_type = unicode  # noqa: F821 (defined in Py2)
    bytes_types = (str, bytearray)
else:
    text_type = str
    bytes_types = (bytes, bytearray)


def _to_bytes(data, encoding='utf-8', errors='strict'):
    """
    Ensure data is bytes for socket.sendall in both Py2/3.
    Accepts text (unicode/str) or bytes/bytearray.
    """
    if isinstance(data, bytes_types):
        return bytes(data)
    if isinstance(data, text_type):
        return data.encode(encoding, errors)
    # Fallback: try stringify then encode
    return text_type(data).encode(encoding, errors)


class TcpTxRx(object):
    """
    Non-threaded TCP client (Py2/3)
    """

    def __init__(self, server_address=('127.0.0.1', 15151), timeout=0.5):
        self.tcp_address = server_address
        self.timeout = float(timeout)
        self.sck = None
        self.is_connected = False

    def connect(self):
        host, port = self.tcp_address
        log.debug('Attempting to connect to %s:%d', host, port)
        try:
            # Respect configured timeout
            self.sck = socket.create_connection(self.tcp_address, self.timeout)
            self.sck.settimeout(self.timeout)
            self.is_connected = True
            log.debug('Connected to %s:%d', host, port)
            return True
        except socket.timeout:
            pass            
        except Exception as e:
            # Allow caller to handle/log if they want
            log.error('Connection to %s:%d failed: %s', host, port, e)
            self.is_connected = False
            self.sck = None
            return False

    def send(self, msg):
        if not self.is_connected or self.sck is None:
            log.debug("unable to send because not connected -> %r", msg)
            return

        try:
            buf = _to_bytes(msg)
            if VERBOSE_LOG:
                log.debug('Attempting to send %r', buf)
            self.sck.sendall(buf)
        except socket.error as error:
            err = getattr(error, 'errno', None)
            # Cross-platform checks (Windows may use WSA* constants or raw ints)
            if err in (errno.ECONNRESET, getattr(errno, 'WSAECONNRESET', 10054), 10054):
                log.error("connection reset by peer %s:%d", self.tcp_address[0], self.tcp_address[1])
            elif err in (errno.ENOTCONN, 10057):
                log.warning("socket not connected; is target running?")
            else:
                log.error("error in client socket send: %s", error)
            self.is_connected = False
        except Exception as e:
            log.error("unhandled error in send: %s", e)
            self.is_connected = False

    def receive(self, buffer_size=128):
        if self.sck is None:
            return None
        try:
            return self.sck.recv(int(buffer_size))
        except socket.timeout:
            log.warning("timeout in receive")
            return None
        except socket.error as e:
            log.error("socket error in receive: %s", e)
            self.is_connected = False
            return None
        except Exception as e:
            log.error("unhandled receive error: %s", e)
            self.is_connected = False
            return None

    def close(self):
        if self.sck:
            try:
                self.sck.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass  # ignore shutdown errors on already-closed sockets
            try:
                self.sck.close()
            finally:
                self.sck = None
        self.is_connected = False
        print("connection closed")

    # Context manager support
    def __enter__(self):
        if not self.connect():
            raise socket.error("TcpTxRx: connect() failed for %s:%s" % self.tcp_address)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        # Do not suppress exceptions
        return False


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s %(levelname)-8s %(module)s: %(message)s',
        datefmt='%H:%M:%S'
    )
    log.info("Python: %s", sys.version.replace('\n', ' '))
    log.debug("logging using debug mode")

    client = TcpTxRx()
    if client.connect():
        print("connected; do tests here")
        # Example usage:
        # client.send("hello")            # text OK, will be encoded as UTF-8
        # client.send(b"\x01\x02\x03")    # bytes OK
        # data = client.receive(1024)
        # print("rx:", data)
        client.close()
    else:
        print("error connecting")
