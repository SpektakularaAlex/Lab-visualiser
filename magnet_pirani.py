#import tkinter as tki
#import time
#import threading
#import tooltip

#import common
import commonPS2 as commonPS
#import mychart_pil as mychart
from math import exp, tan

class MagnetPirani(commonPS.CommonPS):
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
        
        
        
        
    def get_data(self):
        super().get_data()
        self.FR = mA_to_mbar(self.FR)
        self.stats_minF = mA_to_mbar(self.stats_minF)
        self.stats_maxF = mA_to_mbar(self.stats_maxF)
        self.slave.last_ret = [(self.FR, self.stats_minF, self.stats_maxF)] # type: ignore
        
        



def mA_to_mbar(mA):
    if mA < 8.0:
        return 0.001
    elif mA > 48.0:
        return 1000.0
    else:
        return 3.86983617*exp(1.76878011*tan(0.06193882*(mA-27.78485364))) - 0.02789361





