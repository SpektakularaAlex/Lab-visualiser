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
                d_ctrl = 0.01): 
        boxheight = 92 if coef_V_read!=0 else 74
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
        self.units_ctrl = units_ctrl
        self.units_I = units_I
        self.units_V = units_V
        self.d_ctrl = d_ctrl
        
        self.chb_currentSet = tki.Label(master=box, text='Set '+control_I_or_V+':')
        self.chb_currentSet.place(x=0, y=3)
        self.chb_currentRead = tki.Checkbutton(master=box, text='I = -1 A')
        self.chb_currentRead.place(x=2, y=28)
        #self.lbl_currentExtra = tki.Label(master=box, text='(...)')
        #self.lbl_currentExtra.place(x=120, y=30)
        if coef_V_read != 0:
            self.chb_voltageRead = tki.Checkbutton(master=box, text='U = -1 V')
            self.chb_voltageRead.place(x=2, y=47)
        #self.lbl_voltageExtra = tki.Label(master=box, text='(...)')
        #self.lbl_voltageExtra.place(x=120, y=46)

        self.the_canvas = tki.Canvas(master=box, width=166, height=81 if coef_V_read!=0 else 66)
        self.the_canvas.place(x=120, y=-16)
        self.the_canvas.bind('<Button-1>', self.on_click_canvas)
        self.bar_ctrl = common.ABar(self.the_canvas, y= 2, minmax=self.minmax_ctrl, twobars=False)
        self.bar_I    = common.ABar(self.the_canvas, y=48, minmax=self.minmax_I   , twobars=True)
        if coef_V_read!=0:
            self.bar_V    = common.ABar(self.the_canvas, y=67, minmax=self.minmax_V   , twobars=True)
        '''self.rect_ctrl = r = (2, 2, 166, 14)
        self.the_canvas.create_rectangle(r[0]-1, r[1]-1, r[2], r[3], fill='', outline='black')                   # outline: (1,1,width,h) to fill canvas and be visible
        self.bar_ctrl = self.the_canvas.create_rectangle(*r, fill='#44cc44', outline='') # fill: (2,2,width,h) to fill the outline without covering it
        self.bartxt_ctrl = self.the_canvas.create_text(r[0]+1, r[1]-1, text='NOT CONNECTED', anchor='nw')
        self.rect_I = r = (2, 48, 166, 49+13)
        self.the_canvas.create_rectangle(r[0]-1, r[1]-1, r[2], r[3], fill='', outline='black')                   # outline: (1,1,width,h) to fill canvas and be visible
        self.bar_I_ma = self.the_canvas.create_rectangle(*r, fill='#ff00ff', outline='') # fill: (2,2,width,h) to fill the outline without covering it
        self.bar_I_mi = self.the_canvas.create_rectangle(*r, fill='#44cc44', outline='') # fill: (2,2,width,h) to fill the outline without covering it
        self.bartxt_I = self.the_canvas.create_text(r[0]+1, r[1]-1, text='0.007', anchor='nw')
        if coef_V_read!=0:
            self.rect_V = r = (2, 67, 166, 68+13)
            self.the_canvas.create_rectangle(r[0]-1, r[1]-1, r[2], r[3], fill='', outline='black')                   # outline: (1,1,width,h) to fill canvas and be visible
            self.bar_V_ma = self.the_canvas.create_rectangle(*r, fill='#ff00ff', outline='') # fill: (2,2,width,h) to fill the outline without covering it
            self.bar_V_mi = self.the_canvas.create_rectangle(*r, fill='#44cc44', outline='') # fill: (2,2,width,h) to fill the outline without covering it
            self.bartxt_V = self.the_canvas.create_text(r[0]+1, r[1]-1, text='0.007', anchor='nw')
        self.bar_ctrl_clr = '#44cc44'
        self.bar_I_clr = '#44cc44'
        self.bar_V_clr = '#44cc44'
        self.canvas_show_stats_prev = True'''
        self.canvas_show_stats = False
        
        self.var_current = tki.StringVar()
        self.var_current.set('0.000')
        self.txt_current = tki.Entry(master=box, textvariable=self.var_current)
        self.txt_current.place(x=122, y=2, width=50)
        self.txt_current.bind('<Return>', self.on_currentReturn)
        self.txt_current.bind('<KP_Enter>', self.on_currentReturn)
        #self.txt_current.bind('<MouseWheel>', lambda ev: self.set_dI(0.01 if ev.delta>0 else -0.01))
        # on linux bind('<MouseWheel>') does not work...
        self.txt_current.bind('<Button-4>', lambda _ev: self.set_dI( 1))
        self.txt_current.bind('<Button-5>', lambda _ev: self.set_dI(-1))

        '''(a, b, c, d) = self.rect_ctrl
        self.the_canvas.coords(self.bar_ctrl, a, b, c*0.7, d)
        self.the_canvas.itemconfigure(self.bar_ctrl, fill='#ff8888')
        (a, b, c, d) = self.rect_VR
        self.the_canvas.coords(self.bar_VR_ma, a, b, c*1, d)
        self.the_canvas.coords(self.bar_VR_mi, a, b, c*0.7, d)
        #self.the_canvas.itemconfigure(self.bar_VR_mi, fill='#ff8888')'''
        
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
        self.lbl_restarts.place(x=290, y=30)
        self.lbl_restarts.bind("<ButtonRelease-3>", self.clear_fails)
        self.lbl_comfails = tki.Label(master=box, text='cf: 0', font=('', 8))
        self.lbl_comfails.place(x=290, y=42)
        self.lbl_comfails.bind("<ButtonRelease-3>", self.clear_fails)

        #btn = tki.Button(master=box, text='0.7', command=self.set_to_07)
        #btn.place(x=200, y=1)
        if presets is None:
            presets = []
        for i in range(len(presets)):
            btn = tki.Button(master=box, text=presets[i][0], command=lambda v=presets[i][1]: self.set_I(v))
            btn.place(x=214+i*32, y=1, width=31 if len(presets)>1 else 41, height=28)
            tooltip.ToolTip(btn, presets[i][1])

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
        
        self.the_lock = threading.Lock()
        self.the_socket, self.sockok = common.connect_socket(term_serv_addr, port, aname)
        
        self.AI_rate = 5 # 0 to 7; noise level and max-min are ca 2x lower for rate=R vs rate=R+2
        AI_samples_per_s = [4, 7, 15, 30, 58, 107, 181, 292]
        self.AI_timestep_ms = 1000.0/AI_samples_per_s[self.AI_rate]
        
        self.on_change_ctrl_proc = None
        
        if self.sockok:
            self.send_message('setRate '+str(self.AI_rate))
            try:
                self.current = float(self.send_message('getSet'+control_I_or_V)) / coef_ctrl
                self.var_current.set('{:.3f}'.format(self.current))
                #print('version:')
                print(aname, self.send_message('version'))
            except:
                print('Exception in ', aname, 'current and version get')
                self.sockok = False
        else:
            print(aname, 'socket is not ok')

        self.the_probes =[(self.get_probe_I, 'I')]
        self.the_checkbuttons = [self.chb_currentRead]
        if coef_V_read != 0:
            self.the_probes.append((self.get_probe_V, 'V'))
            self.the_checkbuttons.append(self.chb_voltageRead)
        
        
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
        
    def clear_fails(self, _ev):
        self.restarted_count = 0
        self.comfails_count = 0
        
    def on_click_canvas(self, _ev):
        self.canvas_show_stats = not self.canvas_show_stats
        self.update_ui()

        
    def send_message(self, msg):
        ret = common.send_socket_message(self.the_socket, msg, self.the_lock)
        self.sockok = ret != 'timeout'
        return ret
    
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
        
        
    def switchOff(self):
        self.var_current.set('0.000')
        self.on_currentReturn(None)
        
        
    def set_I(self, v):
        self.var_current.set('{:.3f}'.format(v))
        self.on_currentReturn(None)
    
    def set_dI(self, dI):
        c = float(self.var_current.get())
        self.var_current.set('{:.3f}'.format(c + dI*self.d_ctrl))
        self.on_currentReturn(None)


    def on_destroy(self):
        self.the_socket.close()
        print(self.the_name+' socket closed.')

    
    def get_data(self):
        r = self.send_message('get')
        rr = r.split(' ')
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
                self.stats_deltaI = round(float(rr[6])-float(rr[5]))
                self.VR = float(rr[7])*self.coef_V_read
                self.stats_minV = float(rr[8])*self.coef_V_read
                self.stats_maxV = float(rr[9])*self.coef_V_read
                self.stats_deltaV = round(float(rr[9])-float(rr[8]))
            except Exception as ex:
                print(r, rr, ex)
                f = -1
        else:
            f = -1
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
            self.comfail = False
        
        self.last_ret = [(self.CR, self.stats_minI, self.stats_maxI)]
        if self.coef_V_read != 0:
            self.last_ret.append((self.VR, self.stats_minV, self.stats_maxV))
        return rr
        
        
    def update_ui(self):
        self.chb_currentSet.configure(text='Set '+self.control_I_or_V+' = {:.3f} '.format(self.current)+self.units_ctrl)
        self.chb_currentRead.configure(text='I = {:.3f} '.format(self.CR)+self.units_I)
        if self.coef_V_read != 0:
            self.chb_voltageRead.configure(text='U = {:.3f} '.format(self.VR)+self.units_V)
        #self.lbl_flags.configure(text=self.FR)
        
        txt = ''
        if self.canvas_show_stats:
            txt = '{:.3f} .. {:.3f},  Δ: {:g}'.format(self.stats_minI, self.stats_maxI, self.stats_deltaI)
        self.bar_I.update(self.stats_minI, self.stats_maxI, txt=txt)

        if self.coef_V_read!=0:
            txt = ''
            if self.canvas_show_stats:
                txt = '{:.3f} .. {:.3f},  Δ: {:g}'.format(self.stats_minV, self.stats_maxV, self.stats_deltaV)
            self.bar_V.update(self.stats_minV, self.stats_maxV, txt=txt)
        
        ctrltxt = ''
        if self.interlock_open: ctrltxt += 'Interlock open! '
        if self.HV_off        : ctrltxt += 'HV off '
        if self.arc_start_flag: ctrltxt += 'ARC START! '
        if self.comfail       : ctrltxt  = 'No connection'
        self.bar_ctrl.update(self.current, txt=ctrltxt)
        
        if self.fail_count != self.restarted_count + self.comfails_count:
            self.lbl_restarts.configure(text='rs: '+str(self.restarted_count))
            self.lbl_comfails.configure(text='cf: '+str(self.comfails_count))
            self.fail_count = self.restarted_count + self.comfails_count
        

    def on_currentReturn(self, _event):
        c = float(self.var_current.get())
        if c < 0:
            self.var_current.set('0.000')
            c = 0
        cmd = 'ramp' + self.control_I_or_V
        print(cmd, '-->', c, c*self.coef_ctrl)
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



if __name__ == '__main__':
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
    root.mainloop()


