"""
my_festo-sim

displays festo messages

"""
import easyip
import sys
import socket
import threading
import time
from queue import Queue

import traceback


MAX_MSG_LEN = 1024

class festo_sim():
    def __init__(self): 
        self.HOST = ""
        self.PORT = easyip.EASYIP_PORT
        self.inQ = Queue()
        self.thread = threading.Thread(target=self.listener_thread, args=(self.inQ, self.HOST, self.PORT))
        if self.thread:
           self.thread.daemon = True
           self.thread.start()
        else:
            print("Unable to start festo sim thread")


    def read(self):
        while not self.inQ.empty():
            payload = self.inQ.get()
            #  print "in Q, payload", payload, "..."
            try:
                if payload != None:
                    print("Festo Message:", payload)
            except:
                #  print error if input not a string or cannot be converted into valid request
                e = sys.exc_info()[0]
                s = traceback.format_exc()
                print(e, s)

    def listener_thread(self, inQ, HOST, PORT):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind((HOST, PORT))
            #print "opening socket on", PORT
            self.inQ = inQ
        except:
            e = sys.exc_info()[0]
            s = traceback.format_exc()
            print("thread init err", e, s)
        while True:
            try:
                msg, addr = sock.recvfrom(MAX_MSG_LEN)
                #  print "in thread:", msg, addr
                self.inQ.put((msg,addr))
            except:
                e = sys.exc_info()[0]
                s = traceback.format_exc()
                print("listener err", e, s)

if __name__ == "__main__":
    festo = festo_sim()
    while True:
        festo.read()

