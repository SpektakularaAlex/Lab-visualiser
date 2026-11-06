#import tkinter as tki
#import time
#import threading
#import tooltip

#import common
import commonPS2

class KOven(commonPS2.CommonPS):
    def __init__(self, 
                box, box2,
                term_serv_addr, 
                port, 
                aname=('K oven',' K oven'), 
                presets=None, 
                minmax_ctrl=None,
                minmax_T=(5, 7, 10),  # min_ok, max_ok, max
                minmax_H=(5, 7, 10),  # min_ok, max_ok, max
                d_ctrl = 1): 
        super().__init__(box, box2, term_serv_addr, port, aname, 'T', presets, 1.0, 1.0, 100.0, minmax_ctrl, minmax_T, minmax_H, ('T','°C'), ('T','°C'), ('Heater',''), d_ctrl)
        #box.place(height=92)
        self.pid_P = 0.0
        self.pid_I = 0.0
        self.pid_D = 0.0

        '''self.chb_currentSet.configure(text='Set T:')
        self.chb_currentRead.configure(text='T = -1 ')
        self.chb_voltageRead.configure(text='Heater = -1')'''
        
        #self.send_message('relay 0 0.1') # for 100 oC, (0 0.3) is good
        #                             Kp    Ki     Kd  TTavg Kpp
        #print(self.send_message('pid 0.076 0.00004 4.0 10.0 0'))
        #print(self.send_message('pid 0.076 0.00004 12.0 10.0 0')) values that work ok-ish (for jump 0->200 oC); should be default on the driver.
        #print(self.send_message('pid 0.076 0.00064 6.0 10.0 0')) values for 'no overshoot', from relay(0 0.3) at 100 oC, T=4 minutes, A=1 oC.
        print(self.send_message('pid'))
        self.the_probes =[]

        
                

    
    def get_data(self):
        rr = super().get_data()
        if len(rr)>12:
            try:
                self.current = float(rr[0])
                self.pid_P = float(rr[10])
                self.pid_I = float(rr[11])
                self.pid_D = float(rr[12])
            except Exception as ex:
                print(ex)
        self.last_ret[1] = self.last_ret[1][0]
        self.last_ctrl[0] = self.current
        
        
    def update_ui(self):
        super().update_ui()
        '''common.change_text(self.chb_currentSet, 'Set T = {:g} '.format(round(self.current))+self.units_ctrl)
        common.change_text(self.chb_currentRead, 'T = {:.3f} '.format(self.CR)+self.units_I)
        common.change_text(self.chb_voltageRead, 'Heater = {:g}'.format(round(self.VR))+self.units_V)'''
        if self.canvas_show_stats:
            self.bar_V.update(self.stats_minV, self.stats_maxV, txt='P {:.2f}    I {:.2f}    D {:.2f}'.format(self.pid_P, self.pid_I, self.pid_D))



