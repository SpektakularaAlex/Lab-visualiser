import tkinter as tki
from tkinter.ttk import Frame, Combobox
import mychart_pil as mychart
import time
import threading
import socket
import os
import struct
import tkinter.messagebox

try:
    import duo_sqlite_logger
except Exception as ex:
    duo_sqlite_logger = None
    print("SQLite logger import failed:", ex)

import common
import koven
import socket_server
'''import filament
import valve
import pressures
import commonPS'''


UPDATE_PERIOD_MS = 1000
MAX_PTS_PER_GRAPH = 3600*16
S_PER_TIMEUNIT = 60


class S1S2(Frame):
    def __init__(self, the_items, S1_or_S2, fancy_pos=False, pic=''):
        super().__init__()

        self.master.title(S1_or_S2+' control')  # type: ignore

        common.the_app = self                  # type: ignore # yes my new favorite comment

        if pic != '' and fancy_pos:
            self.pic = tki.PhotoImage(file=pic)
            lbl = tki.Label(self.master, image=self.pic)
            lbl.place(x=0, y=0)

        # -MAX_PTS_PER_GRAPH+i for i in range(MAX_PTS_PER_GRAPH)
        self.data_x = []
        self.data_y: list[list[float]] = []
        self.data_bands: list[tuple[list[float], list[float]]] = []
        self.data_probe_x = []
        self.data_probe_y = []

        self.menu_probe_var = tki.StringVar(value='0')
        self.menu_probe = tki.Menu(self.master, tearoff=0)
        self.menu_probe.add_radiobutton(
            label='[none]', value='0', variable=self.menu_probe_var, command=lambda: self.on_menu_probe('[none]'))

        self.btn_probe = tki.Button(text='[none]')
        self.btn_probe.bind("<ButtonRelease-1>", self.on_btn_probe)
        self.btn_probe.place(x=350, y=0, height=18)

        self.btn_clear_graphs = tki.Button(
            text='Clear graphs', command=self.clear_graphs)
        self.btn_clear_graphs.place(x=450, y=0, height=18)

        self.btn_save_data = tki.Button(
            text='Save data', command=self.save_data)
        self.btn_save_data.place(x=550, y=0, height=18)

        self.btn_presets = tki.Button(text='Presets...')
        self.btn_presets.bind("<ButtonRelease-1>", self.on_btn_presets)
        self.btn_presets.place(x=650, y=0, height=18)

        # operator note widgets; placed later in place_boxes()
        try:
            self.init_note_widgets()
        except Exception as ex:
            print('Operator note widgets failed:', ex)

        self.default_color = self.master.cget('bg')
        self.default_color_a = self.master.cget('bg')

        self.S1_or_S2 = S1_or_S2
        self.fancy_pos = fancy_pos

        # === saved zoom === :
        try:
            f = open('saved_zoom_'+S1_or_S2+'.txt', 'r', encoding='utf-8')
            t = f.read()
            f.close()
            saved_zoom = []
            for line in t.split('\n'):
                vv = line.split('\t')
                if len(vv) >= 3:
                    saved_zoom.append(vv)
        except:
            saved_zoom = []
        self.saved_zoom = []

        # === saved minmax === :
        try:
            f = open('saved_minmax_'+S1_or_S2+'.txt', 'r', encoding='utf-8')
            t = f.read()
            f.close()
            saved_minmax = []
            for line in t.split('\n'):
                vv = line.split('\t')
                if len(vv) == 4:
                    saved_minmax.append(vv)
        except:
            saved_minmax = []
        self.the_bars: list[common.ABar] = []

        # ==== Graphs =======
        self.chart = mychart.Chart(self.master, 450, 560, 'Time /min',
                                   legend_style='selected',
                                   on_select_line_proc=self.on_select_line_proc,
                                   on_save_zoom_proc=self.on_save_zoom_proc)
        #self.chart.draw([212e-4, 222e-4, 232e-4, 242e-4, 252e-4], [[2, 4, 6, 8, 16], [1, 3, 5, 7, 9]])
        self.chart2 = mychart.Chart(self.master, 350, 280, 'Time /min')
        self.chart_probe = mychart.Chart(self.master, 450, 280, 'Time /ms')

        self.the_items = []
        self.the_checkbuttons = []
        self.the_probes = []
        probe_ind = 0

        for it in the_items:
            names = it[3][0].split('/')
            box = tki.LabelFrame(master=self.master, text=names[0])
            if len(names) == 1:
                anitem: common.Anitem = it[0](box, None, *it[1:-1])
                anitem.slave = None
                self.the_items.append(anitem)
            else:
                box2 = tki.LabelFrame(master=self.master, text=names[1])
                anitem = it[0](box, box2, *it[1:-1])

                # type: ignore #(magic comment to suppress warning)
                anitem2: common.Anitem = anitem.slave
                anitem2.the_box = box2
                anitem2.the_name = names[1]
                anitem2.is_master = False
                anitem2.fancy_pos = [] if len(it[-1]) < 4 else it[-1][2:4]
                self.the_items.append(anitem)
                self.the_items.append(anitem2)
                if len(names) > 2 and names[2] == 'invert':
                    # same as anitem.next_pos = True, but to satisfy the Assistant.
                    setattr(anitem, 'next_pos', True)
                    # anitem2.prev_pos = True
                    setattr(anitem2, 'prev_pos', True)
                if len(names) > 2 and names[2] == 'hide':
                    # anitem2.hide_pos = True
                    setattr(anitem2, 'hide_pos', True)
            anitem.fancy_pos = it[-1]
            anitem.the_box = box
            anitem.the_name = names[0]
            anitem.is_master = True
        ind = 0
        for anitem in self.the_items:
            anitem.chb_enabled = tki.Checkbutton(master=self.master, text=anitem.the_name, command=lambda a=anitem: self.on_enable(
                a), font=('', 10, 'bold'))  # type: ignore
            anitem.chb_enabled.place(x=-10, y=-18)
            set_checked(anitem.chb_enabled, True)
            anitem.enabled = True
            anitem.on_change_ctrl_proc = self.on_change_ctrl_proc
            if hasattr(anitem, 'the_checkbuttons'):
                for chb in anitem.the_checkbuttons:
                    # ([56.3 for i in range(MAX_PTS_PER_GRAPH)])
                    self.data_y.append([])
                    # ([2.01 for i in range(MAX_PTS_PER_GRAPH)], [99.1 for i in range(MAX_PTS_PER_GRAPH)])
                    self.data_bands.append(([], []))
                    self.the_checkbuttons.append(chb)
                    #chb.bind("<ButtonRelease-1>", lambda e, c=chb, ci=ind: self.on_chb(e, c, 1, ci))
                    #chb.bind("<ButtonRelease-3>", lambda e, c=chb, ci=ind: self.on_chb(e, c, 3, ci))
                    chb.bind("<Button-1>", lambda e, c=chb,
                             ci=ind: self.on_chb(e, c, 1, ci))
                    chb.axis = '1L'
                    chb.item = anitem
                    c = self.chart.colors[ind % len(self.chart.colors)]
                    chb.configure(fg=c, activeforeground=c)
                    self.default_color_a = chb.cget('activebackground')
                    chbn = (chb.master.cget('text') + ' ' +
                            chb.cget('text')).split('=')[0].strip()
                    mima = (0.0, 100.0)
                    print(chbn)
                    for alist in saved_zoom:
                        if chbn.startswith(alist[0]):
                            mima = (float(alist[1]), float(alist[2]))
                            if len(alist) > 3 and alist[3] == '1':
                                set_checked(chb, True)
                            print('    ', alist)
                            break
                    # mima = (0.0, 100.0) #  !!!!!! just testing
                    self.saved_zoom.append(mima)
                    ind += 1
            if hasattr(anitem, 'the_probes'):
                for pr in anitem.the_probes:
                    self.the_probes.append(pr[0])
                    probe_ind += 1
                    ss = anitem.the_name+' '+pr[1]
                    self.menu_probe.add_radiobutton(label=ss, value=str(
                        probe_ind), variable=self.menu_probe_var, command=lambda a=ss: self.on_menu_probe(a))  # type: ignore

        for bar in self.the_bars:
            for alist in saved_minmax:
                if bar.bar_name == alist[0]:
                    bar.minmax = (float(alist[1]), float(
                        alist[2]), float(alist[3]))
                    bar.update_marks()
                    break

        self.master.bind('<Destroy>', self.on_destroy)
        self.master.bind('<Configure>', self.on_resize)

        self.master.after_idle(self.place_boxes)

        self.menuvar = tki.StringVar(value='1L')

        self.main_selected_fc_value = [0.0, 1e99, -1e99, 0]
        self.main_selected_fc_index = -1

        self.last_time = 0.0

        # self.the_thread = None #threading.Thread(target=self.the_thread_function)
        self.stop_event = threading.Event()
        self.stop_event.clear()
        self.clear_graphs_flag = False
        self.save_data_flag = False
        # self.the_thread.start()

        #self.nnn = False

        self.updateui_timer_id = None
        self.thread_timer_id = None
        #self.updateui_fast_timer_id = None
        #self.thread_fast_timer_id = None
        # self.on_timer()

        self.shutdown_stage = 0
        self.btn_shutdown = tki.Button(
            text='SHUTDOWN SOURCE', command=self.on_click_shutdown)
        self.btn_shutdown.place(x=358, y=910-30, height=28, width=350)

        self.active_ctrl_name = 'None'
        self.active_ctrl_value = 0.0
        self.active_ctrl_ammeter = -1.0

        self.the_socket_server = socket_server.SingleConnectionSocketServer(
            18001, self.on_socket_server_data)
        '''self.the_server_thread = threading.Thread(
            target=self.the_server_thread_function)
        self.the_server_thread.daemon = True
        self.the_server_thread.start()'''

        self.db_logger = duo_sqlite_logger.create_logger_from_env(
            self) if duo_sqlite_logger else None
        self.db_cycle_index = 0
        self._last_struct_warning_items = set()

        self.the_event = threading.Event()
        self.the_event.set()

        #self.the_fast_event = threading.Event()
        # self.the_fast_event.set()

        self.start_thread()

        #self.the_fast_thread = threading.Thread(target=self.the_fast_thread_function)
        # self.the_fast_thread.start()

    # winfo_height() works only after the main loop has started, so :
    def place_boxes(self):
        top = 1
        col = 0
        winhe = 1050  # self.winfo_height() - 20
        for i in range(len(self.the_items)):
            it = self.the_items[i]
            if hasattr(it, 'next_pos'):
                it = self.the_items[i+1]
            elif hasattr(it, 'prev_pos'):
                it = self.the_items[i-1]
            elif hasattr(it, 'hide_pos'):
                it.the_box.place(y=-400)
                it.chb_enabled.place(y=-400)
                continue
            he = it.the_box.winfo_height()
            if he+top+1 > winhe:
                top = 1
                col += 354
            it.the_box.place(x=4+col, y=top, width=350)
            it.chb_enabled.place(x=1+col, y=top)
            if self.fancy_pos and len(it.fancy_pos) >= 2:
                it.the_box.place(x=it.fancy_pos[0], y=it.fancy_pos[1])
                it.chb_enabled.place(x=it.fancy_pos[0]-3, y=it.fancy_pos[1])
            top += 1 + he
        chx = 780 if self.fancy_pos else 358+col
        self.chart.place(x=chx, y=20)
        chx2 = -800 if self.fancy_pos else chx
        self.chart_probe.place(
            x=chx2, y=20+self.chart.chartHeight+self.chart2.chartHeight*0)

        self.btn_probe.place(x=chx, y=0, height=18)
        self.btn_clear_graphs.place(x=100+chx, y=0, height=18)
        self.btn_save_data.place(x=220+chx, y=0, height=18)
        self.btn_presets.place(x=320+chx, y=0, height=18)

        try:
            self.place_note_widgets(col, top, chx)
        except Exception as ex:
            print('Operator note placement failed:', ex)

    # === operator note === :
    def init_note_widgets(self):
        self.note_status_timer_id = None
        self.note_var = tki.StringVar()
        self.lbl_note_title = tki.Label(text='Operator note:')
        self.txt_note = tki.Entry(textvariable=self.note_var, width=36)
        self.txt_note.bind('<Return>', self.on_note_post)
        self.txt_note.bind('<KP_Enter>', self.on_note_post)
        self.btn_note_post = tki.Button(text='Post', command=self.on_note_post)
        self.lbl_note_status = tki.Label(text='', anchor='w')

    def place_note_widgets(self, col, top, chx):
        if not hasattr(self, 'txt_note'):
            return
        if self.fancy_pos:
            # the probe chart is off-screen in this mode; use its slot below the chart
            self.place_note_row(0, 14, self.chart)
        elif top + 4 + NOTE_ROW_HEIGHT <= NOTE_MAX_BOTTOM:
            # below the last box of the last item column
            self.place_note_row(4+col, top + 4)
        else:
            # no room below the items: top button row, right of 'Presets...'
            self.lbl_note_title.place(x=-400, y=-400)
            self.txt_note.place(x=420+chx, y=0, width=180, height=18)
            self.btn_note_post.place(x=604+chx, y=0, width=50, height=18)
            self.lbl_note_status.place(x=658+chx, y=0, width=120, height=18)
        print('Operator note placed at', self.txt_note.place_info())

    def place_note_row(self, x, y, in_widget=None):
        rel = {} if in_widget is None else {'in_': in_widget, 'rely': 1.0}
        self.lbl_note_title.place(x=x, y=y, height=16, **rel)
        self.lbl_note_status.place(x=x+100, y=y, width=246, height=16, **rel)
        self.txt_note.place(x=x, y=y+18, width=262, height=22, **rel)
        self.btn_note_post.place(x=x+266, y=y+18, width=80, height=22, **rel)

    def on_note_post(self, _event=None):
        try:
            status, msg = post_operator_note(
                self.note_var.get(), getattr(self, 'db_logger', None),
                getattr(self, 'db_cycle_index', None), self.S1_or_S2)
            if status in ('db', 'file'):
                self.note_var.set('')
            if status != 'empty':
                self.show_note_status(msg, 'dark green' if status == 'db' else 'dark orange' if status == 'file' else 'red')
        except Exception as ex:
            print('Operator note post failed:', ex)
        return 'break'

    def show_note_status(self, msg, color):
        try:
            self.lbl_note_status.configure(text=msg, fg=color)
            if self.note_status_timer_id is not None:
                self.master.after_cancel(self.note_status_timer_id)
            self.note_status_timer_id = self.master.after(
                NOTE_STATUS_MS, self.clear_note_status)
        except Exception as ex:
            print('Operator note status failed:', ex)

    def clear_note_status(self):
        try:
            self.note_status_timer_id = None
            self.lbl_note_status.configure(text='')
        except Exception as ex:
            print('Operator note status clear failed:', ex)

    def on_click_shutdown(self):
        self.shutdown_stage = 0
        toplevel = tki.Toplevel()
        toplevel.geometry('400x152')
        # toplevel.attributes('-topmost', True) # does nothing
        toplevel.transient(self.winfo_toplevel())
        self.shutdown_label = tki.Label(
            toplevel, text='Shutdown source?', fg='red', font=('', 16))
        self.shutdown_label.place(x=4, y=10)
        self.shutdown_label2 = tki.Label(
            toplevel, text='Shutdown in                hours')
        self.shutdown_label2.place(x=4, y=36)
        var_hours = tki.StringVar()
        var_hours.set('0.0')
        txt_hours = tki.Entry(toplevel, textvariable=var_hours)
        txt_hours.place(x=97, y=36, width=50)

        def cmd_cancel(_ev=None):
            self.shutdown_stage = 0
            toplevel.destroy()

        def cmd_shutdown():
            try:
                tmo = float(var_hours.get().strip())
            except:
                tmo = 0
                tkinter.messagebox.showerror(
                    'fail', 'bad string, cant convert to float ' + var_hours.get())
                return
            self.shutdown_stage = 1
            txt_hours.place(y=-90)
            btn_shutdwn.place(y=-90)
            self.shutdown_label.configure(text='Shutting down in ...')
            self.shutdown_label2.configure(
                text='Leave this window open.\nYou can leave.')
            self.shutdown_time = time.time() + tmo*3600 + 10
        self.shutdown_btn_cancel = tki.Button(
            toplevel, text='Cancel', command=cmd_cancel)
        self.shutdown_btn_cancel.place(x=40, y=106)
        btn_shutdwn = tki.Button(
            toplevel, text='SHUTDOWN', command=cmd_shutdown)
        btn_shutdwn.place(x=190, y=106)
        toplevel.bind('<Destroy>', cmd_cancel)

    def process_shutdown(self):
        if self.shutdown_stage == 0:
            return
        if self.shutdown_stage == 1:
            self.the_pre_acc = None
        if self.shutdown_stage < 11:
            s_left = max(0, round(self.shutdown_time - time.time()))
            h = s_left//3600
            m = (s_left-h*3600)//60
            s = s_left-h*3600-m*60
            self.shutdown_label.configure(text='Shutting down in '+('' if h == 0 else (
                str(h)+' h, '))+('' if m == 0 and h == 0 else (str(m)+' min, '))+str(s)+' s...')
            #self.shutdown_label.configure(text='Shutting down in {:g} ...'.format(11-self.shutdown_stage))
            if s_left == 0:
                self.shutdown_stage = 11
            return
        if self.shutdown_stage == 11:
            # print('koven?')
            for it in self.the_items:
                if isinstance(it, koven.KOven):  # it is koven.KOven:
                    # print('YES')
                    self.shutdown_label.configure(
                        text='Shutting down K oven ...')
                    it.switchOff()
                    self.the_koven = it
                    self.shutdown_stage = 1000
                    return
            # print('NO??')
            self.shutdown_stage = 12
        if self.shutdown_stage >= 1000:
            if self.the_koven.CR > 100:
                self.shutdown_label.configure(
                    text='K oven off, waiting, T = {:d} °C...'.format(round(self.the_koven.CR)))
                self.shutdown_label2.configure(
                    text='Waiting for oven T to reach < 100 °C.\nSource will automatically switch off after that.\nLeave this window open.\nYou can leave.')
            else:
                self.shutdown_stage = 12
            return
        if self.shutdown_stage == 12:  # preacceleration:
            if self.the_pre_acc is None:
                print('pre-acc?')
                for it in self.the_items:
                    if 'Pre-acc' in it.the_name:  # it is preacceleration:
                        print('YES')
                        self.shutdown_label.configure(
                            text='Shutting down Pre-acceleration ...')
                        it.switchOff()
                        self.the_pre_acc = it
                        return
                print('NO??')
            if not self.the_pre_acc is None:
                if self.the_pre_acc.current > 0:
                    self.shutdown_label.configure(
                        text='Pre-acc off, waiting, U = {:d} V...'.format(round(self.the_pre_acc.current*1000)))
                    self.shutdown_label2.configure(
                        text='Waiting for preacc to reach 0 V...')
                    return
            self.shutdown_stage += 1
        if self.shutdown_stage >= 13 and len(self.the_items) > self.shutdown_stage-13:
            it = self.the_items[self.shutdown_stage-13]
            self.shutdown_label.configure(
                text='Shutting down {:s} ...'.format(it.the_name))
            self.shutdown_label2.configure(
                text='Leave this window open.\nYou can leave.')
            if hasattr(it, 'switchOff'):
                it.switchOff()
            self.shutdown_stage += 1
            return
        if len(self.the_items) == self.shutdown_stage-13:
            self.shutdown_label.configure(text='Source is off.')
            self.shutdown_label2.configure(text='Done. You can leave.')
            self.shutdown_btn_cancel.configure(text='Ok')
            self.shutdown_stage = 0
            return

    def clear_graphs(self):
        self.clear_graphs_flag = True

    def save_data(self):
        self.save_data_flag = True

    def on_save_zoom_proc(self, ev, _x_minmax, y_minmax, _y2_minmax):
        '''dlg = tki.Toplevel()
        label=tki.Label(dlg, text='Overwrite saved default zoom?')
            self.label.pack()'''
        print('save zoom called, event state', ev.state)
        if not ev.state & 4:  # 4 is the Ctrl key
            return
        print('saving default zoom...')
        f = open('saved_zoom_'+self.S1_or_S2+'.txt', 'w', encoding='utf-8')
        t = ''
        for mm, cb in zip(y_minmax, self.the_checkbuttons):
            n = cb.master.cget('text') + ' '+cb.cget('text')
            t += n.split('=')[0].strip() + '\t' + str(mm[0])+'\t' + \
                str(mm[1])+'\t'+('1' if get_checked(cb) else '0')+'\n'
        #t = t.strip()
        f.write(t)
        f.close()

    def save_minmax(self):
        print('save bars called, event state')
        f = open('saved_minmax_'+self.S1_or_S2+'.txt', 'w', encoding='utf-8')
        t = ''
        for bar in self.the_bars:
            t += bar.bar_name + '\t' + \
                str(bar.minmax[0]) + '\t' + str(bar.minmax[1]) + \
                '\t' + str(bar.minmax[2]) + '\n'
        f.write(t)
        f.close()

    def on_change_ctrl_proc(self, aname, avalue):
        self.active_ctrl_name = aname
        self.active_ctrl_value = avalue
        #print('on_change_ctrl_proc', self.active_ctrl_name, self.active_ctrl_value)

    def on_btn_probe(self, event):
        try:
            self.menu_probe.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu_probe.grab_release()

    def on_btn_presets(self, event):
        try:
            self.menu_presets = tki.Menu(self.master, tearoff=0)
            self.menu_presets.add_command(
                label='Save...', command=self.menu_presets_save)
            self.menu_presets.add_command(label='Cancel')
            self.menu_presets.add_separator()
            for na in self.get_preset_file_names():
                self.menu_presets.add_command(
                    label=na, command=lambda n=na: self.load_preset(n))  # type: ignore
            self.menu_presets.tk_popup(event.x_root, event.y_root)
        finally:
            pass  # self.menu_presets.grab_release()

    def load_preset(self, fn):
        with open('presets/'+self.S1_or_S2+'/' + fn, 'r', encoding='utf-8') as f:
            for line in f.readlines():
                ll = line.split(' = ')
                if len(ll) == 2:
                    for item in self.the_items:
                        if item.the_name + ' c' == ll[0]:
                            print('setting c', ll)
                            # type: ignore # wtf is the point in declaring shit when it complains anyway #@x@%
                            item.var_current.set(ll[1].strip())
                            item.on_currentReturn(None)
                        if item.the_name + ' f' == ll[0]:
                            print('setting f', ll)
                            item.var_filament.set(
                                ll[1].strip())  # type: ignore
                            item.on_filamentReturn(None)

    def get_preset_file_names(self):
        return os.listdir('presets/'+self.S1_or_S2)

    def menu_presets_save(self):
        toplevel = tki.Toplevel()
        toplevel.geometry('208x90')
        toplevel.transient(self.winfo_toplevel())
        lbl = tki.Label(toplevel, text='Save as')
        lbl.place(x=4, y=4)

        def cmd_save(_ev=None):
            fn = var_fn.get().strip()
            if fn == '':
                return
            with open('presets/'+self.S1_or_S2+'/' + fn, 'w', encoding='utf-8') as f:
                for it in self.the_items:
                    if it.is_master and hasattr(it, 'var_current'):
                        f.write(it.the_name + ' c = ' +
                                it.var_current.get() + '\n')
                    if it.is_master and hasattr(it, 'var_filament'):
                        f.write(it.the_name + ' f = ' +
                                it.var_filament.get() + '\n')
            toplevel.destroy()
        var_fn = tki.StringVar()
        combo = Combobox(toplevel, textvariable=var_fn,
                         values=self.get_preset_file_names())
        combo.place(x=4, y=28, width=200)
        combo.bind('<Return>', cmd_save)
        combo.bind('<KP_Enter>', cmd_save)
        btn = tki.Button(toplevel, text='Cancel', command=toplevel.destroy)
        btn.place(x=20, y=54)
        btn = tki.Button(toplevel, text='Save', command=cmd_save)
        btn.place(x=120, y=54)

    #placement_info = {}

    def on_enable(self, item):
        en = get_checked(item.chb_enabled)
        item.enabled = en
        if en:
            item.the_box.place(**item.placement_info)
        else:
            item.placement_info = item.the_box.place_info()
            item.the_box.place_forget()
        '''return
        for c in item.the_box.winfo_children():
            if c != item.chb_enabled:
                if en:
                    c.place(**self.placement_info[c])
                else:
                    self.placement_info[c] = c.place_info()
                    c.place_forget()'''

    def on_menu_probe(self, txt):
        self.btn_probe.configure(text=txt)

    '''def the_server_thread_function(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('', 18001))
            except:
                print('Server socket 18001 already in use, will not listen.')
                return
            s.listen(10)
            print('>>>> socket server: listening on port 18001')
            while not self.stop_event.is_set():
                conn, addr = s.accept()
                with conn:
                    print('>>>> socket server: connected by ', addr)
                    if self.stop_event.is_set():
                        print('>>>> socket server got a stop event, closing.')
                        break
                    conn.settimeout(2.0)
                    while not self.stop_event.is_set():
                        try:
                            data = conn.recv(1024)
                            #print('>>>> socket server: got: ', data)
                            if not data:
                                print('>>>> socket server: client disconnected')
                                break
                        except socket.timeout:
                            print('----> socket timeout, ok')
                            continue
                        #msg = data.decode('utf-8').strip().split()
                        #if len(msg) > 0 and msg[0] == 'get':
                        if len(data) > 0 and data[:3] == b'get':
                            conn.sendall(
                                bytes(self.active_ctrl_name+'\t'+str(self.active_ctrl_value)+'\n', 'utf-8'))
                        if len(data) == 8: #'get'+float_fc_value+byte_selected_fc_index
                            try:
                                self.main_selected_fc_value, self.main_selected_fc_index = struct.unpack('fb', data[3:])
                                #self.bpm = float(msg[1])
                                print(self.main_selected_fc_value, self.main_selected_fc_index)
                            except Exception as ex:
                                print('no valid bpm value', ex)
            s.close()
            print('>>>> socket server closed <<<<<<<')
            
    
    def stop_the_socket_server(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.2)
        print('sending shutdown socket...')
        try:
            s.connect(('localhost', 18001))
        except Exception as ex:
            print('exception when connecting shutdown socket in stop_the_socket_server', ex)
        s.close()
        print('sending shutdown socket completed')'''

    def on_socket_server_data(self, data):
        if len(data) >= 3 and data[:3] == b'get':
            if self.active_ctrl_ammeter >= -0.5:
                ret = bytes(self.active_ctrl_name+'\t'+str(self.active_ctrl_value) +
                            '\t'+str(self.active_ctrl_ammeter)+'\n', 'utf-8')
            else:
                ret = bytes(self.active_ctrl_name+'\t' +
                            str(self.active_ctrl_value)+'\n', 'utf-8')
        else:
            ret = b''
        #print(self.active_ctrl_ammeter, ret)
        if len(data) == 8:  # 'get'+float4_fc_value+byte1_selected_fc_index
            try:
                v, self.main_selected_fc_index = struct.unpack('fb', data[3:])
                v *= 1e9
                self.main_selected_fc_value[0] += v
                self.main_selected_fc_value[3] += 1
                if self.main_selected_fc_value[1] > v:
                    self.main_selected_fc_value[1] = v
                if self.main_selected_fc_value[2] < v:
                    self.main_selected_fc_value[2] = v
                #self.bpm = float(msg[1])
                #print(self.main_selected_fc_value, self.main_selected_fc_index)
            except Exception as ex:
                print('no valid bpm value', ex)
        return ret

    def start_thread(self):
        self.the_thread = threading.Thread(
            target=self.the_thread_function_multi_once)
        self.the_thread.start()

    '''def the_thread_function(self):
        #while not self.stop_flag:
        #    self.get_all_data()
        probe_ind = int(self.menu_probe_var.get())
        if probe_ind > 0:
            t0 = time.time()
            self.data_probe_x, self.data_probe_y = self.the_probes[probe_ind-1]()
            #print('sdfdfdf:', self.data_probe_y)
            print('probe:', round((time.time()-t0)*1000), 'ms')
        
        if self.clear_graphs_flag:
            self.data_x = []
            for i in range(len(self.data_y)):
                self.data_y[i] = []
                self.data_bands[i] = ([],[])
            self.clear_graphs_flag = False
        
        statstr = ''
        i = 0
        for item in self.the_items:
            t0 = time.time()
            if self.stop_flag:
                break
            # NOTE: StringVar.get() actually requires the main thread to be active, so calling e.g. join() may result in a deadlock!
            if item.enabled:
                ret = item.get_data()   # this is called in a thread, so the item SHALL NOT update its ui!
                item.last_ret = ret
            else:
                ret = item.last_ret
            #print(i, item.the_name, round((time.time()-t0)*1000), 'ms')
            statstr += item.the_name +':'+ str(round((time.time()-t0)*1000))+' '
            
            if ret is None:
                continue
            for j in range(len(ret)):
                datay = self.data_y[i]
                datab = self.data_bands[i]
                retj = ret[j]
                if type(retj) is tuple:
                    datay.append(retj[0])
                    datab[0].append(retj[1])
                    datab[1].append(retj[2])
                else:
                    datay.append(retj)
                if len(datay) > MAX_PTS_PER_GRAPH:
                    datay.pop(0)
                    if len(datab)>0 and len(datab[0])>0:
                        datab[0].pop(0)
                        datab[1].pop(0)
                i += 1
        print(statstr)
        #nn = len(self.data_y[0])
        #self.data_x = [-nn+i+1 for i in range(nn)]
        now = time.time()
        dx = (now - self.last_time) / S_PER_TIMEUNIT
        self.last_time = now
        self.data_x = [x-dx for x in self.data_x]
        self.data_x.append(0)
        if len(self.data_x) > MAX_PTS_PER_GRAPH:
            self.data_x.pop(0)

        if self.stop_flag:
            print('stop flag seen in thread, exiting..')
            return
        self.updateui_timer_id = self.master.after(0, self.update_ui)'''

    def item_thread_function(self, item):
        # if self.nnn:
        #    return
        #print('an item thread started')
        t0 = time.time()
        # if not hasattr(item, 'last_ret'):
        item.get_data()   # this is called in a thread, so the item SHALL NOT update its ui!
        item.time_to_get_ms = round((time.time()-t0)*1000)
        #print('an item thread finished')

    '''def item_fast_thread_function(self, item):
        t0 = time.time()
        item.get_fast_data()   # this is called in a thread, so the item SHALL NOT update its ui!
        item.time_to_get_ms = round((time.time()-t0)*1000)
        #print('an item thread finished')'''

    def the_thread_function_multi(self):
        # while not self.stop_flag:
        #    self.get_all_data()
        #print('multi thread started')
        '''
        probe_ind = int(self.menu_probe_var.get())
        if probe_ind > 0:
            t0 = time.time()
            self.data_probe_x, self.data_probe_y = self.the_probes[probe_ind-1]()
            #print('sdfdfdf:', self.data_probe_y)
            print('probe:', round((time.time()-t0)*1000), 'ms')

        if self.clear_graphs_flag:
            self.data_x = []
            for i in range(len(self.data_y)):
                self.data_y[i] = []
                self.data_bands[i] = ([],[])
            self.clear_graphs_flag = False

        statstr = ''
        i = 0
        for item in self.the_items:
            if self.stop_flag:
                break
            # NOTE: StringVar.get() actually requires the main thread to be active, so calling e.g. join() may result in a deadlock!
            if item.enabled:
                item.thread = threading.Thread(target=self.item_thread_function, args=[item])
                item.thread.start()

        for item in self.the_items:
            t0 = time.time()
            if self.stop_flag:
                break
            # NOTE: StringVar.get() actually requires the main thread to be active, so calling e.g. join() may result in a deadlock!
            if item.enabled:
                item.thread.join()
                statstr += item.the_name +':'+ str(item.time_to_get_ms)+' '
                #print('a thread joined')
            ret = item.last_ret
            #print(i, item.the_name, round((time.time()-t0)*1000), 'ms')

            if ret is None:
                continue
            for j in range(len(ret)):         
                datay = self.data_y[i]
                datab = self.data_bands[i]
                retj = ret[j]
                if type(retj) is tuple:
                    datay.append(retj[0])
                    datab[0].append(retj[1])
                    datab[1].append(retj[2])
                else:
                    datay.append(retj)
                if len(datay) > MAX_PTS_PER_GRAPH:
                    datay.pop(0)
                    if len(datab)>0 and len(datab[0])>0:
                        datab[0].pop(0)
                        datab[1].pop(0)
                i += 1
        #print(statstr)
        #nn = len(self.data_y[0])
        #self.data_x = [-nn+i+1 for i in range(nn)]
        now = time.time()
        dx = (now - self.last_time) / S_PER_TIMEUNIT
        self.last_time = now
        self.data_x = [x-dx for x in self.data_x]
        self.data_x.append(0)
        # print(round(100*len(self.data_x)/MAX_PTS_PER_GRAPH))
        if len(self.data_x) > MAX_PTS_PER_GRAPH:
            self.data_x.pop(0)

        if self.stop_flag:
            print('stop flag seen in thread, exiting..')
            return
        self.updateui_timer_id = self.master.after(0, self.update_ui)
        #self.nnn=True'''

    def the_thread_function_multi_once(self):
        #print('multi thread started')
        while not self.stop_event.is_set():
            self.the_event.wait()
            self.the_event.clear()
            if self.stop_event.is_set():
                return
            print('wtf 1')
            probe_ind = int(self.menu_probe_var.get())
            print('wtf 2')
            if probe_ind > 0:
                t0 = time.time()
                self.data_probe_x, self.data_probe_y = self.the_probes[probe_ind-1](
                )
                #print('sdfdfdf:', self.data_probe_y)
                print('probe:', round((time.time()-t0)*1000), 'ms')

            if self.clear_graphs_flag:
                self.data_x = []
                for i in range(len(self.data_y)):
                    self.data_y[i] = []
                    self.data_bands[i] = ([], [])
                self.clear_graphs_flag = False

            statstr = ''
            i = 0
            print('starting threads...')
            for item in self.the_items:
                # if self.stop_event.is_set():
                #    break
                # NOTE: StringVar.get() actually requires the main thread to be active, so calling e.g. join() may result in a deadlock!
                if item.is_master and (item.enabled or (not item.slave is None and item.slave.enabled)):
                    item.thread = threading.Thread(
                        target=self.item_thread_function, args=[item])
                    item.thread.start()
                else:
                    item.thread = None  # type: ignore # oh cmon wtf

            print('waiting for threads to end...')
            for item in self.the_items:
                t0 = time.time()
                # NOTE: StringVar.get() actually requires the main thread to be active, so calling e.g. join() may result in a deadlock!
                if not item.thread is None:
                    item.thread.join()
                    statstr += item.the_name + ':' + \
                        str(item.time_to_get_ms)+' '
                    #print('a thread joined')
                try:
                    ret = item.last_ret  # type: ignore
                except:
                    print(item.the_name)
                #print(i, item.the_name, round((time.time()-t0)*1000), 'ms')

                if ret is None:
                    continue
                for j in range(len(ret)):
                    datay = self.data_y[i]
                    datab = self.data_bands[i]
                    retj = ret[j]
                    if type(retj) is tuple:
                        datay.append(retj[0])
                        datab[0].append(retj[1])
                        datab[1].append(retj[2])
                    else:
                        datay.append(retj)
                    if len(datay) > MAX_PTS_PER_GRAPH:
                        datay.pop(0)
                        if len(datab) > 0 and len(datab[0]) > 0:
                            datab[0].pop(0)
                            datab[1].pop(0)
                    i += 1
            print('threads done...')
            # print(statstr)
            #nn = len(self.data_y[0])
            #self.data_x = [-nn+i+1 for i in range(nn)]
            now = time.time()
            dx = (now - self.last_time) / S_PER_TIMEUNIT
            self.last_time = now
            # 36 ms with tracemalloc, 2.5 ms normally
            self.data_x = [x-dx for x in self.data_x]
            # for i in range(len(self.data_x)): self.data_x[i] -= dx   # 270 ms with tracemalloc, 4 ms normally
            # self.data_x[:] = map(lambda x: x-dx, self.data_x)        #  43 ms with tracemalloc, 8 ms normally
            self.data_x.append(0)
            # print((time.time()-now)*1000)
            # print(round(100*len(self.data_x)/MAX_PTS_PER_GRAPH))
            if len(self.data_x) > MAX_PTS_PER_GRAPH:
                self.data_x.pop(0)

            print('wtf 3')
            for item in self.the_items:
                # print(item.last_names)
                # print(item.last_ctrl)
                # print(item.last_ret)
                names = getattr(item, 'last_names', None)
                ctrl = getattr(item, 'last_ctrl', None)
                ret = getattr(item, 'last_ret', None)
                warning_key = id(item)
                if names is None or ctrl is None:
                    if warning_key not in self._last_struct_warning_items:
                        print('SQLite metadata missing for', getattr(
                            item, 'the_name', 'unknown item'))
                        self._last_struct_warning_items.add(warning_key)
                elif len(names) != len(ctrl)+len(ret or [])+1:
                    if warning_key not in self._last_struct_warning_items:
                        print('SQLite metadata length mismatch for', getattr(item, 'the_name', 'unknown item'),
                              'names=', len(names), 'ctrl=', len(ctrl), 'ret=', len(ret or []))
                        self._last_struct_warning_items.add(warning_key)

            print('wtf 4')
            if self.db_logger is not None:
                self.db_cycle_index += 1
                self.db_logger.log_cycle(self, self.db_cycle_index)
            print('wtf 5')

            if self.stop_event.is_set():
                print('stop flag seen in thread, exiting..')
                return

            '''if not hasattr(self, 'ctrtst'):
                self.ctrtst = 0
                import tracemalloc # warning: with tracemalloc some operations are > 10x slower!
            if self.ctrtst == 10:
                print(threading.enumerate())
                tracemalloc.start()
            if self.ctrtst %100 == 11:
                print(threading.enumerate())
                snapshot = tracemalloc.take_snapshot()
                top_stats = snapshot.statistics('lineno')
                for stat in top_stats[:10]:
                    print(stat)
                print('\n')
            self.ctrtst +=1'''
            tt = time.time()
            print('wtf 5.5')
            self.updateui_timer_id = self.master.after(0, self.update_ui)
            print('wtf 6', (time.time()-tt)*1000)
            # self.nnn=True

    '''def the_fast_thread_function(self):
        #print('multi thread started')
        while not self.stop_event.is_set():
            self.the_fast_event.wait()
            self.the_fast_event.clear()
            if self.stop_event.is_set():
                return
            i = 0
            for item in self.the_items:
                #if self.stop_event.is_set():
                #    break
                # NOTE: StringVar.get() actually requires the main thread to be active, so calling e.g. join() may result in a deadlock!
                if hasattr(item, 'get_fast_data'):
                    item.fast_thread = threading.Thread(target=item.get_fast_data)
                    item.fast_thread.start()
                else:
                    item.fast_thread = None # type: ignore # oh cmon wtf

            for item in self.the_items:
                t0 = time.time()
                # NOTE: StringVar.get() actually requires the main thread to be active, so calling e.g. join() may result in a deadlock!
                if not item.fast_thread is None:
                    item.fast_thread.join()
                    #print('a thread joined')
                    ret = item.last_fast_ret # type: ignore
                #print(i, item.the_name, round((time.time()-t0)*1000), 'ms')
                
                if ret is None:
                    continue
                for j in range(len(ret)):         
                    datay = self.data_y[i]
                    datab = self.data_bands[i]
                    retj = ret[j]
                    if type(retj) is tuple:
                        datay.append(retj[0])
                        datab[0].append(retj[1])
                        datab[1].append(retj[2])
                    else:
                        datay.append(retj)
                    if len(datay) > MAX_PTS_PER_GRAPH:
                        datay.pop(0)
                        if len(datab)>0 and len(datab[0])>0:
                            datab[0].pop(0)
                            datab[1].pop(0)
                    i += 1
            if self.stop_event.is_set():
                print('stop flag seen in thread, exiting..')
                return
            self.updateui_fast_timer_id = self.master.after(0, self.update_fast_ui)
            #self.nnn=True'''

    def draw_chart(self, full=False):
        if len(self.data_x) > 1:
            y1 = []
            y2 = []
            y3 = []
            y4 = []
            l1 = []
            l2 = []
            l3 = []
            l4 = []
            b1 = []
            b2 = []
            b3 = []
            b4 = []
            there = False
            for i in range(len(self.data_y)):
                cb = self.the_checkbuttons[i]
                if get_checked(cb) and cb.item.enabled:
                    there = True
                    axis = cb.axis
                    if axis == '1L':
                        y1.append(self.data_y[i])
                        l1.append(cb.master.cget('text') + ' '+cb.cget('text'))
                        b1.append(self.data_bands[i])
                    if axis == '1R':
                        y2.append(self.data_y[i])
                        l2.append(cb.cget('text'))
                        b2.append(self.data_bands[i])
                    if axis == '2L':
                        y3.append(self.data_y[i])
                        l3.append(cb.cget('text'))
                        b3.append(self.data_bands[i])
                    if axis == '2R':
                        y4.append(self.data_y[i])
                        l4.append(cb.cget('text'))
                        b4.append(self.data_bands[i])
                else:
                    y1.append([])
                    l1.append(cb.cget('text'))
                    b1.append(([], []))  # b1.append([])

            #print('\nx:', self.data_x, '\ny:', y1, '\nb:', b1)
            if len(y1) > -1 and there:
                self.chart.draw(self.data_x, y1, y2, l1, l2, b1, b2,
                                full=full, x_minmax=(-20, 0), y_minmax=self.saved_zoom)
            # if len(y3)>-1:
            #    self.chart2.draw(self.data_x, y3, y4, l3, l4, b3, b4)

            if self.save_data_flag:
                with open(time.strftime('%Y_%m_%d__%H_%M_%S.txt'), 'w', encoding='utf-8') as f:
                    s = 'time, min'
                    for t, y in zip(l1, y1):
                        if len(y) > 0:
                            s += '\t'+t
                    f.write(s+'\n')
                    for i in range(len(self.data_x)):
                        s = str(self.data_x[i])
                        for y in y1:
                            if len(y) > 0:
                                s += '\t'+str(y[i])
                        f.write(s+'\n')

                self.save_data_flag = False

        probe_ind = int(self.menu_probe_var.get())
        if probe_ind > 0 and len(self.data_probe_y) > 1:
            self.chart_probe.draw(self.data_probe_x, [self.data_probe_y])

    def update_ui(self):
        #statstr = '     '
        #t0 = time.time()
        for item in self.the_items:
            try:
                #t0 = time.time()
                if item.is_master:
                    item.update_ui()  # takes < 1 ms
                #statstr += item.the_name +':'+ str(round((time.time()-t0)*1000))+' '
            except Exception as ex:
                print('EXCEPTION in update_ui!', ex)
        #t0 = time.time()
        self.draw_chart(full=True)
        #statstr += 'charts:'+ str(round((time.time()-t0)*1000))
        # print(round((time.time()-t0)*1000))
        self.process_shutdown()
        # reset_event)#self.start_thread)
        self.thread_timer_id = self.master.after(
            UPDATE_PERIOD_MS, self.the_event.set)

    '''def update_fast_ui(self):        
        #statstr = '     '
        #t0 = time.time()
        for item in self.the_items:
            try:
                #t0 = time.time()
                if hasattr(item, 'update_fast_ui'):
                    item.update_ui() # takes < 1 ms
                #statstr += item.the_name +':'+ str(round((time.time()-t0)*1000))+' '
            except Exception as ex:
                print('EXCEPTION in update_fast_ui!', ex)
        #t0 = time.time()
        #self.draw_chart(full=True)
        #statstr += 'charts:'+ str(round((time.time()-t0)*1000))
        #print(round((time.time()-t0)*1000))
        self.thread_fast_timer_id = self.master.after(UPDATE_PERIOD_MS, self.the_fast_event.set)#reset_event)#self.start_thread)
        '''
    # def reset_event(self):
    #    self.the_event.set()

    def select_chb(self, chb, selected):
        if selected:
            chb.configure(bg='white')
            chb.configure(activebackground='white')
            chb.configure(relief='solid')
        else:
            chb.configure(bg=self.default_color)
            chb.configure(activebackground=self.default_color_a)
            chb.configure(relief='flat')

    def on_select_line_proc(self, old, newind):
        if old >= 0:
            self.select_chb(self.the_checkbuttons[old], False)
        if newind >= 0:
            self.select_chb(self.the_checkbuttons[newind], True)

    def on_chb(self, event, chb, b, chbind):
        #print('df', b, event.x)
        prevent_uncheck = False
        # will be the new state, unless we would uncheck by clicking on the label:
        checked = not get_checked(chb)
        if event.x > 20 and not checked:
            prevent_uncheck = True
            checked = True
        if checked:
            if self.chart.selected_line_ind >= 0:
                self.select_chb(
                    self.the_checkbuttons[self.chart.selected_line_ind], False)
            if self.chart.selected_line_ind == chbind:
                self.chart.selected_line_ind = -1
            else:
                self.chart.selected_line_ind = chbind
                self.select_chb(chb, True)
        else:
            if self.chart.selected_line_ind == chbind:
                self.chart.selected_line_ind = -1
                self.select_chb(chb, False)

        if b == 3:
            self.menuvar.set(chb.axis)
            m = tki.Menu(self.master, tearoff=0)
            m.add_radiobutton(label='chart1, left axis', value='1L',
                              variable=self.menuvar, command=lambda: self.on_menu('1L', chb))
            m.add_radiobutton(label='chart1, right axis', value='1R',
                              variable=self.menuvar, command=lambda: self.on_menu('1R', chb))
            m.add_radiobutton(label='chart2, left axis', value='2L',
                              variable=self.menuvar, command=lambda: self.on_menu('2L', chb))
            m.add_radiobutton(label='chart2, right axis', value='2R',
                              variable=self.menuvar, command=lambda: self.on_menu('2R', chb))
            try:
                m.tk_popup(event.x_root, event.y_root)
            finally:
                m.grab_release()
        self.draw_chart()
        if prevent_uncheck:
            return 'break'
        return ''

    def on_chb_down(self, _event, chb, _b, _chbind):
        print(get_checked(chb))

    def on_menu(self, ax, chb):
        print(ax, chb)
        chb.axis = ax

    def on_destroy(self, _event):
        # this is called many times though (for each entry?)
        # if not self.stop_event.is_set():
        #    print(_event.widget)
        if _event.widget is not self:  # self.master: # apparently first the self is destroyed, then a ton of widgets, then finally the master
            return
        # print(_event.widget)
        if getattr(self, "db_logger", None) is not None:
            self.db_logger.close()
            self.db_logger = None
        #print('stopping...', self.timer_id)
        if not (self.thread_timer_id is None):
            self.stop_event.set()
            self.the_event.set()
            # self.the_fast_event.set()
            # self.stop_the_socket_server()
            self.the_socket_server.stop()
            print('joining thread...')
            self.the_thread.join()
            # self.the_fast_thread.join()
            print('joined; stopping thread timer...')
            self.master.after_cancel(self.thread_timer_id)
            # self.master.after_cancel(self.thread_fast_timer_id)
            self.thread_timer_id = None
            #self.thread_fast_timer_id = None
            print('stopped; destroying items...')
            for item in self.the_items:
                if item.is_master:
                    item.on_destroy()
            print('destroyed; ThreadTimer deleted.')
        if not (self.updateui_timer_id is None):
            self.master.after_cancel(self.updateui_timer_id)
            self.updateui_timer_id = None
            print('UpdateUITimer deleted.')
        # if not (self.updateui_fast_timer_id is None):
        #    self.master.after_cancel(self.updateui_fast_timer_id)
        #    self.updateui_fast_timer_id = None
        #    print('UpdateUIFastTimer deleted.')

    def on_resize(self, event):
        if event.widget == self.master:
            #print('¤¤¤¤¤¤¤¤¤¤¤¤¤¤¤¤¤¤¤¤¤¤¤¤', event.height)
            w = event.width-self.chart.winfo_x()-4
            h = event.height-self.chart.winfo_y()-344
            if w != self.chart.winfo_width() or h != self.chart.winfo_height():
                self.chart.resize(w, h)
                self.chart_probe.place(y=h+34)
                self.btn_shutdown.place(y=event.height-30)

            # else:
            #    print('No change')
'''
    def on_timer(self):
        i = 0
        for item in self.the_items:
            t0 = time.time()
            ret = item.on_timer()
            print(i, round((time.time()-t0)*1000), 'ms')
            if ret is None:
                continue
            for j in range(len(ret)):
                datay = self.data_y[i]
                datay.append(ret[j])
                if len(datay) > MAX_PTS_PER_GRAPH:
                    datay.pop(0)
                i += 1
        
        nn = len(self.data_y[0])
        self.data_x = [-nn+i+1 for i in range(nn)]
        if len(self.data_x)>2:
            y1 = []
            for i in range(len(self.data_y)):
                if get_checked(self.the_checkbuttons[i]):
                    y1.append(self.data_y[i])
            if len(y1)>0:
                self.chart.draw(self.data_x, y1)

            
            
        self.timer_id = self.master.after(UPDATE_PERIOD_MS, self.on_timer)
'''


NOTE_MAX_CHARS = 1000
NOTE_STATUS_MS = 3000
NOTE_ROW_HEIGHT = 40
NOTE_MAX_BOTTOM = 780  # keep the note row well above the SHUTDOWN SOURCE button (y >= 880)
NOTE_CONFIG_PATH = os.path.join(os.path.dirname(
    os.path.abspath(__file__)), 'duo_logging_config.json')


def clean_note_text(text):
    # single line, stripped, at most NOTE_MAX_CHARS
    return ' '.join(str(text).split())[:NOTE_MAX_CHARS]


def note_fallback_dirs():
    # logging base_dir from the config first, then the script folder
    dirs = []
    try:
        import json
        with open(NOTE_CONFIG_PATH, 'r', encoding='utf-8') as f:
            base_dir = json.load(f).get('base_dir')
        if base_dir:
            dirs.append(os.path.expanduser(str(base_dir)))
    except Exception as ex:
        print('Operator note: no base_dir from config:', ex)
    dirs.append(os.path.dirname(os.path.abspath(__file__)))
    return dirs


def append_note_to_file(source, text, ts_unix=None, dirs=None):
    # tab-separated line: ts_utc, source, text; returns the path or None
    import datetime
    if ts_unix is None:
        ts_unix = time.time()
    ts_utc = datetime.datetime.fromtimestamp(
        ts_unix, tz=datetime.timezone.utc).isoformat().replace('+00:00', 'Z')
    month = datetime.datetime.fromtimestamp(ts_unix).strftime('%Y_%m')
    line = ts_utc + '\t' + str(source) + '\t' + clean_note_text(text) + '\n'
    for d in (note_fallback_dirs() if dirs is None else dirs):
        path = os.path.join(d, 'notes_' + str(source) + '_' + month + '.txt')
        try:
            os.makedirs(d, exist_ok=True)
            with open(path, 'a', encoding='utf-8') as f:
                f.write(line)
            return path
        except Exception as ex:
            print('Operator note: cannot write', path, ex)
    return None


def post_operator_note(text, db_logger, cycle_index, source, dirs=None):
    # returns (status, message); status is 'empty', 'db', 'file' or 'failed'
    text = clean_note_text(text)
    if not text:
        return 'empty', ''
    if db_logger is not None:
        try:
            if db_logger.log_note(text, cycle_index):
                return 'db', 'Saved ' + time.strftime('%H:%M:%S')
            print('Operator note: logger did not accept the note; using fallback file')
        except Exception as ex:
            print('Operator note: logger failed:', ex)
    path = append_note_to_file(source, text, dirs=dirs)
    if path is None:
        print('Operator note NOT saved:', text)
        return 'failed', 'NOT saved (see console)'
    print('Operator note saved to', path)
    return 'file', 'Saved to file ' + time.strftime('%H:%M:%S')


def get_checked(chb):
    return int(chb.getvar(chb.cget('variable'))) == 1


def set_checked(chb, v):
    chb.setvar(chb.cget('variable'), 1 if v else 0)
