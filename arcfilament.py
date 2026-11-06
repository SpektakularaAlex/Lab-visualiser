import tkinter as tki
#import time
#import threading
#import tooltip

import common
import commonPS2 as commonPS
#import mychart_pil as mychart

class ArcFilament(commonPS.CommonPS):
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
                d_ctrl=0.01,       
                coef_F_ctrl=1.0, # ----> arc/filament specific stuff from here on
                coef_F_read=1.0,
                minmax_F=(5, 7, 10),  # min_ok, max_ok, max
                units_F='A'): 
        super().__init__(box, box2, term_serv_addr, port, aname, control_I_or_V, presets, coef_ctrl, coef_I_read, coef_V_read, minmax_ctrl, minmax_I, minmax_V, units_ctrl, units_I, units_V, d_ctrl, coef_F_ctrl, coef_F_read, minmax_F, units_F)
        #self.chb_currentSet.configure(text='Arc:')
        
        '''# scale marks on arc current: at 1.3, 1.4, 1.5, 1.6, 1.7:
        self.bar_I.add_marks([1.5], [1.3, 1.4, 1.6, 1.7])
        
        # scale marks on arc voltage: at 50, 60, 70, 80, 90, 100:
        self.bar_V.add_marks([50, 100], [60, 70, 80, 90])

        # scale marks on filament current: at 20..27:
        self.bar_F.add_marks([20, 25], [21, 22, 23, 24, 26, 27])'''

        # === arc start: ===
        lbl = tki.Label(master=box, text='START:')
        lbl.place(x=220, y=5)
        btn = tki.Button(master=box, text='1s', command=lambda: self.arc_start(1.0))
        btn.place(x=276, y=5, width=20, height=22)
        btn = tki.Button(master=box, text='2s', command=lambda: self.arc_start(2.0))
        btn.place(x=298, y=5, width=20, height=22)
        btn = tki.Button(master=box, text='5s', command=lambda: self.arc_start(5.0))
        btn.place(x=320, y=5, width=20, height=22)
        
        # === ramp filament: ===
        self.filament_ramper = common.FilamentRamper(
            box2, 
            targetA=22, 
            rate=0.5, 
            ctrl_var=self.ramp_ctrl_var,
            dependent_var=self.ramp_dependent_var,
            ctrl_var_ui=self.var_F)
            
        self.filament_lifetime_tracker = common.FilamentLifetimeTracker(
            menu=self.menu_extra, 
            targetA=22,
            filename='lifetime_mesh_filament_'+aname[0][:2]+'.txt')

        
        
    def ramp_ctrl_var(self, v=-1):
        if v<0:
            return self.F
        self.F = v
        self.send_message('rampV '+str(self.F*self.coef_F_ctrl))
        return None

    def ramp_dependent_var(self):
        return self.FR

 
    def arc_start(self, s):
        res = self.send_message('arcStart '+str(s))
        print('arcStart '+str(s), res)
        if res != 'ok':
            print(res)        

       
        
    def show_menu(self, event):
        self.filament_lifetime_tracker.show_lifetime()
        super().show_menu(event)
        


    def get_data(self):
        super().get_data()
        self.filament_ramper.on_get_data()
        self.filament_lifetime_tracker.update(self.F)
        
        
        
    def update_ui(self):
        super().update_ui()
        self.filament_ramper.on_update_ui()


