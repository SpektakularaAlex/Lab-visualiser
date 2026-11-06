import tkinter as tki
#import time
#import threading
import tooltip
import tkinter.messagebox

import common


class CommonPS(common.Anitem):
    def __init__(self, 
                box, box2, 
                term_serv_addr, 
                port, 
                aname=('magnet', 'magnet'), 
                control_I_or_V='I', 
                presets=None, 
                coef_ctrl=1.0, 
                coef_I_read=1.0, 
                coef_V_read=1.0,
                minmax_ctrl=None,
                minmax_I=(5, 7, 10),  # min_ok, max_ok, max
                minmax_V=(5, 7, 10),  # min_ok, max_ok, max
                units_ctrl='mA',
                units_I='mA',
                units_V='kV',
                d_ctrl = 0.01,
                coef_F_ctrl=0, # ----> second control/third readout specific stuff from here on
                coef_F_read=0,
                minmax_F=(5, 7, 10),  # min_ok, max_ok, max
                units_F='A'):
        super().__init__()
        hei_i = 0 if coef_I_read==0 else 19
        hei_v = 0 if coef_V_read==0 else 19
        boxheight = 54 + hei_i + hei_v
        box.place(height=boxheight)
        #self.the_name = aname
        self.control_I_or_V = control_I_or_V
        self.coef_ctrl = coef_ctrl
        self.coef_I_read = coef_I_read
        self.coef_V_read = coef_V_read
        self.minmax_I = minmax_I
        self.minmax_V = minmax_V
        if minmax_ctrl is None:
            self.minmax_ctrl = minmax_I if control_I_or_V=='I' else minmax_V
        else:
            self.minmax_ctrl = minmax_ctrl
        self.units_ctrl = units_ctrl[1] if isinstance(units_ctrl, tuple) else units_ctrl
        self.units_I = units_I[1] if isinstance(units_I, tuple) else units_I
        self.units_V = units_V[1] if isinstance(units_V, tuple) else units_V
        self.d_ctrl = d_ctrl
        self.coef_F_ctrl = coef_F_ctrl
        self.coef_F_read = coef_F_read
        self.minmax_F = minmax_F
        self.units_F = units_F[-1] if isinstance(units_F, tuple) else units_F
        
        self.d_F = 0.01 # todo: must be a parameter
        self.descr_ctrl = units_ctrl[0] if isinstance(units_ctrl, tuple) else control_I_or_V
        self.descr_I = units_I[0] if isinstance(units_I, tuple) else 'I'
        self.descr_V = units_V[0] if isinstance(units_V, tuple) else 'U'
        self.descr_F_ctrl = units_F[0] if isinstance(units_F, tuple) else 'F'
        self.descr_F = 'F' if isinstance(units_F, str) else units_F[0] if len(units_F)<3 else units_F[1]
        
        self.last_names = [aname[0].split('/')[0]]
        if self.coef_ctrl   != 0: self.last_names.append(self.descr_ctrl)
        if self.coef_I_read != 0: self.last_names.append(self.descr_I)
        if self.coef_V_read != 0: self.last_names.append(self.descr_V)
        
        if self.coef_ctrl != 0:
            self.chb_currentSet = tki.Label(master=box, text='Set '+self.descr_ctrl+' = -1 A')
            self.chb_currentSet.place(x=0, y=3)
            common.set_text(self.chb_currentSet)
        
        self.the_socket = common.SocketOrSerial(term_serv_addr, port, aname[0])

        if coef_I_read != 0:
            self.chb_currentRead = tki.Checkbutton(master=box, text=self.descr_I+' = -1 A')
            self.chb_currentRead.place(x=2, y=28)
            common.set_text(self.chb_currentRead)
        
        if coef_V_read != 0:
            self.chb_voltageRead = tki.Checkbutton(master=box, text=self.descr_V+' = -1 V')
            self.chb_voltageRead.place(x=2, y=28+hei_i)
            common.set_text(self.chb_voltageRead)

        self.the_canvas = tki.Canvas(master=box, width=166, height=43+hei_i+hei_v)
        self.the_canvas.place(x=120, y=-16)
        self.the_canvas.bind('<Button-1>', self.on_click_canvas)
        self.bar_ctrl = common.ABar(self.the_canvas, y= 2, minmax=self.minmax_ctrl, twobars=False, name=aname[0]+' set value')
        if coef_I_read != 0:
            self.bar_I    = common.ABar(self.the_canvas, y=48      , minmax=self.minmax_I   , twobars=True, name=aname[0]+' I')
        if coef_V_read!=0:
            self.bar_V    = common.ABar(self.the_canvas, y=48+hei_i, minmax=self.minmax_V   , twobars=True, name=aname[0]+' V')
        self.canvas_show_stats = False
        
        if self.coef_ctrl != 0:
            self.var_current = tki.StringVar()
            self.var_current_set(0)
            self.txt_current = tki.Entry(master=box, textvariable=self.var_current)
            self.txt_current.place(x=122, y=2, width=50)
            self.txt_current.bind('<Return>', self.on_currentReturn)
            self.txt_current.bind('<KP_Enter>', self.on_currentReturn)
            #self.txt_current.bind('<MouseWheel>', lambda ev: self.set_dI(0.01 if ev.delta>0 else -0.01))
            # on linux bind('<MouseWheel>') does not work...
            self.txt_current.bind('<Button-4>', lambda _ev: self.set_dI( 1))
            self.txt_current.bind('<Button-5>', lambda _ev: self.set_dI(-1))

            
            btn = tki.Button(master=box, text=chr(9652), command=lambda: self.set_dI(1)) # ▴
            btn.place(x=172, y=1, width=20, height=14)
            self.up_down_tooltip_1 = tooltip.ToolTip(btn, '+'+str(d_ctrl))
            btn = tki.Button(master=box, text=chr(9650), command=lambda: self.set_dI(10))  # ▲
            btn.place(x=192, y=1, width=20, height=14)
            self.up_down_tooltip_10 = tooltip.ToolTip(btn, '+'+str(d_ctrl*10))
            btn = tki.Button(master=box, text=chr(9662), command=lambda: self.set_dI(-1)) # ▾
            btn.place(x=172, y=15, width=20, height=14)
            self.up_down_tooltip_m1 = tooltip.ToolTip(btn, '-'+str(d_ctrl))
            btn = tki.Button(master=box, text=chr(9660), command=lambda: self.set_dI(-10)) # ▼
            btn.place(x=192, y=15, width=20, height=14)
            self.up_down_tooltip_m10 = tooltip.ToolTip(btn, '-'+str(d_ctrl*10))

        self.lbl_restarts = tki.Label(master=box, text='rs: 0', font=('', 8))
        self.lbl_restarts.place(x=290, y=boxheight-38-12)
        self.lbl_restarts.bind("<ButtonRelease-3>", self.clear_fails)
        self.lbl_comfails = tki.Label(master=box, text='cf: 0', font=('', 8))
        self.lbl_comfails.place(x=290, y=boxheight-38)
        self.lbl_comfails.bind("<ButtonRelease-3>", self.clear_fails)

        if presets is None:
            presets = []
        for i in range(len(presets)):
            btn = tki.Button(master=box, text=presets[i][0], command=lambda v=presets[i][1]: self.set_I(v)) # type: ignore
            btn.place(x=214+i*32, y=1, width=31 if len(presets)>1 else 41, height=28)
            tooltip.ToolTip(btn, presets[i][1])

        if self.coef_ctrl != 0:
            self.txt_current.bind('<Button-3>', self.menu_save_restore_show)
            self.menu_save_restore = tki.Menu(box, tearoff=0)
            self.menu_save_restore.add_command(label='Save', command=self.menu_save_restore_save)
            self.menu_save_restore.add_command(label='Restore 0', command=self.menu_save_restore_restore)
            self.menu_save_restore.add_command(label='Cancel')
            self.menu_save_restore_value = 0.0
            self.menu_save_restore.add_separator()
            self.menu_save_restore.add_command(label='Larger steps, {:.3f}'.format(self.d_ctrl*2), command=self.menu_save_restore_larger)
            self.menu_save_restore.add_command(label='Finer steps, {:.3f}'.format(self.d_ctrl/2), command=self.menu_save_restore_finer)
            #self.menu_save_restore.bind('<FocusOut>', lambda _e: self.menu_save_restore.unpost())

            btn = tki.Button(master=box, text='Turn Off', command=self.switchOff)
            btn.place(x=289, y=-16, width=59, height=20)

        btn = tki.Button(master=box, text='...')
        btn.bind('<Button-1>', self.show_menu)
        btn.place(x=330, y=boxheight-36, width=16, height=16)
        self.menu_extra = tki.Menu(box, tearoff=0)
        self.menu_extra.add_command(label='Cancel')
        self.menu_extra.add_command(label='Restart pico controller', command=self.reset_pico)
        self.menu_extra.add_command(label='Restart DAC device', command=self.reset_dac)
        self.menu_extra.add_command(label='DAC 1 soft reset', command=lambda: self.dac_IV_reset_swhw('reset_I_sw'))
        self.menu_extra.add_command(label='DAC 2 soft reset', command=lambda: self.dac_IV_reset_swhw('reset_V_sw'))
        self.menu_extra.add_command(label='DAC 1 hard reset', command=lambda: self.dac_IV_reset_swhw('reset_I_hw 14'))
        self.menu_extra.add_command(label='DAC 2 hard reset', command=lambda: self.dac_IV_reset_swhw('reset_V_hw 14'))
        self.menu_extra.add_command(label='DAC powercycle', command=lambda: self.dac_IV_reset_swhw('reset_hw 14'))

        if not box2 is None:
            self.slave = common.Anitem()
            self.slave.the_checkbuttons = []
            self.slave.the_probes = []
            hr = 15 if self.coef_F_read>0 else 0
            hc = 25 if self.coef_F_ctrl>0 else 0
            hc2= 47 if self.coef_F_ctrl>0 else 0
            box2.place(height=33+hr+hc)
            self.the_canvas2 = tki.Canvas(master=box2, width=166, height=4+hr+hc2)
            self.the_canvas2.place(x=120, y=47-25-16+hc-hc2)#-16)
            if self.coef_F_read != 0:
                self.chb_F_read = tki.Checkbutton(master=box2, text=self.descr_F+' = -1 A')
                self.chb_F_read.place(x=2, y=3+hc)
                self.chb_F_read.lower()
                common.set_text(self.chb_F_read)
                self.slave.the_checkbuttons = [self.chb_F_read]        
                self.bar_F = common.ABar(self.the_canvas2, y=2+hc2, minmax=self.minmax_F   , twobars=True, name=aname[0]+' F')
                self.slave.the_probes = [(self.get_probe_F, 'F')]
                self.FR = 0.0
                self.stats_minF = 5.1
                self.stats_maxF = 5.8
                self.stats_deltaF = 0
            if self.coef_F_ctrl != 0:
                self.chb_F_set = tki.Label(master=box2, text='Set '+self.descr_F_ctrl+' = -1 A')
                self.chb_F_set.place(x=0, y=3)
                common.set_text(self.chb_F_set)
                
                btn = tki.Button(master=box2, text='Turn Off', command=self.switchOff2)
                btn.place(x=289, y=-16, width=59, height=20)
                self.slave.switchOff = self.switchOff2 # type: ignore
                
                self.bar_ctrlF = common.ABar(self.the_canvas2, y=2, minmax=self.minmax_F   , twobars=False, name=aname[0]+' F ctrl')
                self.var_F = tki.StringVar()
                self.var_F.set('0.00')
                self.txt_F = tki.Entry(master=box2, textvariable=self.var_F)
                self.txt_F.place(x=122, y=2, width=50)
                self.txt_F.bind('<Return>', self.on_F_return)
                self.txt_F.bind('<KP_Enter>', self.on_F_return)
                self.txt_F.bind('<Button-4>', lambda _ev: self.set_dF( 1))
                self.txt_F.bind('<Button-5>', lambda _ev: self.set_dF(-1))

                self.F = 0.0
                if self.the_socket.connected:
                    try:
                        self.F = float(self.send_message('getSetV')) / self.coef_F_ctrl
                        self.var_F_set(self.F)
                    except:
                        pass
                    
                btn = tki.Button(master=box2, text=chr(9652), command=lambda: self.set_dF(1)) # ▴
                btn.place(x=172, y=1, width=20, height=14)
                tooltip.ToolTip(btn, '+'+str(self.d_F))
                btn = tki.Button(master=box2, text=chr(9650), command=lambda: self.set_dF(10))  # ▲
                btn.place(x=192, y=1, width=20, height=14)
                tooltip.ToolTip(btn, '+'+str(self.d_F*10))
                btn = tki.Button(master=box2, text=chr(9662), command=lambda: self.set_dF(-1)) # ▾
                btn.place(x=172, y=15, width=20, height=14)
                tooltip.ToolTip(btn, '-'+str(self.d_F))
                btn = tki.Button(master=box2, text=chr(9660), command=lambda: self.set_dF(-10)) # ▼
                btn.place(x=192, y=15, width=20, height=14)
                tooltip.ToolTip(btn, '-'+str(self.d_F*10))
                
            self.slave.last_names = [aname[0].split('/')[1]]
            if self.coef_F_ctrl != 0: self.slave.last_names.append(self.descr_F_ctrl)
            if self.coef_F_read != 0: self.slave.last_names.append(self.descr_F)        
                



        self.current = 0.0
        self.CR = 0.0
        self.VR = 0.0
        self.stats_minI = 5.1
        self.stats_maxI = 5.8
        self.stats_minV = 1.0
        self.stats_maxV = 1.1
        self.stats_deltaI = 0
        self.stats_deltaV = 0
        
        self.restarted_count = 0
        self.comfails_count = 0
        self.fail_count = 0
        self.interlock_open = False
        self.HV_off = False
        self.arc_start_flag = False
        self.comfail = False
        self.dac_fail = False
        
        #self.the_lock = threading.Lock()
        
        self.on_change_ctrl_proc = None
        
        self.AI_rate = 5 # 0 to 7; noise level and max-min are ca 2x lower for rate=R vs rate=R+2
        AI_samples_per_s = [4, 7, 15, 30, 58, 107, 181, 292]
        self.AI_timestep_ms = 1000.0/AI_samples_per_s[self.AI_rate]
        
        self.has_geta = False
        vv = ''
        if self.the_socket.connected:
            vv = self.send_message('version')
            if 'hasgeta' in vv and term_serv_addr != 'rem':
                self.has_geta = True
            if self.the_socket.connected:
                print(aname[0], vv)
            
        if self.the_socket.connected and not 'Error' in vv:
            try:
                #self.send_message('ok') # !!!!!!!!! debug only, remove!
                self.send_message('setRate '+str(self.AI_rate))
                if self.coef_ctrl != 0:
                    self.current = float(self.send_message('getSet'+control_I_or_V)) / coef_ctrl
                    self.var_current_set(self.current)
                #print('version:')
            except Exception as ex:
                print('Exception in ', aname[0], 'current and version get:', ex)
                self.the_socket.connected = False
        if not self.the_socket.connected:
            print(aname[0], 'socket is not ok')

        self.the_probes =[]
        self.the_checkbuttons = []
        if coef_I_read != 0:
            self.the_probes.append((self.get_probe_I, 'I'))
            self.the_checkbuttons.append(self.chb_currentRead)
        if coef_V_read != 0:
            self.the_probes.append((self.get_probe_V, 'V'))
            self.the_checkbuttons.append(self.chb_voltageRead)
        
        
    def var_current_set(self, v):
        if v >= 10.0:
            self.var_current.set('{:.2f}'.format(v))
        else:
            self.var_current.set('{:.3f}'.format(v))
        
    def var_F_set(self, v):
        if v >= 10.0:
            self.var_F.set('{:.2f}'.format(v))
        else:
            self.var_F.set('{:.3f}'.format(v))

    def update_up_down_tooltips(self):
        self.up_down_tooltip_1  .text='+{:.3f}'.format(self.d_ctrl)
        self.up_down_tooltip_10 .text='+{:.3f}'.format(self.d_ctrl*10)
        self.up_down_tooltip_m1 .text='-{:.3f}'.format(self.d_ctrl)
        self.up_down_tooltip_m10.text='-{:.3f}'.format(self.d_ctrl*10)
        self.menu_save_restore.entryconfig(4, label='Larger steps, {:.3f}'.format(self.d_ctrl*2))
        self.menu_save_restore.entryconfig(5, label='Finer steps, {:.3f}'.format(self.d_ctrl/2))
        
    def menu_save_restore_larger(self):
        self.d_ctrl *= 2
        self.update_up_down_tooltips()
        
    def menu_save_restore_finer(self):
        self.d_ctrl /= 2
        self.update_up_down_tooltips()

    def menu_save_restore_show(self, event):
        try:
            value = float(self.var_current.get())
            self.menu_save_restore.entryconfig(0, label='Save    {:.3f}'.format(value))
            self.menu_save_restore.tk_popup(event.x_root-event.x, event.y_root-event.y+20)
        finally:
            pass#self.menu_save_restore.grab_release()
            
    def menu_save_restore_save(self):
        self.menu_save_restore_value = float(self.var_current.get())
        self.menu_save_restore.entryconfig(1, label='Restore {:.3f}'.format(self.menu_save_restore_value))
        
    def menu_save_restore_restore(self):
        self.set_I(self.menu_save_restore_value)
            
    def show_menu(self, event):
        try:
            self.menu_extra.tk_popup(event.x_root, event.y_root)
        finally:
            pass#self.menu_extra.grab_release()

    def reset_pico(self):
        print(self.send_message('restartPico'))

    def reset_dac(self):
        print(self.send_message('restartDAC'))
        
    def dac_IV_reset_swhw(self, m):
        tkinter.messagebox.showinfo(message=self.send_message(m))
        
    def clear_fails(self, _ev):
        self.restarted_count = 0
        self.comfails_count = 0
        self.dac_fail = False
        
    def on_click_canvas(self, _ev):
        self.canvas_show_stats = not self.canvas_show_stats
        self.update_ui()

        
    def send_message(self, msg):
        return self.the_socket.send_message(msg)

    def send_message_array(self, msg, cnt):
        return self.the_socket.send_message_array(msg, bytecnt=cnt)

    
    def get_probe_I(self):
        ar = self.the_socket.send_message_array('arrayI')
        try:
            r = ([i*self.AI_timestep_ms for i in range(len(ar))], [v*self.coef_I_read for v in ar])
        except:
            r =  ([i*self.AI_timestep_ms for i in range(100)], [i*20 for i in range(100)])
        return r
        
    def get_probe_V(self):
        ar = self.the_socket.send_message_array('arrayV')
        try:
            r = ([i*self.AI_timestep_ms for i in range(len(ar))], [v*self.coef_V_read for v in ar])
        except:
            r = ([i*self.AI_timestep_ms for i in range(100)], [i*20 for i in range(100)])
        return r
        
    def get_probe_F(self):
        ar = self.the_socket.send_message_array('array3')
        try:
            r = ([i*self.AI_timestep_ms for i in range(len(ar))], [v*self.coef_F_read for v in ar])
        except:
            r = ([i*self.AI_timestep_ms for i in range(100)], [i*20 for i in range(100)])
        return r
        
        
    def switchOff(self):
        if self.coef_ctrl != 0:
            self.var_current_set(0)
            self.on_currentReturn(None)
        
    def switchOff2(self):
        #super().switchOff()
        if self.coef_F_ctrl != 0:
            self.var_F_set(0)
            self.on_F_return(None)        
        
    def set_I(self, v):
        self.var_current_set(v)
        self.on_currentReturn(None)
    
    def set_F(self, v):
        self.var_F_set(v)
        self.on_F_return(None)
    
    def set_dI(self, d):
        c = float(self.var_current.get())
        self.var_current_set(c + d*self.d_ctrl)
        self.on_currentReturn(None)

    def set_dF(self, d):
        c = float(self.var_F.get())
        self.var_F_set(c + d*self.d_F)
        self.on_F_return(None)
        

    def on_destroy(self):
        self.the_socket.close()
        print(self.the_name+' socket closed.')

    
    def get_data(self):
        if self.has_geta:
            r = self.send_message_array('geta', 26)
            rr = [i for i in r]
            if len(rr) > 12:
                rr[0] = int16_to_float05(rr[0])
                rr[1] = int16_to_float05(rr[1])
                rr[3] = make_unsigned(rr[3])
        else:
            r = self.send_message('get')
            rr = r.split(' ')
        if len(rr) > 12:
            try:
                if self.coef_ctrl != 0:
                    if self.control_I_or_V == 'I':
                        self.current = float(rr[0])/self.coef_ctrl
                        if self.coef_F_ctrl != 0:
                            self.F = float(rr[1])/self.coef_F_ctrl
                    else:
                        self.current = float(rr[1])/self.coef_ctrl
                        if self.coef_F_ctrl != 0:
                            self.F = float(rr[0])/self.coef_F_ctrl
                f = int(rr[2])
                self.stats_cnt = int(rr[3])
                self.CR = float(rr[4])*self.coef_I_read
                self.stats_minI = float(rr[5])*self.coef_I_read
                self.stats_maxI = float(rr[6])*self.coef_I_read
                self.stats_deltaI = round(float(rr[6])-float(rr[5]))
                self.VR = float(rr[7])*self.coef_V_read
                self.stats_minV = float(rr[8])*self.coef_V_read
                self.stats_maxV = float(rr[9])*self.coef_V_read
                self.stats_deltaV = round(float(rr[9])-float(rr[8]))
                if self.coef_F_read != 0:
                    self.FR = float(rr[10])*self.coef_F_read
                    self.stats_minF = float(rr[11])*self.coef_F_read
                    self.stats_maxF = float(rr[12])*self.coef_F_read
                    self.stats_deltaF = int(rr[12])-int(rr[11])
                    #self.slave.last_ret = [(self.FR, self.stats_minF, self.stats_maxF)] # type: ignore
                        
            except Exception as ex:
                print('Exception in commonPS.get_data:', r, rr, ex)
                f = -1
        else:
            f = -1
        #if len(rr) != 13:# and len(rr) != 15:
        #    print('commonPS.get_data message wrong size, not 13 but', len(rr), r)
        if f < 0:
            self.comfails_count += 1
            self.comfail = True
        if f >= 0  and  f & 128:
            self.restarted_count += 1
            self.send_message('ok')            
        if f >= 0:
            self.interlock_open = bool(f & 64) # interlock open
            self.HV_off = bool(f & 256)
            self.arc_start_flag = bool(f & 512)
            if bool(f & 1024): self.dac_fail = True
            self.comfail = False
        self.flags = f
        
        self.last_ctrl = [self.current] if self.coef_ctrl != 0 else []
        
        self.last_ret = []
        if self.coef_I_read != 0:
            if self.stats_minI > self.stats_maxI:
                print('FAIL I')
                self.stats_maxI = self.stats_minI
            self.last_ret.append((self.CR, self.stats_minI, self.stats_maxI))
        if self.coef_V_read != 0:
            if self.stats_minV > self.stats_maxV:
                print('FAIL V')
                self.stats_maxV = self.stats_minV
            self.last_ret.append((self.VR, self.stats_minV, self.stats_maxV))
        #print(self.last_ret)
        if not self.slave is None:
            if self.coef_F_read != 0:
                self.slave.last_ret = [(self.FR, self.stats_minF, self.stats_maxF)] 
            else:
                self.slave.last_ret = []
            self.slave.last_ctrl = [self.F] if self.coef_F_ctrl != 0 else []
        return rr
        
        
    def update_ui(self):
        if self.coef_ctrl != 0:
            common.change_text(self.chb_currentSet, 'Set '+self.descr_ctrl+' = {:.3f} '.format(self.current)+self.units_ctrl)
        if self.coef_F_ctrl != 0:
            common.change_text(self.chb_F_set, 'Set '+self.descr_F_ctrl+' = {:.3f} '.format(self.F)+self.units_F)
        if self.coef_I_read != 0:
            common.change_text(self.chb_currentRead, self.descr_I+' = {:.3f} '.format(self.CR)+self.units_I)
            txt = ''
            if self.canvas_show_stats:
                txt = '{:.3f} .. {:.3f},  Δ: {:g}'.format(self.stats_minI, self.stats_maxI, self.stats_deltaI)
            self.bar_I.update(self.stats_minI, self.stats_maxI, txt=txt)
        if self.coef_V_read != 0:
            common.change_text(self.chb_voltageRead, self.descr_V+' = {:.3f} '.format(self.VR)+self.units_V)
            txt = ''
            if self.canvas_show_stats:
                txt = '{:.3f} .. {:.3f},  Δ: {:g}'.format(self.stats_minV, self.stats_maxV, self.stats_deltaV)
            self.bar_V.update(self.stats_minV, self.stats_maxV, txt=txt)
        if self.coef_F_read != 0:            
            common.change_text(self.chb_F_read, self.descr_F+' = {:.3f} '.format(self.FR)+self.units_F)
            txt = ''
            if self.canvas_show_stats:
                txt = '{:.3f} .. {:.3f},  Δ: {:g}'.format(self.stats_minF, self.stats_maxF, self.stats_deltaF)
            self.bar_F.update(self.stats_minF, self.stats_maxF, txt=txt)

        
        ctrltxt = ''
        if self.interlock_open: ctrltxt += 'Interlock open! '
        if self.HV_off        : ctrltxt += 'HV off '
        if self.arc_start_flag: ctrltxt += 'ARC START! '
        if self.dac_fail      : ctrltxt += 'DAC FAIL!!!'
        if self.comfail       : ctrltxt  = 'No connection'
        bad = self.interlock_open or self.comfail or self.dac_fail
        self.bar_ctrl.update(self.current, txt=ctrltxt, bad=bad)

        if self.coef_F_ctrl != 0:
            self.bar_ctrlF.update(self.F, txt='No connection' if self.comfail else '', bad=bad)


        if self.fail_count != self.restarted_count + self.comfails_count:
            self.lbl_restarts.configure(text='rs: '+str(self.restarted_count))
            self.lbl_comfails.configure(text='cf: '+str(self.comfails_count))
            self.fail_count = self.restarted_count + self.comfails_count
        

    def on_currentReturn(self, _event):
        c = float(self.var_current.get())
        if c < 0:
            self.var_current_set(0)
            c = 0
        cmd = 'ramp' + self.control_I_or_V
        #print(cmd, '-->', c, c*self.coef_ctrl)
        res=self.send_message(cmd+' '+str(c*self.coef_ctrl))
        if res != 'ok':
            print(res)
            try:
                self.current = float(self.send_message('getSet'+self.control_I_or_V)) / self.coef_ctrl
            except:
                print('failed to getSet...')
        if not self.on_change_ctrl_proc is None:
            self.on_change_ctrl_proc(self.the_name, c)
        self.update_ui()


    def on_F_return(self, _event):
        IorV = 'I' if self.control_I_or_V=='V' else 'V'
        c = float(self.var_F.get())
        if c < 0:
            self.var_F_set(0)
            c = 0
        cmd = 'ramp' + IorV
        #print(cmd, '-->', c, c*self.coef_ctrl)
        res=self.send_message(cmd+' '+str(c*self.coef_F_ctrl))
        if res != 'ok':
            print(res)
            try:
                self.F = float(self.send_message('getSet'+IorV)) / self.coef_F_ctrl
            except:
                print('failed to getSetF...')
        if not self.on_change_ctrl_proc is None:
            self.on_change_ctrl_proc(self.slave.the_name, c)
        self.update_ui()



def int16_to_float05(i):
    ui = i if i >= 0 else i + 65536
    return ui/13107.0  # 0xffff/5

def make_unsigned(res): # int16 -> uint16
    return res if res >= 0 else res + 65536


'''if __name__ == '__main__':
    root = tki.Tk()
    root.title('test')
    root.geometry('350x350')
    abox = tki.LabelFrame(master=root, text='test')
    #ps = CommonPS(abox, '1.2.3.4', 17, 'Magnet', 'V', [('0.7', 0.7), ('24',24)])
    ps = CommonPS(abox, '192.168.2.7', 6, 'Neutral trap'    , 'V' , [('1kV',  1)    ], 5.0/ 3   , 0.000044868*5  , 0.00004533* 3 , (0, 2,   5*0+0.115*2)    , (0   ,    2,   3*0+1.1*2), 'mA'   , 'kV'   , 0.005) # 5mA, 3kV
    abox.place(x=0, y= 0, width=350)
    ps.get_data()
    ps.update_ui()
    def tst():
        ps.get_data()
        ps.update_ui()
    tt = tki.Button(root, text='update', command=tst)
    tt.place(x=5, y=300)
    root.mainloop()'''


