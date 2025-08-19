""" Platform Controller connects a selected client to chair.

Copyright Michael Margolis, Middlesex University 2019; see LICENSE for software rights.

This version requires NoLimits attraction license and NL ver 2.5.3.4 or later
"""

import sys
import time
import tkinter as tk
import tkinter.ttk
import tkinter.messagebox
import traceback
import numpy as np
from math import degrees
import time
import os
import copy
import logging

import importlib

from kinematics.kinematics import Kinematics
from kinematics.shape import Shape
from output.platform_output import OutputInterface

# from output.muscle_output import MuscleOutput
# import d_to_p


isActive = True  # set False to terminate

processing_dur = 5  # time in ms to processes frame data (value updated in real time)

# from  platform_config import *
import platform_config

cfg = importlib.import_module(platform_config.platform_selection).PlatformConfig()
client = importlib.import_module(platform_config.client_selection).InputInterface()

chair = OutputInterface()
# DtoP = d_to_p.DistanceToPressure(201, 800)
# chair = MuscleOutput(DtoP.muscle_length_to_pressure, time.sleep, )

shape = Shape(platform_config.FRAME_RATE_SECS)
k = Kinematics()

class Controller:

    def __init__(self):
        self.prevT = 0
        self.is_output_enabled = False
        self._init_geometry()

    def _init_geometry(self):
        try:
           if cfg.calculate_coords:
               cfg.calculate_coords()
        except:
            pass
        if len(cfg.BASE_POS) == 3:
            #  reflect around X axis to generate right side coordinates
            otherSide = copy.deepcopy(cfg.BASE_POS[::-1])  # order reversed
            for inner in otherSide:
                inner[1] = -inner[1]   # negate Y valueswaiti
            cfg.BASE_POS.extend(otherSide)

            otherSide = copy.deepcopy(cfg.PLATFORM_POS[::-1])  # order reversedFrunning
            for inner in otherSide:
                inner[1] = -inner[1]   # negate Y values
            cfg.PLATFORM_POS.extend(otherSide)

        base_pos = np.array(cfg.BASE_POS)
        platform_pos = np.array(cfg.PLATFORM_POS)

        #  uncomment the following to plot the array coordinates
        # plot_config.plot(base_pos, platform_pos, cfg.PLATFORM_MID_HEIGHT, cfg.PLATFORM_NAME )

        print(("starting", cfg.PLATFORM_NAME))
        print((cfg.GEOMETRY_TYPE))
        try:
            chair.begin(cfg.MIN_ACTUATOR_LEN, cfg.MAX_ACTUATOR_LEN, cfg.DISABLED_LEN, cfg.PROPPING_LEN, cfg.FIXED_LEN, cfg.TOTAL_WEIGHT)
            self.actuator_lengths = [cfg.PROPPING_LEN] * 6   # position for attaching stairs or moving prop
            k.set_geometry( base_pos, platform_pos, cfg.PLATFORM_MID_HEIGHT)
            
            shape.begin(cfg.PLATFORM_1DOF_LIMITS, "shape.cfg")
        except:
            e = sys.exc_info()[0]  # report error
            s = traceback.format_exc()
            print((e, s))

    def init_gui(self, root):
        self.root = root
        self.root.geometry("800x480")
        if os.name == 'nt':
            self.root.iconbitmap('images\ChairIcon3.ico')
        title = client.rootTitle + " for " + cfg.PLATFORM_NAME
        self.root.title(title)
        self.nb = tkinter.ttk.Notebook(root)
        page1 = tkinter.ttk.Frame(self.nb)  # client
        self.nb.add(page1, text='  Input  ')
        page2 = tkinter.ttk.Frame(self.nb)  # shape
        self.nb.add(page2, text='  Shape  ')
        page3 = tkinter.ttk.Frame(self.nb)  # output
        self.nb.add(page3, text='  Output ')
        page4 = tkinter.ttk.Frame(self.nb)  # station bitfields
        self.nb.add(page4, text=' Station Status ')
        self.nb.pack(expand=1, fill="both")
        try: 
            client.init_gui(page1)
            shape.init_gui(page2)
            chair.init_gui(page3)
            client.init_bitfield_gui(page4)  # comment this out if not using updated nl2 code
            self.set_intensity(10)  # default intensity at max
            return True
        except:
            e = sys.exc_info()[0]  # report error
            s = traceback.format_exc()
            print((e, s))
        return False

    def update_gui(self):
        self.root.update_idletasks()
        self.root.update()

    def quit(self):
        if client.USE_GUI:
            result = tkinter.messagebox.askquestion("Shutting Down Platform Software", "Are You Sure you want to quit?", icon='warning')
            if result != 'yes':
                return
        global isActive
        isActive = False

    def enable_platform(self):
        ##pos = client.get_current_pos()
        ##actuator_lengths = k.inverse_kinematics(self.process_request(pos))
        #  print "cp", pos, "->",actuator_lengths
        chair.set_enable(True, self.actuator_lengths)
        self.is_output_enabled = True
        #  print "enable", pos

    def disable_platform(self):
        ##pos = client.get_current_pos()
        #  print "disable", pos
        ##actuator_lengths = k.inverse_kinematics(self.process_request(pos))
        chair.set_enable(False, self.actuator_lengths)
        self.is_output_enabled = False
    
    def move_to_idle(self):
        ##actuator_lengths = k.inverse_kinematics(self.process_request(client.get_current_pos()))
        pos = client.get_current_pos()
        self.park_platform(True)  # added 25 Sep as backstop to prop when coaster state goes idle
        chair.move_to_idle(self.actuator_lengths, pos[2]) # send current z pos
        # chair.show_muscles([0,0,0,0,0,0], actuator_lengths)
        
    def move_to_ready(self):
        ##actuator_lengths = k.inverse_kinematics(self.process_request(client.get_current_pos()))
        pos = client.get_current_pos()
        chair.move_to_ready(self.actuator_lengths, pos[2])
        
    def swell_for_access(self):
        chair.swell_for_access(3, False)  # four seconds in up pos

    def park_platform(self, state):
        chair.park_platform(state)
        print((format("Platform park state changed to %s" %("parked" if state else "unparked"))))
                     
    def set_intensity(self, intensity):
        lower_payload_weight = 20  # todo - move these or replace with real time load cell readings 
        upper_payload_weight = 90
        payload = self.scale((intensity), (0,10), (lower_payload_weight,  upper_payload_weight))
        #  print "payload = ", payload
        chair.set_payload(payload + cfg.PLATFORM_UNLOADED_WEIGHT) 

        intensity = intensity * 0.1
        shape.set_intensity(intensity)
        status = format("%d percent Intensity, (Weight %d kg)" % (shape.get_overall_intensity() * 100, payload)) 
        client.intensity_status_changed( (status, "green3"))
       
    def scale(self, val, src, dst) :  # the Arduino 'map' function written in python
           return (val - src[0]) * (dst[1] - dst[0]) / (src[1] - src[0])  + dst[0]

    def process_request(self, request):
        #  print "in process", request
        if client.is_normalized:
            #  print "pre shape", request,
            request = shape.shape(request)  # adjust gain & washout and convert from norm to real
            #  print "post",request
        request = shape.smooth(request)
        #  print ", after smoothing", request
        ##if self.is_output_enabled:
        return request

    def move(self, position_request):
        #  position_requests are in mm and radians (not normalized)
        start = time.time()
        #  print "req= " + " ".join('%0.2f' % item for item in position_request)
        self.actuator_lengths = k.inverse_kinematics(position_request)
        if self.nb.index("current") == 2: # the output tab
            chair.show_muscles(position_request, self.actuator_lengths)
        if client.USE_UDP_MONITOR and client.USE_UDP_MONITOR == True:
            chair.echo_requests_to_udp(position_request) 
        if client.USE_GUI:
            self.update_gui()
        chair.move_platform(self.actuator_lengths)

        #  print "dur =",  time.time() - start, "interval= ",  time.time() - self.prevT
        #  self.prevT =  time.time()

    def cmd_func(self, cmd):  # command handler function called from Platform input
        global isActive
        if cmd == "exit":
            isActive = False
        elif cmd == "enable":
            self.enable_platform()
        elif cmd == "disable":
            self.disable_platform()
        elif cmd == "idle":
            self.move_to_idle()
        elif cmd == "ready":
            self.move_to_ready()
        elif cmd == "swellForStairs":
            self.swell_for_access()
        elif 'intensity' in cmd:
             m,intensity = cmd.split('=',2)
             self.set_intensity(int(intensity)) 
        elif cmd == "parkPlatform":
             self.park_platform(True)
        elif cmd == "unparkPlatform":
             self.park_platform(False)
        elif cmd == "quit":
            # prompts with tk msg box to confirm 
            self.quit() 

    def move_func(self, request):  # move handler to position platform as requested by Platform input
        #  print "request is trans/rot list:", request
        try:
            start = time.time()
            r = self.process_request(np.array(request))
            
            self.move(r)
            if client.log:
                """
                r[3] = r[3]* 57.3  # convert to degrees
                r[4] = r[4]* 57.3
                r[5] = r[5]* 57.3
                # client.log(r)
                """
                request[3] = request[3]* 57.3  # convert to degrees
                request[4] = request[4]* 57.3
                request[5] = request[5]* 57.3
                client.log(request)
            global processing_dur
            processing_dur = time.time() - start
        except:
            e = sys.exc_info()[0]  # report error
            s = traceback.format_exc()
            print((e, s))

controller = Controller()


def setup_logging():
    print("todo, simplify log setup when dropping py 2.7 support")
    is_windows = (os.name == 'nt')

    # Try to get UTF-8 stdout when possible
    if not is_windows and hasattr(sys.stdout, 'reconfigure'):
        # Py3.7+
        try:
            sys.stdout.reconfigure(encoding='utf-8', newline='')
        except Exception:
            pass
    else:
        # Py2 / older Py3 fallback: best-effort UTF-8 wrapper on Py2
        try:
            if sys.version_info[0] == 2:
                import codecs
                enc = getattr(sys.stdout, 'encoding', None)
                if not enc or enc.lower() != 'utf-8':
                    sys.stdout = codecs.getwriter('utf-8')(sys.stdout)
        except Exception:
            pass

    class CleanFormatter(logging.Formatter):
        def format(self, record):
            # Py2-safe super call
            s = logging.Formatter.format(self, record)
            try:
                return s.rstrip('\r\n')
            except Exception:
                return s

    log_format = "%(asctime)s [%(levelname)s] %(message)s"
    formatter = CleanFormatter(log_format, datefmt="%H:%M:%S")

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    # log_level = logging.DEBUG  
    log_level = logging.INFO
    root_logger.setLevel(log_level)

    # Avoid duplicates: only add if no existing StreamHandler to stdout
    add = True
    for h in getattr(root_logger, 'handlers', []):
        try:
            if isinstance(h, logging.StreamHandler) and getattr(h, 'stream', None) is sys.stdout:
                add = False
                break
        except Exception:
            pass
    if add:
        root_logger.addHandler(handler)



def main():
    setup_logging()
    log = logging.getLogger(__name__)  
    try:
        if client.USE_GUI:
            root = tk.Tk()
            if controller.init_gui(root) == False:
                print("init gui returned false")
                return  # exit if unable to establish contact with client
    except NameError:
        client.USE_GUI = False
        print("GUI Disabled")

    except:
        e = sys.exc_info()[0]  # report error
        s = traceback.format_exc()
        print((e, s)) 

    previous = time.time()
    chair_status = None
    ip_address = "192.168.1.117"
    print("attempting to connect to PC at:", ip_address)
    if client.begin(controller.cmd_func, controller.move_func, cfg.PLATFORM_1DOF_LIMITS, server_ip=ip_address) == False: 
        return  # exit if client forces exit

    print("starting main service loop")
    while isActive: 
        if client.USE_GUI:
            controller.update_gui()
            """
            # todo - move into client?
            delta = time.time() - previous 
            percent = -100 * (1 - platform_config.FRAME_RATE_SECS / delta)
            if percent >=0:
                color = "green3"
            elif percent > -10:
                color = "orange"
            else:
                 color = "red"
            if percent > 9:
                percent = int(percent/10) * 10
                client.chair_status_changed((format("Processing leeway is > %d percent" % (percent)),color ))
            else:
                client.chair_status_changed((format("Processing leeway is %d percent" % percent),color ))
            """
        #time_to_go =  time.time() - previous
        #print "in controller, time to go=", time_to_go
        # wait for start of next frame
        while time.time() - previous < platform_config.FRAME_RATE_SECS:
            if client.USE_GUI:
                controller.update_gui()
        previous = time.time()

        if chair_status != chair.get_output_status():
            chair_status = chair.get_output_status()
            client.chair_status_changed(chair_status)

        client.service()

if __name__ == "__main__":
    main()
    client.fin()
    chair.fin()

