from __future__ import print_function

import sys
from struct import pack, unpack, calcsize
import ctypes  # for bit fields
import os
import traceback
import threading
import time
import logging

# Perf counter compatible alias (Py3: perf_counter, Py2: clock/time)
try:
    perf_counter = time.perf_counter          # Py3
except AttributeError:                        # Py2
    perf_counter = time.clock if sys.platform.startswith('win') else time.time

log = logging.getLogger(__name__)

sys.path.insert(0, os.getcwd())  # for runtime root
from .tcp_tx_rx import TcpTxRx, socket


def is_bit_set(integer, position):
    return integer >> position & 1 > 0


class Nl2MsgType(object):
    OK = 1
    ERROR = 2
    GET_VERSION = 3  # datasize 0
    VERSION = 4
    GET_TELEMETRY = 5  # datasize 0
    TELEMETRY = 6
    GET_NEAREST_STATION = 11  # size 0, gets nearest coaster and station
    GET_STATION_STATE = 14  # size=8 (int32=coaster index, int32=station index)
    STATION_STATE = 15  # DataSize = 4
    SET_MANUAL_MODE = 16  # datasize 9
    DISPATCH = 17  # datasize 8
    SET_GATES = 18  # datasize 9
    SET_HARNESS = 19  # datasize 9
    SET_PLATFORM = 20  # datasize 9
    SET_FLYER_CAR = 21  # datasize 9
    LOAD_PARK = 24  # datasize 1 + string
    CLOSE_PARK = 25  # datasize 0
    SET_PAUSE = 27  # datasize 1
    RESET_PARK = 28  # datasize 1
    SELECT_SEAT = 29  # datasize = 16
    SET_ATTRACTION_MODE = 30  # datasize 1
    RECENTER_VR = 31  # datasize 0


class ConnState(object):
    DISCONNECTED, NOT_IN_SIM_MODE, READY = list(range(3))

    @staticmethod
    def text(state):
        return ("Not Connected", "Not in sim mode", "Ready")[state]


class Nl2_Link(object):
    def __init__(self):
        self.tcp = TcpTxRx()
        self.connection_state = ConnState.DISCONNECTED
        self._next_request_id = 1          # simple rolling uint32
        self.telemetry_latency_ms = None   # only for GET_TELEMETRY
        self._io_lock = threading.RLock()  # serialize send/recv cycles

    def connect(self):
        try:
            return self.tcp.connect()
        except Exception as e:
            print(e)
        return False

    def is_connected(self):
        # return true if tcp connected but may not be in sim mode
        return self.tcp.is_connected

    def send_msg(self, msg_type, data=None):
        """
        Send one NL2 message and return the payload bytes, or None on failure.

        Rules:
          - Only GET_TELEMETRY updates:
              * self.connection_state  (READY / NOT_IN_SIM_MODE)
              * self.telemetry_latency_ms  (int milliseconds)
          - For all other messages, connection_state is NOT modified here,
            except when there is NO reply (treated as DISCONNECTED).
        """
        # measure latency only for telemetry
        start = perf_counter() if msg_type == Nl2MsgType.GET_TELEMETRY else None

        # Build, send, and wait atomically to avoid interleaving replies
        with self._io_lock:
            if data is not None:
                frame = self._create_NL2_message(msg_type, self._get_msg_id(), data)
            else:
                frame = self._create_simple_message(msg_type, self._get_msg_id())
            self._send_raw(frame)
            reply = self._listen_for(msg_type)

        if reply is None:
            # No reply => assume link problem
            self.connection_state = ConnState.DISCONNECTED
            return None

        # Non-telemetry: just return bytes; state handled elsewhere
        if msg_type != Nl2MsgType.GET_TELEMETRY:
            return reply

        # --- Telemetry handling: update latency + state ---
        # Try parsing binary telemetry
        try:
            _ = unpack('>IIIIIIIIfffffffffff', reply)  # only need t[0] bit 0 to set state
        except Exception:
            # Some NL2 builds return text like "Not in play mode"
            try:
                sreply = reply.decode('utf-8', 'ignore')
            except Exception:
                sreply = None

            if sreply and ('Not in play mode' in sreply or 'Application is busy' in sreply):
                self.connection_state = ConnState.NOT_IN_SIM_MODE
                return None

            # Malformed/unexpected payload: treat as link trouble
            self.connection_state = ConnState.DISCONNECTED
            log.error("Telemetry parse failed (len=%d)", len(reply))
            return None

        # Latency for telemetry only
        if start is not None:
            self.telemetry_latency_ms = int((perf_counter() - start) * 1000.0)

        # Determine play mode from telemetry state bit (bit 0)
        try:
            t = unpack('>IIIIIIIIfffffffffff', reply)
            state_flags = t[0]
            if is_bit_set(state_flags, 0):
                self.connection_state = ConnState.READY
            else:
                self.connection_state = ConnState.NOT_IN_SIM_MODE
        except Exception:
            # If second unpack fails (shouldn't), keep previous state
            pass

        return reply

    def _send_raw(self, msg):
        try:
            self.tcp.send(msg)
        except Exception as e:
            print(str(e))

    def _listen_for(self, msg_id):
        """Return msg or None if no connection, invalid msg, or not in sim mode."""
        try:
            # Start byte
            startb = self._recv_exact(1)
            if not startb or startb[:1] != b'N':
                got = startb[:1] if startb else None
                log.error("sock header error: expected 0x4E got %r", got)
                return None

            # Header (8 bytes): >HIH
            hdr = self._recv_exact(8)
            if not hdr:
                log.error("incomplete NL2 header")
                return None
            try:
                msg_type, requestId, size = unpack('>HIH', hdr)
            except Exception as e:
                log.error("invalid NL2 header: %s", e)
                return None

            # Payload
            if size < 0:
                log.error("negative payload size: %d", size)
                return None
            data = self._recv_exact(size) if size else b''
            if size and not data:
                log.error("incomplete NL2 payload, expected %d bytes", size)
                return None

            # End byte
            endb = self._recv_exact(1)
            if not endb or endb[:1] != b'L':
                log.warning("Invalid message trailer (expected 'L')")
                return None

            return data

        except socket.timeout:
            log.error("timout waiting for Nl2 reply for msg id %d", msg_id)
        except Exception as e:
            log.error("error waiting for Nl2 reply: %s", str(e))
            print(traceback.format_exc())
        return None

    def _create_simple_message(self, msgId, requestId):
        # fields are: 'N' Message-Id request-Id 0 'L'
        result = pack('>cHIHc', b'N', msgId, requestId, 0, b'L')
        return result

    def _create_NL2_message(self, msgId, requestId, data):
        # fields are: 'N' Message-Id request-Id data-size data 'L'
        start = pack('>cHIH', b'N', msgId, requestId, len(data))
        end = pack('>c', b'L')
        result = start + data + end
        return result

    def _get_msg_id(self):
        rid = self._next_request_id & 0xFFFFFFFF
        self._next_request_id = (rid + 1) & 0xFFFFFFFF
        return rid

    def _recv_exact(self, nbytes):
        """
        Read exactly nbytes from the socket via TcpTxRx.receive(),
        looping until complete or a timeout/EOF occurs. Returns bytes or None.
        """
        total = bytearray()
        remaining = int(nbytes)
        while remaining > 0:
            chunk = self.tcp.receive(remaining)
            if not chunk:
                return None
            if not isinstance(chunk, (bytes, bytearray)):
                try:
                    chunk = bytes(chunk)
                except Exception:
                    return None
            total.extend(chunk)
            remaining = nbytes - len(total)
        return bytes(total)

    # ------ shared helpers for callers (to avoid duplication elsewhere) ------

    def _reply_to_text(self, reply):
        """Return a decoded UTF-8 string for logging/tests, or None."""
        try:
            if isinstance(reply, (bytes, bytearray)):
                return reply.decode("utf-8", "ignore")
        except Exception:
            pass
        return None

    def _is_not_in_play_text(self, s):
        """Detect common NL2 textual errors that mean not in play mode."""
        if not s:
            return False
        s = s.strip()
        return ("Not in play mode" in s) or ("Application is busy" in s)

    def _expect_len(self, reply, expected_len, label):
        """
        Validate that reply is bytes/bytearray of expected_len.
        Handles NL2 text errors by setting NOT_IN_SIM_MODE and returning None.
        Logs unexpected payloads and returns None on mismatch.
        """
        if not reply:
            log.debug("%s: no reply", label)
            return None

        if isinstance(reply, (bytes, bytearray)):
            if len(reply) == expected_len:
                return reply
            # Not the expected size: maybe a text error payload
            s = self._reply_to_text(reply)
            if self._is_not_in_play_text(s):
                self.connection_state = ConnState.NOT_IN_SIM_MODE
                log.debug("%s: %s", label, s.strip())
            else:
                try:
                    ln = len(reply)
                except Exception:
                    ln = "n/a"
                log.debug("%s: unexpected payload length %s", label, ln)
            return None

        # Non-bytes: try to see if it is a text error
        s = self._reply_to_text(reply)
        if self._is_not_in_play_text(s):
            self.connection_state = ConnState.NOT_IN_SIM_MODE
            log.debug("%s: %s", label, s.strip())
        else:
            log.debug("%s: unexpected non-bytes reply type %s", label, type(reply))
        return None

    def _unpack_exact(self, fmt, reply, label):
        """
        Combine size-check and struct.unpack. Returns tuple on success or None.
        """
        expected_len = calcsize(fmt)
        buf = self._expect_len(reply, expected_len, label)
        if buf is None:
            return None
        try:
            return unpack(fmt, buf)
        except Exception as e:
            log.error("%s: unpack failed: %s", label, e)
            return None
