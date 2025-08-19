"""
platform_output module drives chair with Festo UDP messages

Copyright Michael Margolis, Middlesex University 2019; see LICENSE for software rights.

Supports Festo controllers using easyip port
see: https://github.com/kmpm/fstlib

The module can also drive a serial platform for testing or demo

Muscle calculations use the following formula to convert % contraction to pressure:
  pressure = 35 * percent*percent + 15 * percent + .03  # assume 25 Newtons for now
percent is calculated as follows:
 percent =  1- (distance + MAX_MUSCLE_LEN - MAX_ACTUATOR_LEN)/ MAX_MUSCLE_LEN
"""

import sys
import socket
import traceback
import math
import time
import copy
import numpy as np
from output.output_gui import OutputGui
import platform_config as cfg

TESTING = False
if not TESTING:
    # sys.path.insert(0, './fstlib')
    from output.fstlib import easyip

PRINT_MUSCLES = False
PRINT_PRESSURE_DELTA = True
WAIT_FESTO_RESPONSE = False

# modify following two lines for MEng output to monitor client
MONITOR_PORT = 10020 # echo actuator lengths to this port
MONITOR_ADDR = ('127.0.0.1', MONITOR_PORT)

if TESTING:
    print("THIS IS TESTING MODE, no output to Festo!!!")
    FST_ip = 'localhost'

OutSerialPort = None # 'COM9'
try: OutSerialPort  #  enable serial if defined in config file
except NameError: OutSerialPort = None

if OutSerialPort is not None:
    IS_SERIAL = True
    print("Using serial port", OutSerialPort,"for platform output")
    import serial
else:
    IS_SERIAL = False
    if not TESTING:
        # Set the socket parameters
        FST_ip =  cfg.Festo_IP_ADDR  # default is '192.168.0.10'
        FST_port = cfg.Festo_Port   # default is 995
        bufSize = 1024
        print("Using Festo controller socket at",  FST_ip, FST_port)

class OutputInterface(object):

    #  IS_SERIAL is set True if using serial platform simulator for testing
    global IS_SERIAL

    def __init__(self):
        np.set_printoptions(precision=2, suppress=True)
        #### self.LIMITS = platform_1dof_limits  # max movement in a single dof
        self.platform_disabled_pos = np.empty(6)   # position when platform is disabled
        self.platform_winddown_pos = np.empty(6)  # position for attaching stairs
        self.isEnabled = False  # platform disabled if False
        self.prev_pos = [0, 0, 0, 0, 0, 0]  # requested distances stored here
        self.requested_pressures = [0,0,0,0,0,0]
        self.actual_pressures =  [0,0,0,0,0,0]
        self.pressure_percent = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        self.prev_time = time.perf_counter()
        self.netlink_ok = False # True if festo responds without error
        self.ser = None
        self.monitor_client = None
        if MONITOR_PORT:
            self.monitor_client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            print("platform monitor output on port", MONITOR_PORT)
        if IS_SERIAL:
            #  configure the serial connection
            try:
                self.ser = serial.Serial(port=OutSerialPort, baudrate=57600, timeout=1)
                print("Serial Output simulator opened on ", OutSerialPort)
            except:
                print("unable to open Out simulator serial port", OutSerialPort)
        elif not TESTING:
            self.FSTs = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.FST_addr = (FST_ip, FST_port)
            self.FSTs.bind(('0.0.0.0', 0))
            self.FSTs.settimeout(1)  # timout after 1 second if no response
        print("")
        self.prevMsg = []
        self.use_gui = False # defualt is no gui
        self.activate_piston_flag = 0  # park piston is extended when flag set to 1, parked when 0
        self.client_zpos = 0
        
    def init_gui(self, master):
        self.gui = OutputGui()
        self.gui.init_gui(master, self.min_actuator_len, self.max_actuator_len)
        self.use_gui = True

    def begin(self, min_actuator_len, max_actuator_len, disabled_length, propping_len, fixed_len, loaded_weight):
        self.min_actuator_len = min_actuator_len
        self.max_actuator_len = max_actuator_len
        self.platform_disabled_pos.fill(disabled_length)   # position when platform is disabled (propped)
        self.platform_winddown_pos.fill(propping_len)      # position for attaching stairs or moving prop
        self.fixed_len = fixed_len
        self.loaded_weight = loaded_weight

    def fin(self):
        """
        free resources used by ths module
        """
        global IS_SERIAL
        if IS_SERIAL:
            try:
                if self.ser and self.ser.isOpen():
                    self.ser.close()
            except:
                pass
        else:
            if not TESTING:
                self.FSTs.close()

    def get_platform_pos(self):
        """
        get coordinates of fixed platform attachment points
        """
        return platform_pos

    def get_output_status(self):
        """
        return string describing output status
        """
        if TESTING:
            return ("Test mode, no output to Festo", "red")
        else:
            if WAIT_FESTO_RESPONSE:
                ###self._get_pressure()
                if not self.netlink_ok:
                    return ("Festo network error (check ethernet cable and festo power)", "red")
                else:    
                    bad = []
                    if 0 in self.actual_pressures:
                        for idx, v in enumerate(self.actual_pressures):
                           if v == 0:
                              bad.append(idx)
                        if len(bad) == 6:
                           return ("Festo Pressure Zero on all muscles", "red")
                        else:
                           bad_str = ','.join(map(str, bad))                   
                           return ("Festo Pressure Zero on muscles: " + bad_str, "red")
                    elif any(p < 10 for p in self.pressure_percent):
                        return ("Festo Pressure is Low", "orange")
                    elif any(p < 10 for p in self.pressure_percent):
                        return ("Festo Pressure is High", "orange")
                    else:
                        return ("Festo Pressure is Good", "green")  # todo, also check if pressure is low
            else:        
                return ("Festo controller responses not being used", "orange")

    def set_payload(self, payload_kg):
        """
        set total weight in killograms
        """
        self.loaded_weight = payload_kg

    def set_enable(self, state, actuator_lengths):
        """
        enable platform if True, disable if False
        
        actuator_lengths are those needed to achieve current client orientation
        """
        if self.isEnabled != state:
            self.isEnabled = state
            print("Platform enabled state is", state)
            if state:
                pass
                #  self._slow_move(self.platform_disabled_pos, actuator_lengths, 1000)
            else:
                self.activate_piston_flag = 0
                self._slow_move(actuator_lengths, self.platform_disabled_pos, 1000)

    """
    def move_to_limits(self, pos):

        self.moveTo([p*l for p, l in zip(pos, self.limits)])
    """

    def move_to_idle(self, client_pos, zpos):
       print("move to idle pos")
       self.client_zpos = zpos
       print("zpos=", self.client_zpos)
       self._slow_move(client_pos, self.platform_disabled_pos, 1000)


    def move_to_ready(self, client_pos, zpos):
        print("move to ready pos")
        self.client_zpos = zpos
        print("zpos=", self.client_zpos)
        self._slow_move(self.platform_disabled_pos, client_pos, 1000)

    def swell_for_access(self, interval, disengage_prop):
        """
        Briefly raises platform high enough to insert access stairs
        if disengage is true then activate pistion to detach prop
        else if false, activate pistion
        
        moves even if disabled
        Args:
          interval (int): time in ms before dropping back to start pos
        """ 
        print("Start swelling for access")
        self._slow_move(self.platform_disabled_pos, self.platform_winddown_pos, 1000)
        time.sleep(interval)
        self._slow_move(self.platform_winddown_pos, self.platform_disabled_pos, 1000)
        print("Finished swelling for access")
        

    def park_platform(self, state):
        delay=0
        if state:
            self.activate_piston_flag = 0
            delay= 0.5
            print(format("Setting flag to activate piston to 0, delay= %0.1f" % (delay)))
        else:
            self.activate_piston_flag = 1
            print("setting flag to activate piston to 1")
        print("Sending last requested pressure with new piston state")
        self._send(self.requested_pressures[:6])  # current prop state will be appended in _send
        if delay > 0: time.sleep(delay)
        print("Todo in output park_platform, check if more delay is needed")

    def move_platform(self, lengths):  # lengths is list of 6 actuator lengths as millimeters
        """
        Move all platform actuators to the given lengths
        
        Args:
          lengths (float): numpy array comprising 6 actuator lengths
        """

        """
        clipped = []
        for idx, l in enumerate(lengths):
            if l < MIN_ACTUATOR_LEN:
                lengths[idx] = MIN_ACTUATOR_LEN
                clipped.append(idx)
            elif l > MAX_ACTUATOR_LEN:
                lengths[idx] = MAX_ACTUATOR_LEN
                clipped.append(idx)
        if len(clipped) > 0:
            pass
            #  print "Warning, actuators", clipped, "were clipped"
        """
        if self.isEnabled:
            global IS_SERIAL
            if IS_SERIAL:
                self._move_to_serial(lengths)
            else:
                self._move_to(lengths)  # only fulfill request if enabled
        """
        else:
            print "Platform Disabled"
        """

    def show_muscles(self, position_request, muscles):
        if self.use_gui:
           self.gui.show_muscles(position_request, muscles, self.pressure_percent)
        """
        if self.monitor_client:
            # echo position requests to monitor port if enabled
             xyzrpy = ",".join('%0.3f' % item for item in position_request)
             lengths = ",".join('%0.1f' % item for item in muscles)
             #msg = "monitor," + xyzrpy + ',' + lengths +'\n'
             msg = "request," + xyzrpy  +'\n'
             #print msg
             # send pos as mm and radians, actuator lengths as mm
             self.monitor_client.sendto(msg, MONITOR_ADDR)
        """

    def echo_requests_to_udp(self, position_request):
        if self.monitor_client:
            # echo position requests to monitor port if enabled
             xyzrpy = ",".join('%0.3f' % item for item in position_request)
             msg = "request," + xyzrpy  +'\n'
             print(msg)
             # send pos as mm and radians, actuator lengths as mm
             self.monitor_client.sendto(msg, MONITOR_ADDR)

    #  private methods
    def _slow_move(self, start, end, duration):
        global IS_SERIAL
        if IS_SERIAL:
            move_func = self._move_to_serial
        else:
            move_func = self._move_to
       
        #  caution, this moves even if disabled
        interval = 50  # time between steps in ms
        steps = duration / interval
        if steps < 1:
            self.move(end)
        else:
            current = start
            # print "moving from", start, "to", end, "steps", steps
            # print "percent", (end[0]/start[0]) * 100
            delta = [float(e - s)/steps for s, e in zip(start, end)]
            for step in range(int(steps)):
                current = [x + y for x, y in zip(current, delta)]
                move_func(copy.copy(current))
                # self.show_muscles([0,0,0,0,0,0], current)
                #  self.echo_slow_move(start[0], end[0], current[0])
                time.sleep(interval / 1000.0)

    def echo_slow_move(self, start, end, current):
        #increment =  max_z * current/self.max_actuator_len
        increment = (start - current) * 0.7
        z =  self.client_zpos + increment
        #  print start, end, current, current/self.max_actuator_len, max_z * current/self.max_actuator_len
        #print "udp slow move", z, "start", start, "end", end, "inc", increment,"percent", current/self.max_actuator_len,"current", current
        print("udp slow move", z, "start", start, "end", end, "inc", increment, "current", current)
        self.echo_requests_to_udp([0,0, z, 0, 0, 0])

    def _move_to_serial(self, lengths):
        # msg = "xyzrpy," + ",".join([str(round(item)) for item in lengths])
        print(lengths)
        #  payload =   ",".join('%0.1f' % item for item in lengths)
        # this is a hack to test nextgen model
        # l = [(((i-200) *1 )+0) for i in lengths]        
        for idx, l in enumerate(lengths):
            min_len = 285 # todo, should be self.min_actuator_len
            lengths[idx] =  np.clip(l-min_len,0,100) 
        payload =   ",".join('%d' % item for item in lengths)
        print(payload)
        
        if payload != self.prevMsg:
            # print "payload: ", payload, "org", lengths
            self.prevMsg = payload
        if self.ser and self.ser.isOpen():
            self.ser.write("lengths," + payload + '\n')
            print("lengths," + payload)
            #  print self.ser.readline()
            if (self.ser.inWaiting()>0): #if incoming bytes are waiting to be read from the serial input buffer
                data_str = self.ser.read(self.ser.inWaiting()).decode('ascii') #read the bytes and convert from binary array to ASCII
                print(data_str)
        else:
            print("serial not open")

    def _move_to(self, lengths):
        #  print "lengths:\t ", ",".join('  %d' % item for item in lengths)
        now = time.perf_counter()
        timeDelta = now - self.prev_time
        self.prev_time = now
        load_per_muscle = self.loaded_weight / 6  # if needed we could calculate individual muscle loads
        pressure = []
        #print "LENGTHS = ",lengths
        # print format("%0.3f,%s,%s" % (timeDelta,",".join('%d' % item for item in lengths), "Unpropped" if self.activate_piston_flag else "Propped"))
        for idx, len in enumerate(lengths):
            pressure.append(int(1000*self._convert_MM_to_pressure(idx, len-self.fixed_len, timeDelta, load_per_muscle)))
        self._send(pressure)

    def _convert_MM_to_pressure(self, idx, muscle_len, timeDelta, load):
        #  returns pressure in bar
        #  calculate the percent of muscle contraction to give the desired distance
        percent = (self.max_actuator_len - self.fixed_len - muscle_len) / float(self.max_actuator_len - self.fixed_len)
        #  check for range between 0 and .25
        #  print "muscle Len =", muscle_len, "percent =", percent
        """
        if percent < 0 or percent > 0.25:
            print "%.2f percent contraction out of bounds for muscle length %.1f" % (percent, muscle_len)
        """
        distDelta = muscle_len-self.prev_pos[idx]  # the change in length from the previous position
        accel = (distDelta/1000) / timeDelta  # accleration units are meters per sec

        if distDelta < 0:
            force = load * (1-accel)  # TODO  here we assume force is same magnitude as expanding muscle ???
            #  TODO modify formula for force
            #  pressure = 30 * percent*percent + 12 * percent + .01  # assume 25 Newtons for now
            pressure = 35 * percent*percent + 15 * percent + .03  # assume 25 Newtons for now
            if PRINT_MUSCLES:
                print(("muscle %d contracting %.1f mm to %.1f, accel is %.2f, force is %.1fN, pressure is %.2f"
                      % (idx, distDelta, muscle_len, accel, force, pressure)))
        else:
            force = load * (1+accel)  # force in newtons not yet used
            #  TODO modify formula for expansion
            pressure = 35 * percent*percent + 15 * percent + .03  # assume 25 Newtons for now
            if PRINT_MUSCLES:
                print(("muscle %d expanding %.1f mm to %.1f, accel is %.2f, force is %.1fN, pressure is %.2f"
                      % (idx, distDelta, muscle_len, accel, force, pressure)))

        self.prev_pos[idx] = muscle_len  # store the muscle len
        MAX_PRESSURE = 6.0 
        MIN_PRESSURE = .05  # 50 millibar is minimin pressure
        pressure = max(min(MAX_PRESSURE, pressure), MIN_PRESSURE)  # limit range 
        return pressure

    def _send(self, muscle_pressures):
        self.requested_pressures = muscle_pressures  # store this for display if required
        if not TESTING:
            try:
                #print format("Muscle pressures %s,%s" % (",".join('%d' % item for item in muscle_pressures), "Unpropped" if self.activate_piston_flag else "Propped"))
                muscle_pressures.append(self.activate_piston_flag)
                packet = easyip.Factory.send_flagword(0, muscle_pressures)
                try:
                    self._send_packet(packet)
                    #  print "festo output:", packet, FST_port
                    if WAIT_FESTO_RESPONSE:
                        self.actual_pressures = self._get_pressure()
                        delta = [act - req for req, act in zip(muscle_pressures, self.actual_pressures)]
                        # todo - next line needs changing because park flag now appended to list
                        self.pressure_percent = [int(d * 100 / req) for d, req in zip(delta, muscle_pressures)]
                        if PRINT_PRESSURE_DELTA:
                            print(muscle_pressures, delta, self.pressure_percent)

                except socket.timeout:
                    print("timeout waiting for replay from", self.FST_addr)

            except:
                e = sys.exc_info()[0]
                s = traceback.format_exc()
                print("error sending to Festo", e, s)

    def _send_packet(self, packet):
        if not TESTING:
            data = packet.pack()
            #  print "sending to", self.FST_addr
            self.FSTs.sendto(data, self.FST_addr)
            if WAIT_FESTO_RESPONSE:
                #  print "in sendpacket,waiting for response..."
                data, srvaddr = self.FSTs.recvfrom(bufSize)
                resp = easyip.Packet(data)
                #  print "in senddpacket, response from Festo", resp
                if packet.response_errors(resp) is None:
                    self.netlink_ok = True
                    #  print "No send Errors"
                else:
                    self.netlink_ok = False
                    print("errors=%r" % packet.response_errors(resp))
            else:
                resp = None
            return resp

    def _get_pressure(self):
        # first arg is the number of requests your making. Leave it as 1 always
        # Second arg is number of words you are requesting (probably 6, or 16)
        # third arg is the offset.
        # words 0-5 are what you sent it.
        # words 6-9 are not used
        # words 10-15 are the current values of the presures
        # packet = easyip.Factory.req_flagword(1, 16, 0)
        if TESTING:
            return self.requested_pressures  # TEMP for testing
        #  print "attempting to get pressure"
        try:
            packet = easyip.Factory.req_flagword(1, 6, 10)
            resp = self._send_packet(packet)
            values = resp.decode_payload(easyip.Packet.DIRECTION_REQ)
            #  print list(values)
            return list(values)
        except socket.timeout:
            print("timeout waiting for Pressures from Festo")
        return [0,0,0,0,0,0]
