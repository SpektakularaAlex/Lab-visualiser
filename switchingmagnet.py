import tkinter as tki
import tkinter.messagebox
#import time
#import threading
#import tooltip

#import common
import commonPS2 as commonPS
#import mychart_pil as mychart
#from math import exp, tan

class SwitchingMagnet(commonPS.CommonPS):
    def __init__(self, 
                box, box2,
                term_serv_addr, 
                port, 
                aname=('magnet','magnet'), 
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
                coef_F_ctrl=0, # ----> teslameter specific stuff from here on
                coef_F_read=1.0,
                minmax_F=(5, 7, 10),  # min_ok, max_ok, max
                units_F='G'): 
        super().__init__(box, box2, term_serv_addr, port, aname, control_I_or_V, presets, coef_ctrl, coef_I_read, coef_V_read, minmax_ctrl, minmax_I, minmax_V, units_ctrl, units_I, units_V, d_ctrl, coef_F_ctrl, coef_F_read, minmax_F, units_F)
        
        
        self.var_polarity = tki.IntVar()
        self.radio_S1 = tki.Radiobutton(master=box, text='S1', value=0, variable=self.var_polarity, command=self.switch_polarity, padx=0, pady=0)
        self.radio_S2 = tki.Radiobutton(master=box, text='S2', value=1, variable=self.var_polarity, command=self.switch_polarity, padx=0, pady=0)
        self.radio_S1.place(x=300, y=3)
        self.radio_S2.place(x=300, y=20)
        self.radio_S1.lower()
        self.radio_S2.lower()
        self.polarity_switch_enabled = True
        self.polarity_switch_value = 0
        
        
    def switch_polarity(self):
        rep = self.send_message('switchPositive' if self.var_polarity.get()==0 else 'switchNegative')
        tkinter.messagebox.showinfo(message=rep)
        self.polarity_switch_value = -1 # invalidate, to be updated
    
        
        
    def update_ui(self):
        super().update_ui()
        
        f = self.flags
        if f >= 0:
            pol = (f & 8) >> 3
            if pol != self.polarity_switch_value:
                self.polarity_switch_value = pol
                self.var_polarity.set(pol)
            ena = bool(f & 4)
            if ena and self.current != 0:
                ena = False
            if ena != self.polarity_switch_enabled:
                self.polarity_switch_enabled = ena
                st = tki.NORMAL if ena else tki.DISABLED
                self.radio_S1.config(state=st)
                self.radio_S2.config(state=st)






