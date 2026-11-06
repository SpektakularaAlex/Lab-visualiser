import tkinter as tki
#import time
#import threading
#import tooltip

import common
import commonPS2 as commonPS
#import mychart_pil as mychart
#from math import exp, tan

CHEAT_OFFSET = -0.475
RANGE_COEF = 1.0

class Ammeter(commonPS.CommonPS):
    '''def __init__(self, 
                box, box2,
                term_serv_addr, 
                port, 
                aname=('magnet', 'magnet'), 
                control_I_or_V='I', # I, V, or IF
                presets=None, 
                coef_ctrl=1.0, 
                coef_I_read=1.0, 
                coef_V_read=1.0,
                minmax_ctrl=(0, 60, 100),
                minmax_I=(5, 7, 10),  # min_ok, max_ok, max
                minmax_V=(5, 7, 10),  # min_ok, max_ok, max
                units_ctrl=' ',
                units_I='mA',
                units_V='kV',
                d_ctrl=0.01,       
                coef_F_ctrl=0, # ----> Pirani specific stuff from here on
                coef_F_read=1.0,
                minmax_F=(5, 7, 10),  # min_ok, max_ok, max
                units_F='A'): 
        super().__init__(box, box2, term_serv_addr, port, aname, control_I_or_V, presets, coef_ctrl, coef_I_read, coef_V_read, minmax_ctrl, minmax_I, minmax_V, units_ctrl, units_I, units_V, d_ctrl)
    '''    
    def __init__(self, *args):
        super().__init__(*args)
        box = args[0]
        #self.lbl_nA = tki.Label(master=box, text='0 nA', font=('', 24))
        #self.lbl_nA.place(x=2, y=4)
        self.chb_checked = tki.IntVar()
        self.chb_nA = tki.Checkbutton(master=box, text='0 nA', font=('', 15, 'bold'), variable=self.chb_checked, command=self.on_check_fast)
        self.chb_nA.place(x=2, y=0)
        common.set_text(self.chb_nA)
        self.master = box.winfo_toplevel()
        self.fast_timer = None
        self.largerange = False
        #self.fast_timer = self.master.after(100, self.fast_func)
        
    def on_check_fast(self):
        if self.chb_checked.get() == 1:
            self.fast_func()
        else:
            self.master.after_cancel(self.fast_timer)
            common.the_app.active_ctrl_ammeter = -1.0
        
    def fast_func(self):
        #if self.chb_checked.get() == 1:
        r = self.send_message_array('g', 2)
        v = int.from_bytes(r, 'little',signed=True)
        v = (v*self.coef_I_read + CHEAT_OFFSET) * (RANGE_COEF if self.largerange else 1)
        common.change_text(self.chb_nA, '{:.2f} '.format(v)+self.units_I+('*' if self.largerange else ''))
        common.the_app.active_ctrl_ammeter = v
        #else:
        #    common.the_app.active_ctrl_ammeter = -1.0
        #print(v)
        self.fast_timer = self.master.after(100, self.fast_func)
        
        
    def get_data(self):
        super().get_data()
        self.CR         += CHEAT_OFFSET
        self.stats_minI += CHEAT_OFFSET
        self.stats_maxI += CHEAT_OFFSET
        self.largerange = bool(self.flags & 4)
        if self.largerange:
            self.CR         *= RANGE_COEF
            self.stats_minI *= RANGE_COEF
            self.stats_maxI *= RANGE_COEF
        
     
    def update_ui(self):
        super().update_ui()
        common.change_text(self.chb_nA, '{:.2f} '.format(self.CR)+self.units_I)

    def on_destroy(self):
        if not self.fast_timer is None:
            self.master.after_cancel(self.fast_timer)







