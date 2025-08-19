"""
Serial remote control
Copyright Michael Margolis, Middlesex University 2019; see LICENSE for software rights.
 """

import sys
import serial
import time
import serial.tools.list_ports
import threading
import os
from queue import Queue


class SerialRemote(object):
    """ provide action strings associated with buttons on serial remote control."""
    auto_conn_str = "MdxRemote_V1"  # remote responds with this when promted for version

    def __init__(self, actions):
        """ Call with dictionary of action strings.
 
        Keys are the strings sent by the remote,
        values are the functons to be called for the given key.
        """
        self.ser = None
        self.connected = False
        self.ser_buffer = ""
        self.baud_rate = 57600
        self.timeout_period = 2
        self.actions = actions
        self.RxQ = Queue()
        t = threading.Thread(target=self.rx_thread, args=(self.ser, self.RxQ,))
        t.daemon = True
        t.start()

    def rx_thread(self, ser, RxQ):
        """ Auto detect com port and put data in given que."""
        self.RxQ = RxQ
        while True:
            port = self._search()
            if port != None:
                break
        self.RxQ.put("Detected Remote Control on %s" % port)
        while True:
            #  wait forever for data to forward to client
            try:
                result = self.ser.readline()
                if len(result) > 0:
                    self.RxQ.put(result)
            except:
                print("serial error, trying to reconnect")
                self.RxQ.put("Reconnect Remote Control")
                while True:
                    port = self._search()
                    if port != None:
                        self.RxQ.put("Detected Remote Control on %s" % port)
                        break
            
    def _search(self):
        found = False
        for p in sorted(list(serial.tools.list_ports.comports())):
            port = p[0]
            #print "p[0]", p[0], "p[1]", p[1],"p[2]", p[2]
            if 'USB-SERIAL CH340' in  p[1]: 
                print("found USB-SERIAL CH340 on port", port)
                found = True
            if 'PID=1A86:7523' in p[2]:
                print("found Serial PID")
                found = True
            if found:
                try:
                    self.ser = serial.Serial(port, self.baud_rate)
                    self.ser.timeout = self.timeout_period
                    #self.ser.setDTR(False)  
                    if not self.ser.isOpen():
                        print("Connection failed:", port, "has already been opened by another process")
                        self.ser = None
                        return False
                    self.ser.flush()
                    return port
                except:
                    self.ser = None
        return None

    def _connect(self, portName):
        # Private method to connect to the given portNamem, NOT USED IN THIS VERSION.
        self.connected = False
        self.ser = None
        result = ""
        try:
            self.ser = serial.Serial(portName, self.baud_rate)
            self.ser.timeout = self.timeout_period
            #self.ser.setDTR(False)  
            if not self.ser.isOpen():
                print("Connection failed:", portName, "has already been opened by another process")
                self.ser = None
                return False
            self.ser.flush()
            time.sleep(.1)
            print("Looking for Remote control on ", portName)    
            self.ser.write('V\n')
            #  print self.ser.readline()
            time.sleep(1.1)

            for x in range (0,3):
                result = self.ser.readline()
                if len(result) > 0:
                    print("serial data:", result)
                if SerialRemote.auto_conn_str in result or  "intensity" in result or  "reset" in result:
                    self.connected = True
                    return True
                if len(result) < 1:
                    break
            self.ser.close()
        except:
            self.ser = None
            pass
        return False

    def _send_serial(self, toSend):
        # private method sends given string to serial port
        if self.ser and self.connected :
            if self.ser.isOpen() and self.ser.writable:
                self.ser.write(toSend)
                self.ser.flush()
                return True
        return False

    def send(self, toSend):
        #  print " ".join(str(ord(char)) for char in toSend)
        self._send_serial(toSend)
    
    def service(self):
        """ Poll to service remote control requests."""
        while not self.RxQ.empty():
            msg = self.RxQ.get().rstrip()
            if "Detected Remote" in msg or "Reconnect Remote" in msg or "Looking for Remote" in msg:
                self.actions['detected remote'](msg)
            elif SerialRemote.auto_conn_str not in msg:  # ignore remote ident
                if "intensity" in msg:
                    # TODO add error checking below
                    m,intensity = msg.split('=',2)
                    # print m, "=", intensity
                    self.actions[m](msg)
                elif "scroll_parks" in msg:
                    # TODO add error checking below
                    m,direction = msg.split('=',2)
                    #print m, "=", direction
                    self.actions[m](direction)
                elif "show_parks" in msg:
                    # TODO add error checking below
                    m,flag = msg.split('=',2)
                    #print m, "=", flag
                    self.actions[m](flag)
                else:
                    self.actions[msg]()

if __name__ == "__main__":
    def detected_remote(info):
        print(info)
    def activate():
        print("activate")
    def deactivate():
        print("deactivate") 
    def pause():
        print("pause")
    def dispatch():
        print("dispatch")
    def reset():
        print("reset")
    def deactivate():
        print("deactivate")
    def emergency_stop():
        print("estop")
    def set_intensity(intensity):
        print("intensity ", intensity)
            
    actions = {'detected remote': detected_remote, 'activate': activate,
               'deactivate': deactivate, 'pause': pause, 'dispatch': dispatch,
               'reset': reset, 'emergency_stop': emergency_stop, 'intensity' : set_intensity}
 
    RemoteControl = SerialRemote(actions)
    while True:
         RemoteControl.service()
         time.sleep(.1)
