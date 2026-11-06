import tkinter as tki
#import time
#import threading
#import tooltip

import common
import commonPS2 as commonPS
#import mychart_pil as mychart

FILAMENT_RATE_FAST = 0.25 # default value for internal ramping, V/s, so 5 V for 20 s
FILAMENT_RATE_SLOW = 5/500 # slow value for internal ramping, V/s, so 5 V for 300s=5min, when turning off

class SolidFilament(commonPS.CommonPS):
    def __init__(self, 
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
                d_ctrl=0.01): 
        super().__init__(box, box2, term_serv_addr, port, aname, control_I_or_V, presets, coef_ctrl, coef_I_read, coef_V_read, minmax_ctrl, minmax_I, minmax_V, units_ctrl, units_I, units_V, d_ctrl)

        # scale marks on arc current: at 1.3, 1.4, 1.5, 1.6, 1.7:
        #self.bar_I.add_marks([1.5], [1.3, 1.4, 1.6, 1.7])
        
        # scale marks on arc voltage: at 50, 60, 70, 80, 90, 100:
        #self.bar_V.add_marks([50, 100], [60, 70, 80, 90])
        self.filament_ramper = common.FilamentRamper(
            box, 
            targetA=65, 
            rate=2, 
            ctrl_var=self.ramp_ctrl_var,
            dependent_var=self.ramp_dependent_var,
            ctrl_var_ui=self.var_current)
        self.filament_lifetime_tracker = common.FilamentLifetimeTracker(
            menu=self.menu_extra, 
            targetA=65,
            filename='lifetime_solid_filament.txt')
            
        self.filament_rate = FILAMENT_RATE_FAST
        
        self.lbl_power = tki.Label(master=box, text='0 W', font=('', 8))
        self.lbl_power.place(x=290, y=30)

        
    def ramp_ctrl_var(self, v=-1):
        if v<0:
            return self.current
        self.current = v
        return self.send_message('rampI '+str(self.current*self.coef_ctrl))

    def ramp_dependent_var(self):
        return self.VR
        
    def get_data(self):
        super().get_data()
        self.filament_ramper.on_get_data()
        self.filament_lifetime_tracker.update(self.current)
        # setI, setV, flags, cnt, Iread, Imin, Imax, Vread, Vmin, Vmax, Fread, Fmin, Fmax
        
    def show_menu(self, event):
        self.filament_lifetime_tracker.show_lifetime()
        super().show_menu(event)
        
    def update_ui(self):
        super().update_ui()
        self.filament_ramper.on_update_ui()
        self.lbl_power.configure(text=str(round(self.CR*self.VR))+' W')
        
    def switchOff(self):
        self.var_current_set(0)
        res=self.send_message('rampI 0 ' + str(FILAMENT_RATE_SLOW))
        if res != 'ok':
            print(res)
        self.update_ui()






