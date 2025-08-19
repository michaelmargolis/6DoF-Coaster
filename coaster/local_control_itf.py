""" Local control interface"""

import sys
import time
import os
import rotary_encoder
import buttons

USE_PCB = True

if USE_PCB:
    DISPATCH_PIN = 18
    PAUSE_PIN = 17
    RESET_PIN = 23
    ACTIVATE_PIN = 22
    ENCODER_A = 3
    ENCODER_B = 4
    ENCODER_SW_PIN = 2
else:
    DISPATCH_PIN = 5 
    PAUSE_PIN = 6
    RESET_PIN = 13
    ACTIVATE_PIN = 19
    ENCODER_A = 9
    ENCODER_B = 11
    ENCODER_SW_PIN = 26

class LocalControlItf(object):   # was SerialRemote(object):
    """ provide action strings associated with buttons on raspberry pi."""

    def __init__(self, actions):
        """ Call with dictionary of action strings.
 
        Keys are the strings associated with gpio pins,
        values are the functons to be called for the given key.
        """
        global USE_PCB
        if USE_PCB:
           print("Initializing Raspberry Pi Touch Control Panel")
        else:
           print("Initializing Raspberry Pi using hard wired switches")
        self.actions = actions
        self.decoder = rotary_encoder.decoder(ENCODER_A, ENCODER_B, self.encoder_callback)
        self.intensity = 10
        self.prev_intensity = None
        self.enc_pushed = False
        self.park_inc = 0
        self.buttons = buttons.Buttons(self.button_callback)
        self.buttons.append(DISPATCH_PIN,'dispatch', 'pullup','falling')
        self.buttons.append(PAUSE_PIN,'pause', 'pullup','falling')
        self.buttons.append(RESET_PIN,'reset', 'pullup','falling')
        self.buttons.append(ACTIVATE_PIN,['activate', 'deactivate'], 'pullup','both')
        self.buttons.append(ENCODER_SW_PIN,['enc_pushed', 'enc_released'], 'pullup','both')

    def encoder_callback(self, dir):
       if  self.enc_pushed == False:
           self.intensity += dir
           if self.intensity > 10:
               self.intensity = 10
           if self.intensity < 0:
               self.intensity = 0
       else:
           print "button pushed" 
           self.park_inc += dir
    
    def button_callback(self, msg):
        print 'local control', msg
        if msg == 'enc_pushed':
             self.enc_pushed = True
             self.actions['show_parks']('True')
        elif msg == 'enc_released':
             self.enc_pushed = False
             self.actions['show_parks']('False')
        else:
            self.actions[msg]()

    def is_activated(self):
        return self.buttons.raw_value(ACTIVATE_PIN) == 'high'

    def service(self):
        """ Poll to service button requests."""
        self.buttons.service()
        if self.prev_intensity != self.intensity:
            msg = format("intensity=%d" % (self.intensity))
            print msg
            self.actions['intensity'](msg)
            self.prev_intensity = self.intensity
        if self.park_inc > 1:
            # print self.park_inc
            self.actions['scroll_parks']('1')
            self.park_inc = 0
        elif self.park_inc < -1:
            self.actions['scroll_parks']('-1')
            self.park_inc = 0


if __name__ == "__main__":
    def detected_remote(info):
        print info
    def activate():
        print "activate"
    def deactivate():
        print "deactivate" 
    def pause():
        print "pause"
    def dispatch():
        print "dispatch"
    def reset():
        print "reset"
    def deactivate():
        print "deactivate"
    def emergency_stop():
        print "estop"
    def set_intensity(intensity):
        print "intensity ", intensity
            
    actions = {'detected remote': detected_remote, 'activate': activate,
               'deactivate': deactivate, 'pause': pause, 'dispatch': dispatch,
               'reset': reset, 'emergency_stop': emergency_stop, 'intensity' : set_intensity}
 
    local_control = LocalControlItf(actions)
    while True:
         local_control.service()
         time.sleep(.1)
