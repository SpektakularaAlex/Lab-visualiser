import tkinter as tki
#import time
import threading
import tooltip

import common


class CommonPS():
    def __init__(self, 
                box, 
                term_serv_addr, 
                port, 
                aname='magnet', 
                control_I_or_V='I', # I, V, or IF
                presets=None, 
                coef_ctrl=1.0, 
                coef_I_read=1.0, 
                coef_V_read=1.0,
                minmax_I=(5, 7, 10),  # min_ok, max_ok, max
                minmax_V=(5, 7, 10),  # min_ok, max_ok, max
                units_I='mA',
                units_V='kV',
                d_ctrl=0.01,       
                coef_F_ctrl=1.0, # ----> arc/filament specific stuff from here on
                coef_F_read=1.0,
                minmax_F=(5, 7, 10),  # min_ok, max_ok, max
                units_F='A'): 
        self.the_name = aname
        if control_I_or_V == 'IF':
            self.has_extra_filament = True
            control_I_or_V = 'I'
        else:
            self.has_extra_filament = False
        self.control_I_or_V = control_I_or_V
        self.coef_ctrl = coef_ctrl
        self.coef_I_read = coef_I_read
        self.coef_V_read = coef_V_read
        self.minmax_I = minmax_I
        self.minmax_V = minmax_V
        self.minmax_ctrl = minmax_I if control_I_or_V=='I' else minmax_V
        self.units_I = units_I
        self.units_V = units_V
        self.coef_F_ctrl = coef_F_ctrl
        self.coef_F_read = coef_F_read
        self.minmax_F = minmax_F
        self.units_F = units_F

        if self.has_extra_filament:
            box.place(height=142)
            s = 'Arc:'
        else:    
            box.place(height=92)
            s = 'Set '+control_I_or_V+':'

        self.chb_currentSet = tki.Label(master=box, text=s)
        self.chb_currentSet.place(x=0, y=3)
        self.chb_currentRead = tki.Checkbutton(master=box, text='I = -1 A')
        self.chb_currentRead.place(x=2, y=28)
        self.chb_voltageRead = tki.Checkbutton(master=box, text='U = -1 V')
        self.chb_voltageRead.place(x=2, y=47)
        if self.has_extra_filament:
            self.chb_filamentSet = tki.Label(master=box, text='Filament:')
            self.chb_filamentSet.place(x=0, y=47+25)
            self.chb_filamentRead = tki.Checkbutton(master=box, text='I = -1 A')
            self.chb_filamentRead.place(x=2, y=47+25+25)
            self.the_checkbuttons = [self.chb_currentRead, self.chb_voltageRead, self.chb_filamentRead]
            h = 81 + 25 + 25
        else:
            self.the_checkbuttons = [self.chb_currentRead, self.chb_voltageRead]
            h = 81

        self.the_canvas = tki.Canvas(master=box, width=166, height=h)
        self.the_canvas.place(x=120, y=-15)
        self.the_canvas.bind('<Button-1>', self.on_click_canvas)
        self.rect_ctrl = r = (2, 2, 166, 14)
        self.the_canvas.create_rectangle(r[0]-1, r[1]-1, r[2], r[3], fill='', outline='black')                   # outline: (1,1,width,h) to fill canvas and be visible
        self.bar_ctrl = self.the_canvas.create_rectangle(*r, fill='#44cc44', outline='') # fill: (2,2,width,h) to fill the outline without covering it
        self.bartxt_ctrl = self.the_canvas.create_text(r[0]+1, r[1]-1, text='NOT CONNECTED', anchor='nw')
        self.rect_I = r = (2, 48, 166, 49+13)
        self.the_canvas.create_rectangle(r[0]-1, r[1]-1, r[2], r[3], fill='', outline='black')                   # outline: (1,1,width,h) to fill canvas and be visible
        self.bar_I_ma = self.the_canvas.create_rectangle(*r, fill='#ff00ff', outline='') # fill: (2,2,width,h) to fill the outline without covering it
        self.bar_I_mi = self.the_canvas.create_rectangle(*r, fill='#44cc44', outline='') # fill: (2,2,width,h) to fill the outline without covering it
        self.bartxt_I = self.the_canvas.create_text(r[0]+1, r[1]-1, text='0.007', anchor='nw')
        self.rect_V = r = (2, 67, 166, 68+13)
        self.the_canvas.create_rectangle(r[0]-1, r[1]-1, r[2], r[3], fill='', outline='black')                   # outline: (1,1,width,h) to fill canvas and be visible
        self.bar_V_ma = self.the_canvas.create_rectangle(*r, fill='#ff00ff', outline='') # fill: (2,2,width,h) to fill the outline without covering it
        self.bar_V_mi = self.the_canvas.create_rectangle(*r, fill='#44cc44', outline='') # fill: (2,2,width,h) to fill the outline without covering it
        self.bartxt_V = self.the_canvas.create_text(r[0]+1, r[1]-1, text='0.007', anchor='nw')
        self.bar_ctrl_clr = '#44cc44'
        self.bar_I_clr = '#44cc44'
        self.bar_V_clr = '#44cc44'
        if self.has_extra_filament:
            self.rect_F = r = (2, 117, 166, 118+13)
            self.the_canvas.create_rectangle(r[0]-1, r[1]-1, r[2], r[3], fill='', outline='black')                   # outline: (1,1,width,h) to fill canvas and be visible
            self.bar_F_ma = self.the_canvas.create_rectangle(*r, fill='#ff00ff', outline='') # fill: (2,2,width,h) to fill the outline without covering it
            self.bar_F_mi = self.the_canvas.create_rectangle(*r, fill='#44cc44', outline='') # fill: (2,2,width,h) to fill the outline without covering it
            self.bartxt_F = self.the_canvas.create_text(r[0]+1, r[1]-1, text='0.007', anchor='nw')
            self.bar_F_clr = '#44cc44'
        self.canvas_show_stats = False
        self.canvas_show_stats_prev = True
        
        self.var_current = tki.StringVar()
        self.var_current.set('0.000')
        self.txt_current = tki.Entry(master=box, textvariable=self.var_current)
        self.txt_current.place(x=122, y=2, width=50)
        self.txt_current.bind('<Return>', self.on_currentReturn)
        self.txt_current.bind('<KP_Enter>', self.on_currentReturn)
        #self.txt_current.bind('<MouseWheel>', lambda ev: self.set_dI(0.01 if ev.delta>0 else -0.01))
        # on linux bind('<MouseWheel>') does not work...
        self.txt_current.bind('<Button-4>', lambda _ev: self.set_dI( d_ctrl))
        self.txt_current.bind('<Button-5>', lambda _ev: self.set_dI(-d_ctrl))
        if self.has_extra_filament:
            self.var_filament = tki.StringVar()
            self.var_filament.set('0.000')
            self.txt_filament = tki.Entry(master=box, textvariable=self.var_filament)
            self.txt_filament.place(x=122, y=47+25, width=50)
            self.txt_filament.bind('<Return>', self.on_filamentReturn)
            self.txt_filament.bind('<KP_Enter>', self.on_filamentReturn)
            self.txt_filament.bind('<Button-4>', lambda _ev: self.set_dF( 0.1))
            self.txt_filament.bind('<Button-5>', lambda _ev: self.set_dF(-0.1))

            btn = tki.Button(master=box, text=chr(9652), command=lambda: self.set_dF(0.1)) # ▴
            btn.place(x=172, y=1+45+25, width=20, height=14)
            tooltip.ToolTip(btn, '+0.1')
            btn = tki.Button(master=box, text=chr(9650), command=lambda: self.set_dF(1.0))  # ▲
            btn.place(x=192, y=1+45+25, width=20, height=14)
            tooltip.ToolTip(btn, '+1')
            btn = tki.Button(master=box, text=chr(9662), command=lambda: self.set_dF(-0.1)) # ▾
            btn.place(x=172, y=15+45+25, width=20, height=14)
            tooltip.ToolTip(btn, '-0.1')
            btn = tki.Button(master=box, text=chr(9660), command=lambda: self.set_dF(-1.0)) # ▼
            btn.place(x=192, y=15+45+25, width=20, height=14)
            tooltip.ToolTip(btn, '-1')

        '''(a, b, c, d) = self.rect_ctrl
        self.the_canvas.coords(self.bar_ctrl, a, b, c*0.7, d)
        self.the_canvas.itemconfigure(self.bar_ctrl, fill='#ff8888')
        (a, b, c, d) = self.rect_VR
        self.the_canvas.coords(self.bar_VR_ma, a, b, c*1, d)
        self.the_canvas.coords(self.bar_VR_mi, a, b, c*0.7, d)
        #self.the_canvas.itemconfigure(self.bar_VR_mi, fill='#ff8888')'''
        
        
        btn = tki.Button(master=box, text=chr(9652), command=lambda: self.set_dI(0.01)) # ▴
        btn.place(x=172, y=1, width=20, height=14)
        tooltip.ToolTip(btn, '+0.01')
        btn = tki.Button(master=box, text=chr(9650), command=lambda: self.set_dI(0.1))  # ▲
        btn.place(x=192, y=1, width=20, height=14)
        tooltip.ToolTip(btn, '+0.1')
        btn = tki.Button(master=box, text=chr(9662), command=lambda: self.set_dI(-0.01)) # ▾
        btn.place(x=172, y=15, width=20, height=14)
        tooltip.ToolTip(btn, '-0.01')
        btn = tki.Button(master=box, text=chr(9660), command=lambda: self.set_dI(-0.1)) # ▼
        btn.place(x=192, y=15, width=20, height=14)
        tooltip.ToolTip(btn, '-0.1')

        self.lbl_restarts = tki.Label(master=box, text='rs: 0', font=('', 8))
        self.lbl_restarts.place(x=290, y=30)
        self.lbl_restarts.bind("<ButtonRelease-3>", self.clear_fails)
        self.lbl_comfails = tki.Label(master=box, text='cf: 0', font=('', 8))
        self.lbl_comfails.place(x=290, y=42)
        self.lbl_comfails.bind("<ButtonRelease-3>", self.clear_fails)

        if presets is None:
            presets = []
        for i in range(len(presets)):
            btn = tki.Button(master=box, text=presets[i][0], command=lambda v=presets[i][1]: self.set_I(v))
            btn.place(x=214+i*32, y=1, width=31 if len(presets)>1 else 41, height=28)
            tooltip.ToolTip(btn, presets[i][1])

        btn = tki.Button(master=box, text='Turn Off', command=self.switchOff)
        btn.place(x=280, y=1, width=63, height=28)
        
        self.current = 0.0
        self.CR = 0.0
        self.VR = 0.0
        self.stats_minI = 5.1
        self.stats_maxI = 5.8
        self.stats_minV = 1.0
        self.stats_maxV = 1.1
        self.filament = 0.0
        self.FR = 0.0
        self.stats_minF = 5.1
        self.stats_maxF = 5.8
        
        
        self.restarted_count = 0
        self.comfails_count = 0
        self.fail_count = 0
        self.interlock_open = False
        self.HV_off = False
        self.comfail = False
        
        #btn = tki.Button(master=box, text='clr', command=self.clear_fails)
        #btn.place(x=320, y=-2, width=20, height=16)
        
        self.the_lock = threading.Lock()
        self.the_socket, sockok = common.connect_socket(term_serv_addr, port, aname)
        
        self.the_probes =[(self.get_probe_I, 'I'), (self.get_probe_V, 'V')]
        if self.has_extra_filament:
            self.the_probes.append((self.get_probe_F, 'Filament I'))
        
        self.AI_rate = 5 # 0 to 7; noise level and max-min are ca 2x lower for rate=R vs rate=R+2
        AI_samples_per_s = [4, 7, 15, 30, 58, 107, 181, 292]
        self.AI_timestep_ms = 1000.0/AI_samples_per_s[self.AI_rate]
        
        if sockok:
            self.send_message('setRate '+str(self.AI_rate))
            try:
                # ctrl_value_here * coef_ctrl = ctrl_value_pico
                self.current = float(self.send_message('getSet'+control_I_or_V)) / coef_ctrl
                self.var_current.set('{:.3f}'.format(self.current))
                if self.has_extra_filament:
                    self.filament = float(self.send_message('getSetV')) / coef_F_ctrl
                    self.var_filament.set('{:.3f}'.format(self.filament))
                print(self.the_name, self.send_message('version'))
            except:
                pass
                
        
    def clear_fails(self, _ev):
        self.restarted_count = 0
        self.comfails_count = 0
        
    def on_click_canvas(self, _ev):
        self.canvas_show_stats = not self.canvas_show_stats
        self.update_ui()

        
    def send_message(self, msg):
        return common.send_socket_message(self.the_socket, msg, self.the_lock)
    
    def get_probe_I(self):
        ar = common.send_socket_message_array(self.the_socket, 'arrayI', self.the_lock)
        try:
            r = ([i*self.AI_timestep_ms for i in range(len(ar))], [v*self.coef_I_read for v in ar])
        except:
            r =  ([i*self.AI_timestep_ms for i in range(100)], [i*20 for i in range(100)])
        return r
        
    def get_probe_V(self):
        ar = common.send_socket_message_array(self.the_socket, 'arrayV', self.the_lock)
        try:
            r = ([i*self.AI_timestep_ms for i in range(len(ar))], [v*self.coef_V_read for v in ar])
        except:
            r = ([i*self.AI_timestep_ms for i in range(100)], [i*20 for i in range(100)])
        return r

    def get_probe_F(self):
        ar = common.send_socket_message_array(self.the_socket, 'array3', self.the_lock)
        try:
            r = ([i*self.AI_timestep_ms for i in range(len(ar))], [v*self.coef_F_read for v in ar])
        except:
            r = ([i*self.AI_timestep_ms for i in range(100)], [i*20 for i in range(100)])
        return r
        
        
    def switchOff(self):
        self.var_current.set('0.000')
        self.on_currentReturn(None)
        if self.has_extra_filament:
            self.var_filament.set('0.000')
            self.on_filamentReturn(None)
        
        
    '''def set_to_07(self):
        self.var_current.set('0.700')
        self.on_currentReturn(None)'''
        
    def set_I(self, v):
        self.var_current.set('{:.3f}'.format(v))
        self.on_currentReturn(None)

    def set_F(self, v):
        self.var_filament.set('{:.3f}'.format(v))
        self.on_filamentReturn(None)
    
    def set_dI(self, dI):
        c = float(self.var_current.get())
        self.var_current.set('{:.3f}'.format(c + dI))
        self.on_currentReturn(None)

    def set_dF(self, dI):
        c = float(self.var_filament.get())
        self.var_filament.set('{:.3f}'.format(c + dI))
        self.on_filamentReturn(None)

    def on_destroy(self):
        self.the_socket.close()
        print(self.the_name+' socket closed.')

    
    def get_data(self):
        r = self.send_message('get')
        rr = r.split(' ')
        # setI, setV, flags, cnt, Iread, Imin, Imax, Vread, Vmin, Vmax, Fread, Fmin, Fmax
        if len(rr) > 12:
            try:
                if self.control_I_or_V == 'I':
                    self.current = float(rr[0])/self.coef_ctrl
                else:
                    self.current = float(rr[1])/self.coef_ctrl
                f = int(rr[2])
                self.stats_cnt = int(rr[3])
                self.CR = float(rr[4])*self.coef_I_read
                self.stats_minI = float(rr[5])*self.coef_I_read
                self.stats_maxI = float(rr[6])*self.coef_I_read
                self.VR = float(rr[7])*self.coef_V_read
                self.stats_minV = float(rr[8])*self.coef_V_read
                self.stats_maxV = float(rr[9])*self.coef_V_read
                if self.has_extra_filament:
                    self.filament = float(rr[1])/self.coef_F_ctrl
                    self.FR = float(rr[10])*self.coef_F_read
                    self.stats_minF = float(rr[11])*self.coef_F_read
                    self.stats_maxF = float(rr[12])*self.coef_F_read
            except:
                print(r, rr)
                f = -1
        else:
            f = -1
        if f < 0:
            self.comfails_count += 1
            self.comfail = True
        if f > 0  and  f & 128:
            self.restarted_count += 1
            self.send_message('ok')
        if f > 0:
            self.interlock_open = bool(f & 64) # interlock open
            self.HV_off = bool(f & 256)
            self.comfail = False

        if self.has_extra_filament:
            self.last_ret = [(self.CR, self.stats_minI, self.stats_maxI), (self.VR, self.stats_minV, self.stats_maxV), (self.FR, self.stats_minF, self.stats_maxF)]
        else:
            self.last_ret = [(self.CR, self.stats_minI, self.stats_maxI), (self.VR, self.stats_minV, self.stats_maxV)]
        
        
    def update_ui(self):
        if self.has_extra_filament:
            self.chb_currentSet.configure(text='Arc: {:.3f} '.format(self.current)+self.units_I)
        elif self.control_I_or_V =='I':        
            self.chb_currentSet.configure(text='Set I = {:.3f} '.format(self.current)+self.units_I)
        else:
            self.chb_currentSet.configure(text='Set V = {:.3f} '.format(self.current)+self.units_V)
        self.chb_currentRead.configure(text='I = {:.3f} '.format(self.CR)+self.units_I)
        self.chb_voltageRead.configure(text='U = {:.3f} '.format(self.VR)+self.units_V)
        if self.has_extra_filament:
            self.chb_filamentSet.configure(text='Filament: {:.3f} '.format(self.filament)+self.units_F)
            self.chb_filamentRead.configure(text='FI = {:.3f} '.format(self.FR)+self.units_F)
            
        #self.lbl_flags.configure(text=self.FR)
        if self.canvas_show_stats:
            self.the_canvas.itemconfigure(self.bartxt_I, text='({:.3f} .. {:.3f})'.format(self.stats_minI, self.stats_maxI))
            self.the_canvas.itemconfigure(self.bartxt_V, text='({:.3f} .. {:.3f})'.format(self.stats_minV, self.stats_maxV))
            if self.has_extra_filament:
                self.the_canvas.itemconfigure(self.bartxt_F, text='({:.3f} .. {:.3f})'.format(self.stats_minF, self.stats_maxF))
            self.canvas_show_stats_prev = True
        elif self.canvas_show_stats_prev:
            self.the_canvas.itemconfigure(self.bartxt_I, text='')
            self.the_canvas.itemconfigure(self.bartxt_V, text='')
            if self.has_extra_filament:
                self.the_canvas.itemconfigure(self.bartxt_F, text='')
            self.canvas_show_stats_prev = False
        
        ctrltxt = ''
        if self.interlock_open: ctrltxt += 'Interlock open! '
        if self.HV_off        : ctrltxt += 'HV off '
        if self.comfail       : ctrltxt  = 'No connection'
        
        self.the_canvas.itemconfigure(self.bartxt_ctrl, text=ctrltxt)
        
        #self.lbl_currentExtra.configure(text='±{:.3f} ({:.3f} .. {:.3f})'.format(self.stats_stdevI, self.stats_minI, self.stats_maxI))
        #self.lbl_voltageExtra.configure(text='±{:.3f} ({:.3f} .. {:.3f})'.format(self.stats_stdevV, self.stats_minV, self.stats_maxV))
        if self.fail_count != self.restarted_count + self.comfails_count:
            self.lbl_restarts.configure(text='rs: '+str(self.restarted_count))
            self.lbl_comfails.configure(text='cf: '+str(self.comfails_count))
            self.fail_count = self.restarted_count + self.comfails_count
        
        self.bar_ctrl_clr = self.update_bars(self.minmax_ctrl, self.rect_ctrl, self.bar_ctrl, self.current   , self.bar_ctrl_clr)
        self.bar_I_clr    = self.update_bars(self.minmax_I   , self.rect_I   , self.bar_I_mi, self.stats_minI, self.bar_I_clr, self.bar_I_ma, self.stats_maxI)
        self.bar_V_clr    = self.update_bars(self.minmax_V   , self.rect_V   , self.bar_V_mi, self.stats_minV, self.bar_V_clr, self.bar_V_ma, self.stats_maxV)
        if self.has_extra_filament:
            self.bar_F_clr    = self.update_bars(self.minmax_F   , self.rect_F   , self.bar_F_mi, self.stats_minF, self.bar_F_clr, self.bar_F_ma, self.stats_maxF)
        '''(miok, maok, ma) = self.minmax_ctrl
        (a, b, c, d) = self.rect_ctrl
        self.the_canvas.coords(self.bar_ctrl, a, b, c*self.current/ma, d)
        clr = '#ff8888' if (self.current<miok or self.current>maok) else '#44cc44'
        self.the_canvas.itemconfigure(self.bar_ctrl, fill=clr)
        (a, b, c, d) = self.rect_VR
        self.the_canvas.coords(self.bar_VR_ma, a, b, c*1, d)
        self.the_canvas.coords(self.bar_VR_mi, a, b, c*0.7, d)'''


    def update_bars(self, minmax, rect, bar, v, oldclr, bar2=None, v2=0):
        (miok, maok, ma) = minmax
        (a, b, c, d) = rect
        if bar2 is None:
            v2 = v
        else:
            self.the_canvas.coords(bar2, a, b, c*v2/ma, d)
        self.the_canvas.coords(bar, a, b, c*v/ma, d)
        clr = '#ff8888' if (v<miok or v2>maok) else '#44cc44'
        #print(minmax, v, v2)
        if clr != oldclr:
            self.the_canvas.itemconfigure(bar, fill=clr)
        return clr
        
            
        

    def on_currentReturn(self, _event):
        c = float(self.var_current.get())
        if self.has_extra_filament:
            cmd = 'rampAnode'
        else:
            cmd = 'ramp' + self.control_I_or_V
        print(cmd, '-->', c, c*self.coef_ctrl)
        res=self.send_message(cmd+' '+str(c*self.coef_ctrl))
        if res != 'ok':
            print(res)
        self.update_ui()

    def on_filamentReturn(self, _event):
        c = float(self.var_filament.get())
        cmd = 'rampFilament'
        print(cmd, '-->', c, c*self.coef_F_ctrl)
        res=self.send_message(cmd+' '+str(c*self.coef_F_ctrl))
        if res != 'ok':
            print(res)
        self.update_ui()


if __name__ == '__main__':
    root = tki.Tk()
    root.title('test')
    root.geometry('350x350')
    abox = tki.LabelFrame(master=root, text='test')
    #(filament.Filament  , TERM_SERV_ADDR, 1, 'Filament' ),#   , ctrl, presets          , ctrl_coef, I_read_coef    , V_read_coef   , I_read_min_max           , V_read_min_max              , I_units, V_units, dctrl, coef_F_ctrl, coef_F_read,       F_read_min_max  
    #ps = CommonPS(abox, '1.2.3.4', 17, 'Magnet', 'V', [('0.7', 0.7), ('24',24)])
    #ps = CommonPS(abox, '192.168.2.7', 6, 'Neutral trap'    , 'V' , [('1kV',  1)      ], 5.0/ 3   , 0.000044868*5  , 0.00004533* 3 , (0, 2,   5*0+0.115*2)    , (0   ,    3,   3*0+1.1*2), 'mA'   , 'kV'   , 0.005) # 5mA, 3kV
    ps = CommonPS(abox, '192.168.2.7', 10, 'Arc/Filament'    , 'IF' , [                ], 5.0/10.0 , 3.0/0.719/32768.0, 250.0/0.979/32768.0 , (1.3, 1.7, 3*0+1.5*2)    , (50 , 90, 250*0+75*2), 'A'   , 'V'   , 0.005, 5.0/50.0    , 30.0/0.228/32768.0, (0, 27, 30), 'A') # 5mA, 3kV
    abox.place(x=0, y= 0, width=350)
    ps.get_data()
    ps.update_ui()
    def tst():
        ps.get_data()
        ps.update_ui()
    tt = tki.Button(root, text='update', command=tst)
    tt.place(x=5, y=300)
    root.mainloop()


