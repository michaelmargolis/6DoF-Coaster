"""
 coaster_client control module for NoLimits2.
Copyright Michael Margolis, Middlesex University 2019; see LICENSE for software rights.
 
 module coordinates chair activity with logical coaster state 
This version requires NoLimits attraction license and NL ver 2.5.3.5 or later
"""

import os
import time
import ctypes
import tkinter.messagebox

from .nl2_messenger import Nl2Messenger, ConnState  
from .coaster_gui import CoasterGui
from .coaster_state import RideState, RideStateStr
from .serial_remote import SerialRemote
from platform_config import FRAME_RATE_SECS

JITTER_MARGIN = 0.005  # assume frame rate jitter under 5 ms
MAX_TELEM_AGE = max(0.0, FRAME_RATE_SECS - JITTER_MARGIN)


IS_RASPBERRYPI = False
if os.name == 'posix':
    if os.uname()[1] == 'raspberrypi':
        from . import local_control_itf
        IS_RASPBERRYPI = True

from .telemetry_logger import TelemetryLogger
logger = TelemetryLogger(False)

colors = ["green3", "orange", "red"]  # for warning level text

   
class CoasterEvent:
    ACTIVATED, DEACTIVATED, PAUSED, UNPAUSED, DISPATCHED, STOPPED, RESETEVENT = list(range(7))

CoasterEventStr = ("ACTIVATED", "DEACTIVATED", "PAUSED", "UNPAUSED", "DISPATCHED", "STOPPED", "RESETEVENT")

#  this state machine determines current coaster state from button and telemetry events
class State(object):
    def __init__(self, position_requestCB):
        self._state = None
        self._state = RideState.DEACTIVATED
        self.position_requestCB = position_requestCB
        self.is_chair_active = False
        self.prev_event = None  # only used for debug

    @property
    def state(self):
        """the 'state' property."""
        return self._state

    @state.setter
    def state(self, value):
        self._state = value

    def set_is_chair_active(self, isActive):
        self.is_chair_active = isActive

    def __str__(self):
        return self.string(self._state)

    @staticmethod
    def string(state):
        return RideStateStr[state]
        #return ("Disabled", "ReadyForDispatch", "Running", "Paused",
        #        "EmergencyStopped", "Resetting")[state]

    def coaster_event(self, event):
        if event != self.prev_event:
            self.prev_event = event
            print(("coaster event is",CoasterEventStr[event], "active state is", self.is_chair_active))
        if self.is_chair_active:
            if event == CoasterEvent.STOPPED and self._state != RideState.READY_FOR_DISPATCH:
                #  here if stopped at station
                self._state = RideState.READY_FOR_DISPATCH
                self._state_change()
            elif event == CoasterEvent.DISPATCHED and self._state != RideState.RUNNING:
                self._state = RideState.RUNNING
                self._state_change()
            elif event == CoasterEvent.PAUSED and self._state != RideState.PAUSED:
                self._state = RideState.PAUSED
                self._state_change()
            elif event == CoasterEvent.UNPAUSED and self._state == RideState.PAUSED:
                self._state = RideState.RUNNING
                self._state_change()
        else:
            #  things to do if chair has been disabled:
            if event == CoasterEvent.RESETEVENT and self._state != RideState.RESETTING:
                #  print "resetevent, state  = ", self._state
                if self._state == RideState.DEACTIVATED:
                    print("here if coaster moving at startup")
                self._state = RideState.RESETTING
                #  print "got reset event"
                self._state_change()
            if event == CoasterEvent.STOPPED and self._state != RideState.READY_FOR_DISPATCH:
                #  here if stopped at station
                # print "stopped at station while deactivated, state = ", self._state
                self._state = RideState.READY_FOR_DISPATCH
                self._state_change()
                #  print "state=", self.statecls

                

    def _state_change(self):
        if self.position_requestCB is not None:
            self.position_requestCB(self._state)  # tell user interface that state has changed

colors = ["green3","orange","red"] # for warning level text

class InputInterface(object):
    USE_GUI = True

    def __init__(self):
        self.cmd_func = None
        self.is_normalized = True
        self.current_pos = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        self.is_chair_activated = False
        self._ready_init_done = False

        # Use Nl2Messenger instead of legacy CoasterInterface
        self.nl2 = Nl2Messenger()
        self.nl2.set_telem_min_interval(MAX_TELEM_AGE)

        # Minimal legacy-compatible status shim so GUI code can stay the same
        class _Status(object):
            pass
        self.nl2.system_status = _Status()
        self.nl2.system_status.is_pc_connected = True
        self.nl2.system_status.is_nl2_connected = False
        self.nl2.system_status.is_in_play_mode = False
        self.nl2.system_status.is_paused = False

        self.gui = CoasterGui(self.dispatch, self.pause, self.reset, self.set_activate_state, self.quit)
        actions = {
            'detected remote': self.detected_remote,
            'activate': self.activate,
            'deactivate': self.deactivate,
            'pause': self.pause,
            'dispatch': self.dispatch,
            'reset': self.reset,
            'emergency_stop': self.emergency_stop,
            'intensity': self.set_intensity,
            'show_parks': self.show_parks,
            'scroll_parks': self.scroll_parks
        }
        self.RemoteControl = SerialRemote(actions)
        self.prev_movement_time = 0
        self.seat = 0
        self.speed = 0
        self.isLeavingStation = False
        self.coasterState = State(self.process_state_change)
        self.rootTitle = "NL2 Coaster Ride Controller"
        self.prev_heartbeat = 0

        # No heartbeat now; address passed in begin()
        self.server_address = None

        if IS_RASPBERRYPI and 'local_control_itf' in globals():
            self.local_control = local_control_itf.LocalControlItf(actions)
        else:
            self.local_control = None

        self.USE_UDP_MONITOR = False  # was True with heartbeat; off now

    def init_gui(self, master):
        if self.local_control is not None:
            if self.local_control.is_activated():
                while self.local_control.is_activated():
                    tkinter.messagebox.showinfo("EStop must be Down", "Flip Emergency Stop Switch down and press Ok to proceed")
        self.gui.init_gui(master)
        self.master = master

    def init_bitfield_gui(self, master):
        self.gui.init_gui_bitfield(master)

    def connection_msgbox(self, msg):
        result = tkinter.messagebox.askquestion(msg, icon='warning')
        return result != 'no'

    def _sleep_func(self, duration):
        start = time.time()
        while time.time() - start < duration:
            self.master.update_idletasks()
            self.master.update()

    def command(self, cmd):
        if self.cmd_func is not None:
            print("Requesting command:", cmd)
            self.cmd_func(cmd)

    # -------- Ride actions --------

    def dispatch(self):
        if self.is_chair_activated and self.coasterState.state == RideState.READY_FOR_DISPATCH:
            print('dispatch')
            self.coasterState.coaster_event(CoasterEvent.DISPATCHED)
            print("preparing to dispatch")

            # Chair/platform choreography as before
            self.command("ready")           # slow rise of platform
            self.command("unparkPlatform")
            time.sleep(.2)

            # Ensure we have a coaster/station context
            self.nl2.get_nearest_station()

            # Non-blocking prep loop on station bits (floor/harness/gates etc.)
            while not self.nl2.prepare_for_dispatch():
                self._sleep_func(1)

            # Now it's safe to dispatch
            self.nl2.dispatch()
            print("dispatched")

            self.prev_movement_time = time.time()
            self.isLeavingStation = True
            while self.nl2.is_train_in_station():
                time.sleep(.05)

            self.isLeavingStation = False
            print("left station")
            self.start_time = time.time()
            logger.start()

    def pause(self):
        print("in pause, ride state =", self.coasterState.state)
        if self.coasterState.state == RideState.RUNNING:
            self.nl2.set_pause(True)
            self.command("parkPlatform")
        elif self.coasterState.state == RideState.PAUSED:
            self.command("unparkPlatform")
            self.nl2.set_pause(False)
        elif self.coasterState.state == RideState.READY_FOR_DISPATCH:
            self.command("swellForStairs")

    def reset(self):
        self.nl2.reset_vr()

    def set_intensity(self, intensity_msg):
        self.command(intensity_msg)

    def show_parks(self, isPressed):
        self.gui.show_parks(isPressed)

    def scroll_parks(self, msg):
        if msg == '1':
            self.gui.scroll_parks('<Down>')
        elif msg == '-1':
            self.gui.scroll_parks('<Up>')
        else:
            print("in scroll_parks:", msg, type(msg))

    def emergency_stop(self):
       print("legacy emergency stop requested")
       self.deactivate()

    def set_activate_state(self, state):
        if state:
            self.activate()
        else:
            self.deactivate()

    def activate(self):
        # only activate if coaster is ready for dispatch
        print("In activate, resetting park in manual mode")
        self.nl2.reset_park(False)

        # wait until play mode (messenger updates connection_state via telemetry)
        while self.nl2.connection_state != ConnState.READY:
            print("waiting for play mode")
            time.sleep(0.5)
            self.service()

        self.nl2.ensure_manual_mode(True)
        print("selecting seat", self.seat)
        self.nl2.select_seat(self.seat)

        self.coasterState.coaster_event(CoasterEvent.RESETEVENT)
        self.is_chair_activated = True
        self.coasterState.set_is_chair_active(True)
        self.command("enable")
        self.gui.set_activation_buttons(True)
        self.gui.process_state_change(self.coasterState.state, True)
        self.RemoteControl.send(str(RideState.READY_FOR_DISPATCH))

    def deactivate(self):
       if self.coasterState.state == RideState.READY_FOR_DISPATCH:
           self.RemoteControl.send(str(RideState.DEACTIVATED))
       # disable motion output first
       self.command("disable")
       self.gui.set_activation_buttons(False)

       # if running, pause/park; if already paused, ensure parked
       if self.coasterState.state == RideState.RUNNING:
           self.pause()
       elif self.coasterState.state == RideState.PAUSED:
           self.command("parkPlatform")

       # mark deactivated
       self.is_chair_activated = False
       self.coasterState.set_is_chair_active(False)

       # notify state machine (no EMERGENCY here)
       self.coasterState.coaster_event(CoasterEvent.DEACTIVATED)
       self.gui.process_state_change(self.coasterState.state, False)
        
    def deactivateX(self):
        if self.coasterState.state == RideState.READY_FOR_DISPATCH:
            self.RemoteControl.send(str(RideState.DEACTIVATED))
        self.command("disable")
        self.gui.set_activation_buttons(False)
        self.is_chair_activated = False
        self.coasterState.set_is_chair_active(False)
        if self.coasterState.state in (RideState.RUNNING, RideState.PAUSED):
           # ensure paused, then mark deactivated
           if self.coasterState.state != RideState.PAUSED:
               self.pause()
        self.coasterState.coaster_event(CoasterEvent.DEACTIVATED)

        """
        if self.coasterState.state in (RideState.RUNNING, RideState.PAUSED):
            # ensure paused, mark ESTOP, then run recovery
            if self.coasterState.state != RideState.PAUSED:
                self.pause()
            print('emergency stop ')
            self.coasterState.coaster_event(CoasterEvent.ESTOPPED)
            # Kick off NL2 reset sequence to return to a dispatchable state
            self.recover_from_estop()
        else:
            # If we were already ESTOPPED (or anything else), ensure we reset NL2 as well
            if self.coasterState.state == RideState.EMERGENCY_STOPPED:
                self.recover_from_estop()
            else:
                self.coasterState.coaster_event(CoasterEvent.DEACTIVATED)
        """  
        self.gui.process_state_change(self.coasterState.state, False)

    def quit(self):
        self.command("quit")

    def detected_remote(self, info):
        if "Detected Remote" in info:
            self.set_remote_status_label((info, "green3"))
        elif "Looking for Remote" in info:
            self.set_remote_status_label((info, "orange"))
        else:
            self.set_remote_status_label((info, "red"))

    # -------- GUI status helpers --------

    def set_coaster_connection_label(self, label):
        self.gui.set_coaster_connection_label(label)

    def chair_status_changed(self, status):
        self.gui.chair_status_changed(status)

    def temperature_status_changed(self, status):
        self.gui.temperature_status_changed(status)

    def intensity_status_changed(self, status):
        self.gui.intensity_status_changed(status)

    def set_remote_status_label(self, label):
        self.gui.set_remote_status_label(label)

    def process_state_change(self, new_state):
        if new_state == RideState.READY_FOR_DISPATCH:
            if self.is_chair_activated:
                self.command("idle")  # slow drop of platform
                self.RemoteControl.send(str(RideState.READY_FOR_DISPATCH))
            else:
                self.RemoteControl.send(str(RideState.DEACTIVATED))  # at station but deactivated                
        else:
            self.RemoteControl.send(str(new_state))
        self.gui.process_state_change(new_state, self.is_chair_activated)

    def load_park(self, isPaused, park, seat):
        print("load park", park, "seat", seat)
        self.seat = int(seat)
        self.coasterState.coaster_event(CoasterEvent.RESETEVENT)
        self.gui.set_coaster_connection_label(("loading: " + park, "orange"))
        self._sleep_func(2)

        self.nl2.load_park(isPaused, park)

        # wait until play mode after load
        while self.nl2.connection_state != ConnState.READY:
            self.service()

        print("selecting seat", seat)
        self.nl2.select_seat(int(seat))
        self.coasterState.coaster_event(CoasterEvent.STOPPED)

    def fin(self):
        # client exit code goes here (no heartbeat to close now)
        pass

    def get_current_pos(self):
        return self.current_pos

    # -------- Startup / connection --------

    def begin(self, cmd_func, move_func, limits, server_ip="127.0.0.1", port=15151):
        self.cmd_func = cmd_func
        self.move_func = move_func
        self.server_address = (server_ip, port)

        # Set server address on the messenger
        self.nl2.tcp.tcp_address = (server_ip, int(port))

        self.nl2.begin()
        self.gui.set_park_callback(self.load_park)

        while not self.connect():
            self._sleep_func(0.5)

        # Pick nearest coaster/station so ops have context
        self.nl2.get_nearest_station()

        self.nl2.reset_park(False)
        return True

    def connect(self, wait_for_play=False, play_timeout=3.0):
        nl = self.nl2

        # TCP
        if not nl.tcp.is_connected:
            self.gui.set_coaster_status_label(["Connecting to NoLimits...", "red"])
            if not nl.connect():
                self.gui.set_coaster_connection_label(("No connection to NoLimits, is it running?", "red"))
                self._last_conn_state = ConnState.DISCONNECTED
                return False

        # Version probe (reachability even if telemetry/menu not available)
        ver = nl.get_nl2_version(force=True)
        if not ver:
            self.gui.set_coaster_connection_label(("Connected to PC, but NL2 not responding", "red"))
            return False

        # UI after first success
        self.gui.set_coaster_connection_label(["Connected to NoLimits v%s" % ver, "orange"])

        # Align telemetry cache age with your frame interval
        try:
            import platform_controller as pc
            frame = float(getattr(pc, "FRAME_RATE_SECS", 0.05))
        except Exception:
            frame = 0.05
        jitter = 0.005
        self._max_tm_age = max(0.0, frame - jitter)
        if hasattr(nl, "set_telem_min_interval"):
            nl.set_telem_min_interval(self._max_tm_age)
            
        if wait_for_play and nl.connection_state != ConnState.READY:
           nl.wait_for_ready(timeout=float(play_timeout), poll=0.1) 

        return True

    # -------- Runtime helpers --------


    def recover_from_estop_NoLongerUsed(self, timeout=10.0, poll=0.2):
       """
       Recover NL2 after an emergency stop while chair is deactivated.
       - Reset the park
       - Wait for play mode
       - Ensure manual mode
       - Refresh nearest station
       - Drive state machine: RESETEVENT -> (when train in station) STOPPED
       """
       # Enter RESETTING in the logical state machine (deactivated branch)
       self.coasterState.coaster_event(CoasterEvent.RESETEVENT)

       # Ask NL2 to reset the attraction (start_paused=False has matched prior usage)
       self.nl2.reset_park(False)

       # Wait until telemetry says READY (play mode)
       self.nl2.wait_for_ready(timeout=float(timeout), poll=float(poll))

       # Ensure we have a valid coaster/station and are in manual mode
       self.nl2.get_nearest_station()
       self.nl2.ensure_manual_mode(True)

       # If the train is in station, transition to READY_FOR_DISPATCH
       deadline = time.time() + float(timeout)
       while time.time() < deadline:
           if self.nl2.is_train_in_station():
               self.coasterState.coaster_event(CoasterEvent.STOPPED)
               break
           time.sleep(poll)

       # UI hint: we're recovered but not yet activated
       self.gui.set_coaster_status_label(["Coaster connected but not activated", "orange"])


    def check_is_stationary(self, speed):
        if speed < .5:
            if self.nl2.is_train_in_station():
                if self.isLeavingStation is False:
                    if self.coasterState.state == RideState.RUNNING:
                        print("train arrived in station")
                        logger.stop()
                        self.command("parkPlatform")
                        return True
            else:
                if self.isLeavingStation is True:
                    print("in station check, setting leaving flag to false")
                    self.isLeavingStation = False

            if time.time() - self.prev_movement_time > 3:
                return True
        else:
            self.prev_movement_time = time.time()
            self.gui.set_coaster_status_label([format("Coaster is Running %2.1fm/s" % speed), "green3"])
        return False

    def show_coaster_status(self):
        # refresh bitfield for GUI (legacy expects an int)
        if self.nl2.update_station_state():
            self.nl2.station_status = getattr(self.nl2, 'station_state_bitfield', 0)
            self.gui.update_bitfield(self.nl2.station_status)

        # update legacy 'system_status' shim from messenger
        self.nl2.system_status.is_nl2_connected = bool(self.nl2.tcp.is_connected)
        self.nl2.system_status.is_in_play_mode = (self.nl2.connection_state == ConnState.READY)
        self.nl2.system_status.is_paused = self.nl2.is_paused()

        if not self.nl2.system_status.is_pc_connected:
            self.gui.set_coaster_connection_label(("Not connected to VR server", "red"))
        if not self.nl2.system_status.is_nl2_connected:
            self.gui.set_coaster_connection_label(("Not connected to NoLimits server", "red"))
        elif not self.nl2.system_status.is_in_play_mode:
            self.gui.set_coaster_connection_label(("NoLimits is not in play mode", "red"))
        else:
            self.gui.set_coaster_connection_label(("Receiving NoLimits Telemetry", "green3"))

    def log(self, data):
        if logger.is_enabled and getattr(self.nl2, 'telemetry_msg', None):
            t = time.time() - self.start_time
            xyzrpy = ",".join('%0.2f' % item for item in data)
            tm = self.nl2.telemetry_msg
            quat = "%.4f,%.4f,%.4f,%.4f" % (tm.quatX, tm.quatY, tm.quatZ, tm.quatW)
            log_entry = "%.2f,%s,%s\n" % (t, xyzrpy, quat)
            logger.write(log_entry)

    def log_both(self, raw_data, processed_data):
        if logger.is_enabled:
            t = time.time() - self.start_time
            xyzrpy = ",".join('%0.2f' % item for item in raw_data)
            processed = ",".join('%0.2f' % item for item in processed_data)
            log_entry = format("%.2f,%s,%s\n" % (t, xyzrpy, processed))
            logger.write(log_entry)

    def service(self):
        if self.local_control:
            self.local_control.service()
        self.RemoteControl.service()

        if not self.connect():
            return

        nl = self.nl2

        # If not in READY, re-probe version each frame to keep reachability up-to-date
        if nl.connection_state != ConnState.READY:
            nl.get_nl2_version(force=True)

        # Telemetry at most once per frame
        max_age = getattr(self, "_max_tm_age", 0.045)
        tm = nl.get_telemetry_throttled(max_age=max_age)

        # State-driven UI updates (includes the "connected but not activated" message)
        cs = nl.connection_state
        if getattr(self, "_last_conn_state", None) != cs:
            self._last_conn_state = cs
            self._update_conn_ui(cs)

        # --- Drive ride-state transitions
        if tm and cs == ConnState.READY:
           self.speed = tm.speed
           nl.system_status.is_paused = nl.is_paused()

           if not nl.system_status.is_paused:
               if self.check_is_stationary(self.speed):
                   self.coasterState.coaster_event(CoasterEvent.STOPPED)
               else:
                   if self.coasterState.state == RideState.DEACTIVATED:
                       # moving at startup
                       self.coasterState.coaster_event(CoasterEvent.RESETEVENT)
                   else:
                       self.coasterState.coaster_event(CoasterEvent.UNPAUSED)
           else:
               self.coasterState.coaster_event(CoasterEvent.PAUSED)

           # send transform to motion if active and not waiting in station
           t6 = nl.get_transform()
           if t6 and len(t6) == 6:
               self.current_pos = t6
           if self.is_chair_activated and self.coasterState.state != RideState.READY_FOR_DISPATCH:
               if self.move_func:
                   self.move_func(self.current_pos)

        self.show_coaster_status()

    def _update_conn_ui(self, cs):
        if cs == ConnState.READY:            
            if not getattr(self, "_ready_init_done", False):
                self._on_enter_ready()            
            if not getattr(self, "is_chair_activated", False):
                self.gui.set_coaster_status_label(["Coaster connected but not activated", "orange"])
            else:
                lat = getattr(self.nl2, "telemetry_latency_ms", None)
                if isinstance(lat, int):
                    self.gui.set_coaster_status_label(["Receiving telemetry (~%d ms)" % lat, "green3"])
                else:
                    self.gui.set_coaster_status_label(["Receiving telemetry", "green3"])
        elif cs == ConnState.NOT_IN_SIM_MODE:
            self.gui.set_coaster_status_label(["Coaster connected but not in play mode", "orange"])
        else:
            self.gui.set_coaster_status_label(["Waiting for Connection to NoLimits", "red"])


    def _on_enter_ready(self):
       # make sure we’re focused on the right coaster/station
       self.nl2.get_nearest_station()
       # enforce manual mode early
       self.nl2.ensure_manual_mode(True)
       # if already in station, advance to READY_FOR_DISPATCH
       if self.nl2.is_train_in_station():
           self.coasterState.coaster_event(CoasterEvent.STOPPED)
       self._ready_init_done = True

    def serviceXX(self):
        if self.local_control:
            self.local_control.service()
        self.RemoteControl.service()

        if not self.connect(wait_for_play=False):
            return

        nl = self.nl2

        # If not READY, re-probe version each frame (cheap) to keep reachability signal fresh
        if nl.connection_state != ConnState.READY:
            nl.get_nl2_version(force=True)

        # Telemetry at most once per frame; reuse cached if younger than max age
        max_age = getattr(self, "_max_tm_age", 0.045)
        tm = nl.get_telemetry_throttled(max_age=max_age)

        # Update UI only on state transition
        cs = nl.connection_state
        if getattr(self, "_last_conn_state", None) != cs:
            self._last_conn_state = cs
            if cs == ConnState.READY:
                lat = getattr(nl, "telemetry_latency_ms", None)
                if isinstance(lat, int):
                    self.gui.set_coaster_status_label(["Receiving telemetry (~%d ms)" % lat, "green3"])
                else:
                    self.gui.set_coaster_status_label(["Receiving telemetry", "green3"])
            elif cs == ConnState.NOT_IN_SIM_MODE:
                self.gui.set_coaster_status_label(["Coaster connected but not in play mode", "orange"])
            else:
                self.gui.set_coaster_status_label(["Waiting for Connection to NoLimits", "red"])

        # Existing status/bitfield UI hooks
        self.show_coaster_status()

        # READY-only logic that uses tm goes here
        if tm and cs == ConnState.READY:
            pass


    def serviceXX(self):
        """
        Called every FRAME_RATE_SECS (~50 ms).
        Only this method polls telemetry (throttled); connect() never does.
        """
        if self.local_control:
            self.local_control.service()
        self.RemoteControl.service()

        if not self.connect(wait_for_play=False):
            return

        # Poll telemetry at most once per loop interval (or reuse last sample)
        max_age = getattr(self, "_max_tm_age", 0.045)  # fallback if not set yet
        tm = self.nl2.get_telemetry_throttled(max_age=max_age)

        # Update UI only when connection_state changes
        cs = self.nl2.connection_state
        if getattr(self, "_last_conn_state", None) != cs:
            self._last_conn_state = cs
            if cs == ConnState.READY:
                lat = getattr(self.nl2, "telemetry_latency_ms", None)
                if isinstance(lat, int):
                    self.gui.set_coaster_status_label(["Receiving telemetry (~%d ms)" % lat, "green3"])
                else:
                    self.gui.set_coaster_status_label(["Receiving telemetry", "green3"])
            elif cs == ConnState.NOT_IN_SIM_MODE:
                self.gui.set_coaster_status_label(["Coaster connected but not in play mode", "orange"])
            else:
                self.gui.set_coaster_status_label(["Waiting for Connection to NoLimits", "red"])

        # Your existing per-tick status and UI updates
        self.show_coaster_status()

        # If you need tm-specific logic while READY, use it here
        if tm and cs == ConnState.READY:
            pass  # e.g., state machine hooks, logging, etc.
        
    def serviceX(self):
        if self.local_control:
            self.local_control.service()
        self.RemoteControl.service()

        if self.connect():
            self.nl2.service()
            self.show_coaster_status()

            tm = self.nl2.get_telemetry()
            if tm:
                if self.nl2.connection_state == ConnState.READY:
                    # Show telemetry latency if available
                    lat = getattr(self.nl2, 'telemetry_latency_ms', None)
                    if isinstance(lat, int):
                        self.gui.set_coaster_connection_label(["Receiving Coaster Telemetry (~%d ms)" % lat, "green3"])
                    else:                      
                        self.gui.set_coaster_connection_label(("Receiving Coaster Telemetry", "green3"))

                    self.speed = tm.speed
                    self.nl2.system_status.is_paused = self.nl2.is_paused()

                    if not self.nl2.system_status.is_paused:
                        if self.check_is_stationary(self.speed):
                            self.coasterState.coaster_event(CoasterEvent.STOPPED)
                        else:
                            if self.coasterState.state == RideState.DEACTIVATED:
                                self.coasterState.coaster_event(CoasterEvent.RESETEVENT)
                            else:
                                self.coasterState.coaster_event(CoasterEvent.UNPAUSED)
                    else:
                        self.coasterState.coaster_event(CoasterEvent.PAUSED)

                    t6 = self.nl2.get_transform()
                    if t6 and len(t6) == 6:
                        self.current_pos = t6
                    if self.is_chair_activated and self.coasterState.state != RideState.READY_FOR_DISPATCH:
                        if self.move_func is not None:
                            self.move_func(self.current_pos)
                else:
                    self.gui.set_coaster_connection_label(("Coaster not in play mode", "red"))
            else:
                if self.nl2.tcp.is_connected:
                    errMsg = format("Telemetry error")
                    self.gui.set_coaster_connection_label((errMsg, "red"))
                else:
                    self.gui.set_coaster_connection_label(("No connection to NoLimits, is it running?", "red"))
