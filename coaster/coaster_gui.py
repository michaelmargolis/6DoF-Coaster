"""
Python Coaster client GUI

This version requires NoLimits attraction license and NL ver 2.5.3.4 or later
"""

import os
import sys
import tkinter as tk
import tkinter.ttk
import tkinter.font
from .coaster_state import RideState, RideStateStr
from .nl2_messenger import station_bit_flags

ATTRACTION_LICENCE = True

class CoasterGui(object):

    def __init__(self, dispatch, pause, reset, activate_callback_request, quit_callback):
        self.dispatch = dispatch
        self.pause = pause
        self.reset = reset
        self.activate_callback_request = activate_callback_request
        self.quit = quit_callback
        self.park_path = []
        self.park_name = []
        self.seat = []
        self._park_callback = None
        self.current_park = 0


    def init_gui_bitfield(self, master):
        self.master = master
        self.frame = tk.Frame(master)
        self.frame.grid()
        self.labels = {}
        row = 0
        for bit, label in sorted(station_bit_flags.items()):
            tk.Label(self.frame, text=label).grid(row=row, column=0, sticky='w')
            value_label = tk.Label(self.frame, text='0')
            value_label.grid(row=row, column=1, sticky='w')
            self.labels[bit] = value_label
            row += 1


    def update_bitfield(self, bitfield_value):
        for bit, label_widget in list(self.labels.items()):
            value = '1' if bitfield_value & bit else '0'
            label_widget.config(text=value)
            

    def init_gui(self, master):
        self.master = master
        frame = tk.Frame(master)
        frame.grid()

        spacer_frame = tk.Frame(master, pady=4)
        spacer_frame.grid(row=0, column=0)
        self.label0 = tk.Label(spacer_frame, text="").grid(row=0)

        self.dispatch_button = tk.Button(master, height=2, width=14, text="Dispatch",
                                         command=self.dispatch, underline=0)
        self.dispatch_button.grid(row=1, column=0, padx=(20, 4))

        self.pause_button = tk.Button(master, height=2, width=14, text="Pause", command=self.pause, underline=0)
        self.pause_button.grid(row=1, column=2, padx=(20))

        self.reset_button = tk.Button(master, height=2, width=14, text="Reset Rift",
                                      command=self.reset, underline=0)
        self.reset_button.grid(row=1, column=3, padx=(20))

        label_frame = tk.Frame(master, pady=20)
        label_frame.grid(row=3, column=0, columnspan=4)
        
        #  make all default fonts bigger
        default_font = tkinter.font.nametofont("TkDefaultFont")
        default_font.configure(size=14)

        if ATTRACTION_LICENCE:
            self.pane = tk.Label(label_frame, text="Pane Title")
            self.pane.grid(row=0, column=0, columnspan=2, ipadx=16, sticky=tk.W)
            
        
            self.park_listbox = tkinter.ttk.Combobox(label_frame, font=(None,16))
            self.park_listbox.grid(row=0, column=0, columnspan=2, ipadx=16, sticky=tk.W)
            self.read_parks()

            self.park_listbox["values"] = self.park_name
            self.park_listbox.bind("<<ComboboxSelected>>", lambda _ : self._park_by_index(self.park_listbox.current()))
            self.park_listbox.current(0)
            self.park_listbox.bind("<Enter>",self.park_list_events)
            self.park_listbox.bind("<Leave>",self.park_list_events)
            self.park_listbox.bind("<FocusIn>",self.park_list_events)
            self.park_listbox.bind("<FocusOut>",self.park_list_events)
            self.is_parklist_focused = False
            font = ("TkDefaultFont", '14')
            master.option_add("*TCombobox*Listbox*Font", font)

        self.coaster_status_label = tk.Label(label_frame, text="Waiting for Coaster Status", font=(None, 24),)
        self.coaster_status_label.grid(row=1, columnspan=2, ipadx=16, sticky=tk.W)

        self.intensity_status_Label = tk.Label(label_frame, font=(None, 12),
                 text="Intensity", fg="orange")
        self.intensity_status_Label.grid(row=2, column=0, columnspan=2, ipadx=16, sticky=tk.W)
        
        self.coaster_connection_label = tk.Label(label_frame, fg="red", font=(None, 12),
               text="Coaster Software Not Found (if NL2 is running, check network connection)")
        self.coaster_connection_label.grid(row=3, columnspan=2, ipadx=16, sticky=tk.W)

        self.remote_status_label = tk.Label(label_frame, font=(None, 12),
                 text="Looking for Remote Control", fg="orange")
        self.remote_status_label.grid(row=4, columnspan=2, ipadx=16, sticky=tk.W)

        self.chair_status_Label = tk.Label(label_frame, font=(None, 12),
                 text="Using Festo Controllers", fg="orange")
        self.chair_status_Label.grid(row=5, column=0, columnspan=2, ipadx=16, sticky=tk.W)
        
        self.connection_state_Label = tk.Label(label_frame, font=(None, 12),
                 text="Not Connected", fg="grey")
        self.connection_state_Label.grid(row=6, column=0, columnspan=2, ipadx=16, sticky=tk.W)
        
        """ 
        self.temperature_status_Label = tk.Label(label_frame, font=(None, 12),
                 text="Attempting Connection to VR PC Server", fg="red")
        self.temperature_status_Label.grid(row=6, column=0, columnspan=2, ipadx=16, sticky=tk.W)
        # print self.temperature_status_Label, "wha"
        """
        bottom_frame = tk.Frame(master, pady=16)
        bottom_frame.grid(row=5, columnspan=3)

        self.is_chair_activated = tk.IntVar()
        self.is_chair_activated.set(0)  # disable by default

        self.activation_button = tk.Button(master, underline=0, command=self._enable_pressed)
        self.activation_button.grid(row=4, column=1)
        self.deactivation_button = tk.Button(master, command=self._disable_pressed)
        self.deactivation_button.grid(row=4, column=2)
        self.set_activation_buttons(False)

        self.close_button = tk.Button(master, text="Exit", command=self.quit)
        self.close_button.grid(row=4, column=3)

        self.label1 = tk.Label( bottom_frame, text="     ").grid(row=0, column=1)

        self.org_button_color = self.dispatch_button.cget("background")

        master.bind("<Key>", self.hotkeys)

    def set_seat(self, seat):
        if seat != '':
           print("seat", int(seat))
    """
    def preset_seat(self):
        print "preset seat"
    """
    """
    def set_focus(self):
        # not used in this version
        #needs: import win32gui # for set_focus
        guiHwnd = win32gui.FindWindow("TkTopLevel",None)
        print guiHwnd
        win32gui.SetForegroundWindow(guiHwnd)
    """

    def read_parks(self):
        try:
            path = os.path.abspath('coaster/parks.cfg')
            print(path)
            with open(path) as f:
                parks = f.read().splitlines()
                for park in parks:
                    p = park.split(',')
                    self.park_path.append(p[0]) 
                    self.seat.append(p[1])
                    #  print park
                    p = p[0].split('/')
                    p = p[len(p)-1]
                    #  print p,
                    self.park_name.append(p.split('.')[0])
            self.park_listbox.configure(state="disabled")
            print("available parks are:", self.park_name)
        except:
            e = sys.exc_info()[0]
            print("Unable to open parks.cfg file, select park in NoLimits", e)

    def set_park_callback(self, cb):
        self._park_callback = cb
        
    def _park_by_index(self, idx):
        print(idx, self.park_path[idx])
        #  print "park by index", idx, self.current_park, idx == self.current_park
        if idx != self.current_park and self._park_callback != None:
            print("loading park", self.park_name[idx])
            # load park in pause mode, this will unpuase when park is loaded
            #print "todo select callback commented out!"
            self._park_callback(True, self.park_path[idx], self.seat[idx])
            self.current_park = idx

    def get_current_park_name(self): 
        return self.park_name[self.current_park]

    def scroll_parks(self, dir):
        self.park_listbox.event_generate(dir) 
        #  print "scroll parks, dir=", dir, "is open = ", self.is_parklist_focused

    def show_parks(self, isPressed):
        # todo ignore if input tab not active 
        #print "\nshow parks, pressed=", isPressed, "is open = ", self.is_parklist_focused
        if isPressed == 'True':
           if self.is_parklist_focused == False:
              #open pop down list
              self.park_listbox.focus_set()
              self.park_listbox.event_generate('<Button-1>')
        else:  
            if self.is_parklist_focused == True:
                print("select item here") 
                self.park_listbox.event_generate('<Return>')
            else:
               print("Unhandled state in Show_parks, pressed=", isPressed, "is open = ", self.is_parklist_focused)

    def park_list_events(self,event):
        #print "event", str(event.type)
        if event.type == '10':
           self.is_parklist_focused = True
        elif event.type == '9':
           self.is_parklist_focused = False
        """
        # following prints other events from park list widget
        else:
            print str(event.type)
        """
    
    def hide_parks_dialog(self):
         self.top.destroy()

    def _enable_pressed(self):
        #  self.set_activation_buttons(True)
        self.activate_callback_request(True)

    def _disable_pressed(self):
        #  self.set_activation_buttons(False)
        self.activate_callback_request(False)

    def set_activation_buttons(self, isEnabled):  # callback from Client
        if isEnabled:
            self.activation_button.config(text="Activated ", relief=tk.SUNKEN)
            self.deactivation_button.config(text="Deactivate", relief=tk.RAISED)
            self.park_listbox.configure(state="disabled")
        else:
            self.activation_button.config(text="Activate ", relief=tk.RAISED)
            self.deactivation_button.config(text="Deactivated", relief=tk.SUNKEN)
            self.park_listbox.configure(state="readonly")

    def set_coaster_status_label(self, label):
        #  print label
        self.coaster_status_label.config(text=label[0], fg=label[1])
        
    def set_coaster_connection_label(self, label):
        self.coaster_connection_label.config(text=label[0], fg=label[1])

    def chair_status_changed(self, status):
        self.chair_status_Label.config(text=status[0], fg=status[1])

    def temperature_status_changed(self, status):
        return
        self.temperature_status_Label.config(text=status[0], fg=status[1])

    def intensity_status_changed(self, status):
        self.intensity_status_Label.config(text=status[0], fg=status[1])
        
    def set_remote_status_label(self, label):
        self.remote_status_label.config(text=label[0], fg=label[1])

    def hotkeys(self, event):
        print("pressed", repr(event.char))
        if event.char == 'd':  # ignore case
            self.dispatch()
        if event.char == 'p':
            self.pause()
        if event.char == 'r':
            self.reset()

        """ todo ?
        if event.char == 'a':
            if self.isActivated():
                #print "in hotkeys, cposition_requesting deactivate"
                self.deactivate()
            else:
                #print "in hotkeys, cposition_requesting activate"
                self.activate()
        """
    def process_state_change(self, new_state, isActivated):
        conn_str =format("Coaster state changed to: %s (%s)" % (RideStateStr[new_state], "Activated" if isActivated else "Deactivated"))
        print(conn_str)
        self.connection_state_Label.config(text=conn_str, fg="grey")
        
        if new_state == RideState.READY_FOR_DISPATCH:
            if isActivated:
                print("Coaster is Ready for Dispatch")
                self.dispatch_button.config(relief=tk.RAISED, state=tk.NORMAL)
                self.coaster_status_label.config(text="Coaster is Ready for Dispatch", fg="green3")
            else:
                print("Coaster at Station but deactivated")
                self.dispatch_button.config(relief=tk.RAISED, state=tk.DISABLED)
                self.coaster_status_label.config(text="Coaster at Station but deactivated", fg="orange")
                self.set_coaster_status_label(["Coaster connected but not activated", "orange"])

            self.pause_button.config(relief=tk.RAISED, state=tk.NORMAL, text="Prop Platform")
            self.reset_button.config(relief=tk.RAISED, state=tk.NORMAL)

        elif new_state == RideState.RUNNING:
            self.dispatch_button.config(relief=tk.SUNKEN, state=tk.DISABLED)
            self.pause_button.config(relief=tk.RAISED, state=tk.NORMAL, text="Pause")
            self.reset_button.config(relief=tk.RAISED, state=tk.NORMAL)
            self.coaster_status_label.config(text="Coaster is Running", fg="green3")
        elif new_state == RideState.PAUSED:
            self.dispatch_button.config(relief=tk.SUNKEN, state=tk.DISABLED)
            self.pause_button.config(relief=tk.SUNKEN, state=tk.NORMAL)
            self.reset_button.config(relief=tk.RAISED, state=tk.NORMAL)
            self.coaster_status_label.config(text="Coaster is Paused", fg="orange")
        elif new_state == RideState.RESETTING:
            self.dispatch_button.config(relief=tk.SUNKEN, state=tk.DISABLED)
            self.pause_button.config(relief=tk.RAISED, state=tk.DISABLED)
            self.reset_button.config(relief=tk.SUNKEN, state=tk.NORMAL)
            self.set_coaster_status_label(["Coaster is resetting", "blue"])
