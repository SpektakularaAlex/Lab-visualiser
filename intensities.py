import tkinter as tki
import common
import time

FC_STRINGS = ['UNDEFINED', 'FC LE', 'FC HE-1', 'FC HE-2', 'BPM']

class Intensities():
    def __init__(self, box, _box, _term_serv_addr, _port, aname=('intensities','')):
        box.place(height=46+22)
        
        self.chb_int = tki.Checkbutton(master=box, text='I')
        common.set_text(self.chb_int)
        self.chb_int.place(x=2, y=0)
        
        self.chb_fc_ind = tki.Checkbutton(master=box, text='FC ind')
        common.set_text(self.chb_fc_ind)
        self.chb_fc_ind.place(x=2, y=24)
        
        self.the_checkbuttons = [self.chb_int, self.chb_fc_ind]
        
        self.the_canvas = tki.Canvas(master=box, width=166, height=18)
        self.the_canvas.place(x=120, y=-15)
        self.bar_P = common.ABar(self.the_canvas, y=2, minmax=(0, 1000, 1000), twobars=True, name=aname[0]+'')
        
        self.last_names = ['intensities', 'intensity', 'fc_index']
        self.last_ctrl = []
        self.fc_v = 0.0
        self.fc_mi= 0.0
        self.fc_ma= 0.0


        
    def on_destroy(self):
        pass

    def get_data(self):
        v = common.the_app.main_selected_fc_value
        if v[3] > 0:
            self.fc_v = v[0]/v[3]
            self.fc_mi = v[1]
            self.fc_ma = v[2]
            v[:] = 0.0, 1e99, -1e99, 0
        self.last_ret = [(self.fc_v, self.fc_mi, self.fc_ma), common.the_app.main_selected_fc_index]


    def update_ui(self):
        common.change_text(self.chb_int, 'I = {:.1f} nA'.format(self.fc_v))
        common.change_text(self.chb_fc_ind, 'FC ind = {:d}: '.format(common.the_app.main_selected_fc_index)+FC_STRINGS[common.the_app.main_selected_fc_index+1])
        self.bar_P.update(self.fc_mi, self.fc_ma)
