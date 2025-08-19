"""
NL2_messenger.py  Nl2 interface module
Copyright Michael Margolis, Middlesex University 2019; see LICENSE for software rights.
This version requires NoLimits attraction license and NL ver 2.5.3.5 or later
"""

import sys
from struct import pack, unpack, calcsize
import collections
import sys
import ctypes  # for bit fields
import os
import binascii  # only for debug
import traceback
import shlex

import time
# Perf counter compatible alias (Py3: perf_counter, Py2: clock/time)
try:
    perf_counter = time.perf_counter          # Py3
except AttributeError:                        # Py2
    perf_counter = time.clock if sys.platform.startswith('win') else time.time

sys.path.insert(0, os.getcwd())  # for runtime root

from .transform import Transform
from .nl2_link import Nl2_Link, Nl2MsgType, ConnState, is_bit_set

VERBOSE_LOG = True  # set true for verbose debug logging

import logging
log = logging.getLogger(__name__)


class StationStatus():
    # bit fields for station message
    bit_e_stop = 0x1
    bit_manual = 0x2
    bit_can_dispatch = 0x4
    bit_gates_can_close = 0x8
    bit_gates_can_open = 0x10
    bit_harness_can_close = 0x20
    bit_harness_can_open = 0x40
    bit_platform_can_raise = 0x80
    bit_platform_can_lower = 0x100
    bit_flyercar_can_lock = 0x200
    bit_flyercar_can_unlock = 0x400
    bit_train_in_station = 0x800
    bit_current_train_in_station = 0x1000


station_bit_flags = {
    StationStatus.bit_e_stop: "Emergency Stop",
    StationStatus.bit_manual: "Manual Mode",
    StationStatus.bit_can_dispatch: "Can Dispatch",
    StationStatus.bit_gates_can_close: "Gates Can Close",
    StationStatus.bit_gates_can_open: "Gates Can Open",
    StationStatus.bit_harness_can_close: "Harness Can Close",
    StationStatus.bit_harness_can_open: "Harness Can Open",
    StationStatus.bit_platform_can_raise: "Platform Can Raise",
    StationStatus.bit_platform_can_lower: "Platform Can Lower",
    StationStatus.bit_flyercar_can_lock: "Flyer Car Can Lock",
    StationStatus.bit_flyercar_can_unlock: "Flyer Car Can Unlock",
    StationStatus.bit_train_in_station: "Train In Station",
    StationStatus.bit_current_train_in_station: "Current Train In Station"
}


class Nl2Messenger(Nl2_Link):

    telemetryMsg = collections.namedtuple('telemetryMsg', 'state, frame, viewMode, coasterIndex,'
                                           'coasterStyle, train, car, seat, speed, posX, posY,'
                                           'posZ, quatX, quatY, quatZ, quatW, gForceX, gForceY, gForceZ')

    def __init__(self):
        super(Nl2Messenger, self).__init__()
        self.coaster = 0  # the current coaster
        self.station = 0  # current station
        self.station_msg_time = 0
        self.telemetry_msg = None  # most recent nl2 telemetry msg
        self.is_pause_state = False
        self.transform = Transform()
        self.station_state_bitfield = 0     # cached 32-bit flags
        self._station_ts = 0.0              # last successful poll time (perf_counter units)
        self._station_min_interval = 1.0    # default throttle (seconds)
        self.version_str = None             # last successful version string
        self.handshake_ok = False           # last version probe result
        self.telemetry_latency_ms = None    # set only on GET_TELEMETRY success
        self._last_telem_ts = 0.0
        self._telem_min_interval = 0.05     # default 50ms
        self._moving_speed_thresh = 0.5     # "moving" heuristic based on telemetry speed
        self._prev_conn_state = ConnState.DISCONNECTED
        self.desired_manual = True          # we always want manual when in play

        log.debug("Verbose debug logging is %s", VERBOSE_LOG)

    def begin(self):
        self.start_time = perf_counter()

    def service(self):
        # updates telemetry_msg and connection_state
        if self.is_connected():
            self.telemetry_msg = self.get_telemetry()
            # detect transition to READY
            cur = self.connection_state
            if self._prev_conn_state != cur and cur == ConnState.READY:
                self._on_ready_transition()
            self._prev_conn_state = cur

    def get_conn_state_str(self):  # only used for debug
        return ConnState.text(self.connection_state)

    def get_nl2_version(self, force=True):
        reply = self.send_msg(Nl2MsgType.GET_VERSION)
        if not reply:
            self.handshake_ok = False
            return None

        # Keep your existing parse logic (cccc with +48), plus safe fallbacks
        try:
            v0, v1, v2, v3 = unpack('cccc', reply)
            vs = "%c.%c.%c.%c" % (
                chr(ord(v0) + 48), chr(ord(v1) + 48),
                chr(ord(v2) + 48), chr(ord(v3) + 48)
            )
        except Exception:
            vs = None
            try:
                b = bytearray(reply)
                if len(b) >= 4:
                    vs = "%d.%d.%d.%d" % (b[0], b[1], b[2], b[3])
            except Exception:
                pass
            if vs is None:
                try:
                    s = reply.decode("ascii", "ignore").strip()
                    vs = s if s else None
                except Exception:
                    vs = None

        if not vs:
            self.handshake_ok = False
            return None

        self.version_str = vs
        self.handshake_ok = True
        if self.connection_state == ConnState.DISCONNECTED:
            self.connection_state = ConnState.NOT_IN_SIM_MODE
        return vs

    def set_telem_min_interval(self, seconds):
        try:
            self._telem_min_interval = max(0.0, float(seconds))
        except Exception:
            pass

    def get_telemetry_throttled(self, max_age=None, force=False):
        if max_age is None:
            max_age = self._telem_min_interval
        now = perf_counter()
        if (not force and
                self.telemetry_msg is not None and
                (now - self._last_telem_ts) < float(max_age)):
            return self.telemetry_msg
        tm = self.get_telemetry()
        if tm is not None:
            self._last_telem_ts = now
        return tm

    def get_telemetry(self):
        start = perf_counter()
        reply = self.send_msg(Nl2MsgType.GET_TELEMETRY)
        if not reply:
            return None

        # Try binary
        try:
            t = unpack('>IIIIIIIIfffffffffff', reply)
            # Note: telemetry_latency_ms is also set by the link layer; keeping this is harmless
            self.telemetry_latency_ms = int((perf_counter() - start) * 1000.0)
            self.telemetry_msg = self.telemetryMsg._make(t)
            state_flags = t[0]
            self.is_pause_state = bool(state_flags & 0x4)  # bit 2
            if state_flags & 0x1:
                self.connection_state = ConnState.READY
            else:
                self.connection_state = ConnState.NOT_IN_SIM_MODE
            return self.telemetry_msg
        except Exception:
            pass

        # Maybe a text reply
        try:
            s = reply.decode('utf-8', 'ignore')
        except Exception:
            s = None

        if s and ('Not in play mode' in s or 'Application is busy' in s):
            self.connection_state = ConnState.NOT_IN_SIM_MODE
            return None

        # Unexpected payload
        return None

    def get_transform(self):
        """ returns transform from latest telemetry msg as: xyzrpy
            get_telemetry should be called before get_transform     """
        if self.telemetry_msg:
            # transform is: [surge, sway, heave, roll, pitch, yaw]
            return self.transform.get_transform(self.telemetry_msg)
        return None

    def is_paused(self):
        """ returns True if was paused at most recent telemetry msg"""
        return self.is_pause_state

    def update_station_state(self):
        # returns True if state is available (ie, play mode)
        data = pack(">ii", self.coaster, self.station)
        reply = self.send_msg(Nl2MsgType.GET_STATION_STATE, data)
        res = self._unpack_exact(">I", reply, "update_station_state")
        if not res:
            return False
        self.station_state_bitfield = res[0]
        self._decode_station_state(self.station_state_bitfield)
        return True

    def _on_ready_transition(self):
        """Called once when we enter play mode (READY)."""
        self.get_nearest_station()  # ignore None result; indexes remain as-is on failure
        # Enforce manual mode and verify
        self.ensure_manual_mode(self.desired_manual)

    def _wait_station(self, expect_set=None, expect_clear=None, timeout=4.0, poll=0.05):
        """
        Poll station bits until conditions are met or timeout.
        expect_set:   iterable of masks that must be 1
        expect_clear: iterable of masks that must be 0
        """
        end = perf_counter() + float(timeout)
        expect_set = tuple(expect_set or ())
        expect_clear = tuple(expect_clear or ())

        while perf_counter() < end:
            if not self._ensure_station_state(force=True):
                time.sleep(poll)
                continue
            bf = self.station_state_bitfield
            ok = all(bf & m for m in expect_set) and all((bf & m) == 0 for m in expect_clear)
            if ok:
                return True
            time.sleep(poll)
        return False

    def prepare_for_dispatch(self):
        FRESH = 0.2

        # Ensure manual mode
        if not self.ensure_manual_mode(True):
            self.set_manual_mode(True)
            self._ensure_station_state(force=True)
            return False

        # If we can dispatch already, we're done.
        if self.get_station_status(StationStatus.bit_can_dispatch, max_age=FRESH):
            return True

        # 1) Close gates
        if self.get_station_status(StationStatus.bit_gates_can_close, max_age=FRESH):
            self.set_gates(False)  # close
            # Wait for "closed" condition: can_open=1, can_close=0
            self._wait_station(
                expect_set=[StationStatus.bit_gates_can_open],
                expect_clear=[StationStatus.bit_gates_can_close]
            )
            return False

        # 2) Close harness
        if self.get_station_status(StationStatus.bit_harness_can_close, max_age=FRESH):
            self.set_harness(False)  # close
            # Wait for "closed": can_open=1, can_close=0
            self._wait_station(
                expect_set=[StationStatus.bit_harness_can_open],
                expect_clear=[StationStatus.bit_harness_can_close]
            )
            return False

        # 3) Lock flyer (flyers like Pterodactyl)
        if self.get_station_status(StationStatus.bit_flyercar_can_lock, max_age=FRESH):
            self.lock_flyer()
            # Wait for "locked": can_unlock=1, can_lock=0
            self._wait_station(
                expect_set=[StationStatus.bit_flyercar_can_unlock],
                expect_clear=[StationStatus.bit_flyercar_can_lock]
            )
            return False

        # 4) Lower platform
        if self.get_station_status(StationStatus.bit_platform_can_lower, max_age=FRESH):
            self.set_floor(True)  # lower
            # Wait for "lowered": can_raise=1, can_lower=0
            self._wait_station(
                expect_set=[StationStatus.bit_platform_can_raise],
                expect_clear=[StationStatus.bit_platform_can_lower]
            )
            return False

        # If nothing to do, check can_dispatch again
        return self.get_station_status(StationStatus.bit_can_dispatch, max_age=FRESH)

    def dispatch(self, coaster=None, station=None):
        if coaster is None:
            coaster = self.coaster
        if station is None:
            station = self.station
        data = pack('>ii', coaster, station)  # coaster, station
        _ = self.send_msg(Nl2MsgType.DISPATCH, data)

    def get_nearest_station(self):
        """
        Query NL2 for the nearest coaster/station and update self.coaster/self.station.
        Returns (coaster, station) on success, or None on failure.
        """
        reply = self.send_msg(Nl2MsgType.GET_NEAREST_STATION)
        res = self._unpack_exact(">ii", reply, "get_nearest_station")
        if not res:
            return None
        coaster, station = res
        self.coaster, self.station = coaster, station
        log.debug("Nearest coaster: %d, nearest station: %d", coaster, station)
        return coaster, station

    def set_gates(self, mode=True):  # True opens, False closes
        data = pack('>ii?', self.coaster, self.station, mode)
        _ = self.send_msg(Nl2MsgType.SET_GATES, data)

    def set_harness(self, mode=True):  # True opens, False closes
        data = pack('>ii?', self.coaster, self.station, mode)
        _ = self.send_msg(Nl2MsgType.SET_HARNESS, data)

    def set_floor(self, mode=True):  # True lowers, False raises
        data = pack('>ii?', self.coaster, self.station, mode)
        _ = self.send_msg(Nl2MsgType.SET_PLATFORM, data)

    def set_flyer(self, mode=True):  # True on, False off
        data = pack('>ii?', self.coaster, self.station, mode)
        _ = self.send_msg(Nl2MsgType.SET_FLYER_CAR, data)

    def lock_flyer(self):
        return self.set_flyer(False)  # lock == False (closed/secured)

    def unlock_flyer(self):
        return self.set_flyer(True)   # unlock == True

    def set_manual_mode(self, mode=True):
        data = pack('>ii?', self.coaster, self.station, mode)  # True sets manual mode, false sets auto
        _ = self.send_msg(Nl2MsgType.SET_MANUAL_MODE, data)

    def reset_vr(self):
        _ = self.send_msg(Nl2MsgType.RECENTER_VR)
        log.info("reset rift")

    def load_park(self, isPaused, park):
        path = park.encode('utf-8')
        data = pack('>?', isPaused) + path
        reply = self.send_msg(Nl2MsgType.LOAD_PARK, data)
        if reply is None:
            return False

        # Ensure we are in play mode and have a station context
        self.wait_for_ready(timeout=10.0)
        self.get_nearest_station()

        # Switch to manual and verify
        self.ensure_manual_mode(True)
        return True

    def close_park(self):
        _ = self.send_msg(Nl2MsgType.CLOSE_PARK)

    def set_pause(self, isPaused=True):
        data = pack('>?', isPaused)  # pause if arg is True
        _ = self.send_msg(Nl2MsgType.SET_PAUSE, data)

    def unpause(self):
        self.set_pause(False)

    def reset_park(self, start_paused=True):
        data = pack('>?', start_paused)  # start paused if arg is True
        _ = self.send_msg(Nl2MsgType.RESET_PARK, data)

    def select_seat(self, seat):
        data = pack('>iiii', self.coaster, 0, 0, seat)  # coaster, train, car, seat
        _ = self.send_msg(Nl2MsgType.SELECT_SEAT, data)

    def set_attraction_mode(self, state=True):
        data = pack('>?', state)   # enable mode if state True
        _ = self.send_msg(Nl2MsgType.SET_ATTRACTION_MODE, data)

    def get_station_status(self, mask, max_age=None, force=False):
        """
        True iff 'mask' bit is set. Ensures the cache is reasonably fresh.
        - max_age seconds: None uses adaptive (fast when stationary, slow when moving).
        - force=True bypasses cache and polls immediately.
        """
        if not self._ensure_station_state(max_age=max_age, force=force):
            return False
        return bool(self.station_state_bitfield & mask)

    def _decode_station_state(self, state):
        self.e_stop = is_bit_set(state, 0)
        self.manual_dispatch = is_bit_set(state, 1)
        self.can_dispatch = is_bit_set(state, 2)
        self.can_close_gates = is_bit_set(state, 3)
        self.can_open_gates = is_bit_set(state, 4)
        self.can_close_harness = is_bit_set(state, 5)
        self.can_open_harness = is_bit_set(state, 6)
        self.can_raise_platform = is_bit_set(state, 7)
        self.can_lower_platform = is_bit_set(state, 8)
        self.can_lock_flyer_car = is_bit_set(state, 9)
        self.can_unlock_flyer_car = is_bit_set(state, 10)
        self.train_in_station = is_bit_set(state, 11)
        self.train_in_station_is_current = is_bit_set(state, 12)

    def is_train_in_station(self):
        if self.update_station_state():
            ret = self.train_in_station and self.train_in_station_is_current
            return ret
        else:
            return False

    def _ensure_station_state(self, max_age=None, force=False):
        """
        Ensure station_state_bitfield is recent enough.
        - max_age: None -> adaptive throttle; else seconds
        - force: True -> always poll now
        Returns True if we have a (possibly newly) updated bitfield.
        """
        now = perf_counter()
        age = now - getattr(self, "_station_ts", 0.0)

        if max_age is None:
            max_age = 0.25 if not self._is_moving() else 1.0

        if not force and age <= max_age:
            return True  # cached is fresh enough

        data = pack(">ii", self.coaster, self.station)
        reply = self.send_msg(Nl2MsgType.GET_STATION_STATE, data)
        res = self._unpack_exact(">I", reply, "_ensure_station_state")
        if not res:
            return False

        self.station_state_bitfield = res[0]
        self._station_ts = now
        return True

    def _is_moving(self):
        tm = getattr(self, 'telemetry_msg', None)
        return bool(tm and abs(getattr(tm, 'speed', 0.0)) >= self._moving_speed_thresh)

    def is_manual(self, max_age=0.5):
        """True if station is in manual mode bit."""
        return self.get_station_status(StationStatus.bit_manual, max_age=max_age)

    def ensure_manual_mode(self, desired=True, retries=3, wait=0.2):
        """
        Ensure manual mode matches `desired` (True=manual, False=auto).
        Verifies via station bit and retries a few times.
        Returns True if final state matches desired else False.
        """
        target = bool(desired)
        for _ in range(int(retries)):
            cur = self.is_manual(max_age=0.25)
            if cur == target:
                return True
            # send request, wait, refresh
            self.set_manual_mode(target)
            time.sleep(wait)
            self._ensure_station_state(force=True)
        # final check
        return self.is_manual(max_age=0.25)

    def wait_for_ready(self, timeout=8.0, poll=0.2):
        """
        Poll telemetry until ConnState.READY or timeout.
        Returns True if READY, else False.
        """
        deadline = perf_counter() + float(timeout)
        while perf_counter() < deadline:
            self.get_telemetry()
            if self.connection_state == ConnState.READY:
                return True
            time.sleep(poll)
        return False

    def print_station_state(self):
        """
        Print the station bitfield flags as "<Label> <0|1>" lines.
        Uses global station_bit_flags {mask: "Label"} and calls update_station_state().
        Returns True if state was printed, False otherwise.
        """
        if not self.update_station_state():
            print("station state unavailable")
            return False

        bf = getattr(self, 'station_state_bitfield', 0)
        # sort by label (the dict's value) for a stable, readable order
        for mask, label in sorted(station_bit_flags.items(), key=lambda kv: kv[1]):
            print("%s %d" % (label, 1 if (bf & mask) else 0))
        return True
