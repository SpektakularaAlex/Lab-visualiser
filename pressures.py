import tkinter as tki
import common
import time

class Pressures():
    def __init__(self, box, _term_serv_addr, _port, _aname='pressures'):
        box.place(height=106)
        #self.the_name = aname
        self.chb_S1 = tki.Checkbutton(master=box, text='S1??')
        self.chb_S1.place(x=2, y=0)
        self.chb_S2 = tki.Checkbutton(master=box, text='S2??')
        self.chb_S2.place(x=2, y=20)
        self.chb_FC_LE1 = tki.Checkbutton(master=box, text='FCLE1??')
        self.chb_FC_LE1.place(x=2, y=40)
        self.chb_FC_HE2 = tki.Checkbutton(master=box, text='FCHE2??')
        self.chb_FC_HE2.place(x=2, y=60)
        self.the_checkbuttons = [self.chb_S1, self.chb_S2, self.chb_FC_LE1, self.chb_FC_HE2]
        self.p = [-1.0, -1.0, -1.0, -1.0]
        
        self.lbl_limit = tki.Label(master=box, text='Limit:')
        self.lbl_limit.place(x=230, y=1)
        self.var_limit = tki.StringVar()
        self.var_limit.set('3e-6')
        self.txt_limit = tki.Entry(master=box, textvariable=self.var_limit)
        self.txt_limit.place(x=230, y=20, width=60)
        self.default_color = self.lbl_limit.cget('bg')
        lbl = tki.Label(master=box, text='mbar')
        lbl.place(x=290, y=21)


    def on_destroy(self):
        pass


    def get_data(self):
        #self.p = common.getDBValue('CCG S1-1|PR\nCCG S2-1|PR\n')
        self.p = common.getDBValue('CCG S1-1|PR\nCCG S2-1|PR\nFC  LE-1|CR\nFC  HE-2|CR\n')
        common.g_pressure_S2 = self.p[1]
        self.last_ret = [self.p[0]*1e6, self.p[1]*1e6,self.p[2]*1e9,self.p[3]*1e9] #[v*1e6 for v in self.p]


    def update_ui(self):
        self.chb_S1.configure(text='S1 = {:.4g} mbar'.format(self.p[0]))
        self.chb_S2.configure(text='S2 = {:.4g} mbar'.format(self.p[1]))
        self.chb_FC_LE1.configure(text='FCLE1 = {:.4g} nA'.format(self.p[2]*1e9))
        self.chb_FC_HE2.configure(text='FCHE2 = {:.4g} nA'.format(self.p[3]*1e9))

        limit = -1.0
        try:
            limit = float(self.var_limit.get())
        except:
            print('BAD PRESSURE LIMIT STRING!')
        if self.p[1] > limit: common.g_pressure_regulate = -1
        if self.p[1] < limit-0.1e-6: common.g_pressure_regulate = 1
        '''if common.g_pressure_too_high:
            print('Pressure is too high...')
        if common.g_pressure_too_low:
            print('Pressure is too low...')'''


        if common.g_pressure_regulate!=0:
            self.lbl_limit.configure(bg='orange')
        else:
            self.lbl_limit.configure(bg=self.default_color)


# DO NOT  USE
class Pressures2():
    def __init__(self, box, _term_serv_addr, _port, _aname='pressures'):
        box.place(height=66)
        #self.the_name = aname
        self.chb_S1 = tki.Checkbutton(master=box, text='S1??')
        self.chb_S1.place(x=2, y=0)
        self.chb_S2 = tki.Checkbutton(master=box, text='S2??')
        self.chb_S2.place(x=2, y=20)
        self.the_checkbuttons = [self.chb_S1, self.chb_S2]
        self.p = [-1.0, -1.0]
        
        self.lbl_limit = tki.Label(master=box, text='Limit:')
        self.lbl_limit.place(x=230, y=1)
        self.var_limit = tki.StringVar()
        self.var_limit.set('3e-6')
        self.txt_limit = tki.Entry(master=box, textvariable=self.var_limit)
        self.txt_limit.place(x=230, y=20, width=60)
        self.default_color = self.lbl_limit.cget('bg')
        lbl = tki.Label(master=box, text='mbar')
        lbl.place(x=290, y=21)


    def on_destroy(self):
        pass


    def get_data(self):
        #self.p = common.getDBValue('CCG S1-1|PR\nCCG S2-1|PR\n')
        self.p = common.getDBValue('CCG S1-1|PR\nCCG S2-1|PR\n')
        common.g_pressure_S2 = self.p[1]
        self.last_ret = [self.p[0]*1e6, self.p[1]*1e6] #[v*1e6 for v in self.p]


    def update_ui(self):
        self.chb_S1.configure(text='S1 = {:.4g} mbar'.format(self.p[0]))
        self.chb_S2.configure(text='S2 = {:.4g} mbar'.format(self.p[1]))

        limit = -1.0
        try:
            limit = float(self.var_limit.get())
        except:
            print('BAD PRESSURE LIMIT STRING!')
        if self.p[1] > limit: common.g_pressure_regulate = -1
        if self.p[1] < limit-0.1e-6: common.g_pressure_regulate = 1
        '''if common.g_pressure_too_high:
            print('Pressure is too high...')
        if common.g_pressure_too_low:
            print('Pressure is too low...')'''


        if common.g_pressure_regulate != 0:
            self.lbl_limit.configure(bg='orange')
        else:
            self.lbl_limit.configure(bg=self.default_color)


class Pressure1():
    def __init__(self, box, _box, _term_serv_addr, _port, aname=('pressure',''), pressure_id='S1'):
        box.place(height=46+22)
        #self.the_name = aname
        self.short_name = pressure_id
        self.pressure_id = 'CCG '+ pressure_id + '-1|PR'
        self.chb_S1 = tki.Checkbutton(master=box, text=pressure_id)
        common.set_text(self.chb_S1)
        self.chb_S1.place(x=2, y=0)
        self.the_checkbuttons = [self.chb_S1]
        self.p = [-1.0]
        
        self.the_canvas = tki.Canvas(master=box, width=166, height=18)
        self.the_canvas.place(x=120, y=-15)
        self.bar_P = common.ABar(self.the_canvas, y=2, minmax=(2.5, 3.1, 5), twobars=False, name=aname[0]+'')
        
        # scale marks on pressure: 
        self.bar_P.add_marks([2.5, 3], [2.6, 2.7, 2.8, 2.9, 3.1])


        self.target_min_max = (2.95, 3.05)
        y_pos = 22
        self.var_regulate = tki.IntVar()
        self.var_regulate.set(0)
        chb = tki.Checkbutton(master=box, variable=self.var_regulate, text='Regulate:', command=self.on_click_regulate)
        chb.place(x=37, y=y_pos)
        
        self.var_min = tki.StringVar()
        self.var_min.set(str(self.target_min_max[0]))
        self.var_min.trace_add('write', self.on_click_regulate)
        self.txt_min = tki.Entry(master=box, textvariable=self.var_min)
        self.txt_min.place(x=124, y=y_pos, width=35)
        
        self.var_max = tki.StringVar()
        self.var_max.set(str(self.target_min_max[1]))
        self.var_max.trace_add('write', self.on_click_regulate)
        self.txt_max = tki.Entry(master=box, textvariable=self.var_max)
        self.txt_max.place(x=124+35+11, y=y_pos, width=35)
        
        tki.Label(box, text='-').place(x=124+35+2, y=y_pos)
        tki.Label(box, text='e-6 mbar').place(x=124+2*35+11+2, y=y_pos)

        self.regulate = False
        self.last_regulation_time = time.time()
        self.last_names = ['pressure', pressure_id]
        self.last_ctrl = []


    def on_click_regulate(self, _v=None, _b=None, _c=None):
        self.regulate = bool(self.var_regulate.get())
        if not self.regulate:
            common.g_pressure_regulate = 0
        mi, ma = self.target_min_max
        #if v == self.var_min():
        try:
            mi = float(self.var_min.get())
            self.txt_min.configure(bg='white')
        except:
            self.txt_min.configure(bg='pink')
        #if v == self.var_max():
        try:
            ma = float(self.var_max.get())
            self.txt_max.configure(bg='white')
        except:
            self.txt_max.configure(bg='pink')
        if mi < ma:
            self.target_min_max = (mi, ma)
        else:
            self.target_min_max = (ma, mi)
        print(self.target_min_max)
    
    
        
    def on_destroy(self):
        pass

    def get_data(self):
        self.p = common.getDBValue(self.pressure_id)
        common.g_pressure_S2 = self.p[0]
        p = self.p[0]*1e6
        self.last_ret = [p]

        if self.regulate and time.time()-self.last_regulation_time>40:
            self.last_regulation_time = time.time()
            if p < self.target_min_max[0]: common.g_pressure_regulate = 1 #'up'
            if p > self.target_min_max[1]: common.g_pressure_regulate = -1 # 'down'

    def update_ui(self):
        common.change_text(self.chb_S1, self.short_name+' = {:.4g} mbar'.format(self.p[0]))
        self.bar_P.update(self.p[0]*1e6)

