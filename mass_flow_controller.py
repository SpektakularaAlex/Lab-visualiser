import commonPS2
#import common
import time

class MassFlowController(commonPS2.CommonPS):
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
        if self.the_socket.connected:
            try:
                self.current = float(self.send_message('SP')[3:])
                self.var_current_set(self.current)
                
                print(self.send_message('G,13')) # 3 N, 13 H
                print(self.send_message('U,%FS')) # %FS, Sml/min
            except Exception as ex:
                print('Exception in MFC:', ex)
        else:
            print('MFC socket is not ok')
            
    def send_message(self, msg):
        ret = self.the_socket.send_message(msg, term='\r')
        return ret.strip('\r\n ><')
        
    def get_data(self):
        t0 = time.time()
        rf = self.send_message('FM') # read mass flow rate
        t1 = time.time()
        rp = self.send_message('GP') # read gass pressure
        print((t1-t0)*1000, (time.time()-t1)*1000)
        try:
            self.CR = float(rf)
            self.stats_minI = self.CR
            self.stats_maxI = self.CR
            self.VR = float(rp)
            self.stats_minV = self.VR
            self.stats_maxV = self.VR
            self.comfail = False
        except Exception as ex:
            if rf != 'timeout' and rp != 'timeout':
                print(time.strftime('%H:%M:%S'), 'Exception in MFC.get_data:', rf, rp, ex)
            self.comfails_count += 1
            self.comfail = True
            
        #reg = self.gas_regulator.get()
        #if reg != 0 and self.gas == 'on' and v>5 and v<6:
        #    print('Regulating pressure:')
        #    self.moveValve(-5 if reg<0 else 5)

        
        self.last_ret = [self.CR, self.VR]
        self.last_ctrl = [self.current]

    def set_flow(self, c):
        #print(self.send_message('GP'))# V.M,A
        valve = 'A' if self.VR > 2 and self.VR < 20 and c > 0 else 'C' # open valve if pressure is between 2 and 12 psi, and if flow is non-zero
        self.send_message('V,M,'+valve)# V.M,A
        r = self.send_message('SP,'+str(c))
        print(r)
        try:
            self.current = float(r[3:])
        except Exception as ex:
            print('Set flow in MFC failed,', ex)
        

    def on_currentReturn(self, _event):
        #super().on_currentReturn(_event)
        c = float(self.var_current.get())
        self.set_flow(c)
        self.update_ui()
        
               
