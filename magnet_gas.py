#import tkinter as tki
#import time
#import tooltip

import common
import commonPS2 as commonPS

class MagnetGas(commonPS.CommonPS):
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
                coef_F_ctrl=1.0, # ----> arc/filament specific stuff from here on
                coef_F_read=0,
                minmax_F=(5, 7, 10),  # min_ok, max_ok, max
                units_F='A'): 
        super().__init__(box, box2, term_serv_addr, port, aname, control_I_or_V, presets, coef_ctrl, coef_I_read, coef_V_read, minmax_ctrl, minmax_I, minmax_V, units_ctrl, units_I, units_V, d_ctrl, coef_F_ctrl, coef_F_read, minmax_F, units_F)
        self.dF = 0.01
        #self.chb_currentSet.configure(text='Magnet:')

        self.update_flag = False
        
        
        

    def get_data(self):
        super().get_data()
        
        if common.g_pressure_regulate != 0 and self.F > 1.5 and self.F<3:
            print('Regulating pressure', common.g_pressure_regulate)
            self.F += common.g_pressure_regulate*self.d_F
            self.send_message('rampV '+str(self.F*self.coef_F_ctrl))
            self.update_flag = True
            common.g_pressure_regulate = 0

        
        
    def update_ui(self):
        super().update_ui()
        
        if self.update_flag:
            self.var_F_set(self.F)
            self.update_flag = False




