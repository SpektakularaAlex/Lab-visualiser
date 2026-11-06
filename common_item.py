import tkinter as tki
#import time
import threading
import tooltip

import common


class CommonItem():
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
        self.units_ctrl = units_ctrl
        self.units_I = units_I
        self.units_V = units_V
        self.d_ctrl = d_ctrl
        
        self.chb_currentSet = tki.Label(master=box, text='Set '+control_I_or_V+':')
        self.chb_currentSet.place(x=0, y=3)
        common.set_text(self.chb_currentSet)
        
        if coef_I_read != 0:
            self.chb_currentRead = tki.Checkbutton(master=box, text='I = -1 A')
            self.chb_currentRead.place(x=2, y=28)
            common.set_text(self.chb_currentRead)
        
        if coef_V_read != 0:
            self.chb_voltageRead = tki.Checkbutton(master=box, text='U = -1 V')
            self.chb_voltageRead.place(x=2, y=28+hei_i)
            common.set_text(self.chb_voltageRead)

        self.the_canvas = tki.Canvas(master=box, width=166, height=43+hei_i+hei_v)
        self.the_canvas.place(x=120, y=-16)
        self.the_canvas.bind('<Button-1>', self.on_click_canvas)
        self.bar_ctrl = common.ABar(self.the_canvas, y= 2, minmax=self.minmax_ctrl, twobars=False)
        if coef_I_read != 0:
            self.bar_I    = common.ABar(self.the_canvas, y=48      , minmax=self.minmax_I   , twobars=True)
        if coef_V_read!=0:
            self.bar_V    = common.ABar(self.the_canvas, y=48+hei_i, minmax=self.minmax_V   , twobars=True)
        self.canvas_show_stats = False
        
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
        self.comfail = False
        self.dac_fail = False
        
        self.the_lock = threading.Lock()
        self.the_socket, self.sockok = common.connect_socket(term_serv_addr, port, aname)
        
        self.on_change_ctrl_proc = None
        
        self.the_probes =[]
        self.the_checkbuttons = []
        if coef_I_read != 0:
            self.the_checkbuttons.append(self.chb_currentRead)
        if coef_V_read != 0:
            self.the_checkbuttons.append(self.chb_voltageRead)
        
        
    def var_current_set(self, v):
        if v >= 10.0:
            self.var_current.set('{:.2f}'.format(v))
        else:
            self.var_current.set('{:.3f}'.format(v))
        
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

    def clear_fails(self, _ev):
        self.restarted_count = 0
        self.comfails_count = 0
        self.dac_fail = False
        
    def on_click_canvas(self, _ev):
        self.canvas_show_stats = not self.canvas_show_stats
        self.update_ui()

        
    def send_message(self, msg):
        ret = common.send_socket_message(self.the_socket, msg, self.the_lock)
        self.sockok = ret != 'timeout'
        return ret

    def switchOff(self):
        self.var_current_set(0)
        self.on_currentReturn(None)
        
        
    def set_I(self, v):
        self.var_current_set(v)
        self.on_currentReturn(None)
    
    def set_dI(self, dI):
        c = float(self.var_current.get())
        self.var_current_set(c + dI*self.d_ctrl)
        self.on_currentReturn(None)


    def on_destroy(self):
        self.the_socket.close()
        print(self.the_name+' socket closed.')

    
    def get_data(self):
        self.last_ret = []
        if self.coef_I_read != 0:
            self.last_ret.append(self.CR)
        if self.coef_V_read != 0:
            self.last_ret.append(self.VR)
        #print(self.last_ret)
        
        
    def update_ui(self):
        common.change_text(self.chb_currentSet, 'Set '+self.control_I_or_V+' = {:.3f} '.format(self.current)+self.units_ctrl)

        if self.coef_I_read != 0:
            common.change_text(self.chb_currentRead, 'I = {:.3f} '.format(self.CR)+self.units_I)
            txt = ''
            if self.canvas_show_stats:
                txt = '{:.3f} .. {:.3f},  Δ: {:g}'.format(self.stats_minI, self.stats_maxI, self.stats_deltaI)
            self.bar_I.update(self.stats_minI, self.stats_maxI, txt=txt)
        if self.coef_V_read != 0:
            common.change_text(self.chb_voltageRead, 'U = {:.3f} '.format(self.VR)+self.units_V)
            txt = ''
            if self.canvas_show_stats:
                txt = '{:.3f} .. {:.3f},  Δ: {:g}'.format(self.stats_minV, self.stats_maxV, self.stats_deltaV)
            self.bar_V.update(self.stats_minV, self.stats_maxV, txt=txt)
        
        ctrltxt = ''
        if self.dac_fail      : ctrltxt += 'DAC FAIL!!!'
        if self.comfail       : ctrltxt  = 'No connection'
        self.bar_ctrl.update(self.current, txt=ctrltxt, bad=self.comfail or self.dac_fail)
        
        if self.fail_count != self.restarted_count + self.comfails_count:
            self.lbl_restarts.configure(text='rs: '+str(self.restarted_count))
            self.lbl_comfails.configure(text='cf: '+str(self.comfails_count))
            self.fail_count = self.restarted_count + self.comfails_count
        

    def on_currentReturn(self, _event):
        c = float(self.var_current.get())
        if c < 0:
            self.var_current_set(0)
            c = 0
            self.update_ui()
        if not self.on_change_ctrl_proc is None:
            self.on_change_ctrl_proc(self.the_name, c)


