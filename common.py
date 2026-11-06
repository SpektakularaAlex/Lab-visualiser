import socket
import select
import subprocess
import time
import datetime
import array
import tkinter as tki
import threading
import mychart_pil as mychart
import tkinter.messagebox
import serial


#g_pressure_too_high = False # the pressures.Pressure1 sets these to True from time to time if regulation is required;
#g_pressure_too_low = False  # the regulator should act and then reset those to False.
g_pressure_regulate = 0 # 1 request regulation up, -1 down
g_pressure_S2 = 1000.0 # in mbar, as returned by ReqPar

the_app = None
the_usb_socket = None


class Anitem():
    def __init__(self):
        self.the_box:tki.LabelFrame 
        self.the_name = ''
        self.chb_enabled: tki.Checkbutton
        self.enabled = True
        self.thread: threading.Thread
        self.time_to_get_ms = 0
        #self.last_ret = []
        self.is_master = True
        # FAILED attempt to get rid of warnings:
        self.the_checkbuttons = []
        self.the_probes = []
        self.slave = None
        self.fancy_pos = []
        self.on_change_ctrl_proc = None
        self.current = -1.0
        #self.var_current = None no, no point, warning just changes, AND i use 'if hasattr var_current', so NO
        #self.var_filament = None no, no point, warning just changes, AND i use 'if hasattr var_filament', so NO
        '''self.var_current: tki.StringVar|None = None
        self.var_filament = None
        self.on_filamentReturn = None'''
    def get_data(self):
        pass
    def update_ui(self):
        pass
    def on_destroy(self):
        pass
    def switchOff(self):
        pass
    def on_currentReturn(self, _ev):
        pass
    def on_filamentReturn(self, _ev):
        pass
    #def switchOff(self):
    #    pass

def connect_socket(address, port, description):
    the_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    #print('connecting ' + description + ' socket...')
    the_socket.settimeout(1)
    try:
        the_socket.connect((address[0], address[1]+port))
        #print(description + ' socket connected.')
        ok = True
    except TimeoutError: # this happens only if server is not there; if the device is off/not responding, socket still connects ok...
        print('TIMEOUT when connecting ' + description + ' socket!')
        ok = False
    except ConnectionRefusedError: # this happens when a device is connected to another window
        print('CONN REGF')
        tkinter.messagebox.showerror('CRITICAL FAIL', 'Connection to '+description+' REFUSED!\nIs there another connection to '+description+' open?\nClose the other connection to '+description+' and try again.' )
        ok = False
        raise
    except Exception as ex:
        print(description + 'socket connect EXCEPTION!', ex)
        ok = False
        #raise
    return (the_socket, ok)

PRINT_TIMES = 0 # 0 1 2 3
def send_socket_message(sock, msg, lock = None, term='\n'):
    if PRINT_TIMES>0: t0 = time.time()
    #print('wtf', msg)
    if not lock is None:
        lock.acquire()
    #print('wtf2', msg)
    leftovers = None
    r = bytes()
    try:
        # sometimes there is a leftover text from another message? check:
        while select.select([sock,],[],[], 0.0)[0]:
            print('=================!!!!!===LEFTOVERS:===', msg)
            leftovers = sock.recv(256)
            print(leftovers)
            if leftovers == b'': # dead socket, have to recreate it
                #print('after blank leftovers 0')
                break
        if PRINT_TIMES>2: print('1:', ((time.time()-t0)*1000), 'ms')
        #if msg != 'get':
        #print('sending:  ', msg)
        sock.sendall(bytes(msg+term, 'utf-8'))
        if PRINT_TIMES>2: print('2:', ((time.time()-t0)*1000), 'ms')
        #time.sleep(0.1)
        #if select.select([sock,],[],[], 0.0)[0]: sanity check
        #    print('yes, there is response')
        while True:
            r += sock.recv(256)
            if PRINT_TIMES>1: print('3:', ((time.time()-t0)*1000), 'ms')
            if b'\n' in r:
                break
            #else: print('>>>>>>>>>>')
        resp = str(r, 'utf-8').strip()
        #print('received: ', resp)
        #print(resp)
    except TimeoutError:
        #print('TIMEOUT')
        resp = 'timeout'
        if len(r) > 0:
            print(r)
    except Exception:
        #print(ex)
        resp = 'dead_socket'
    #print('wtf3', msg)
    if not lock is None:
        lock.release()
    if PRINT_TIMES>0: print('4:', ((time.time()-t0)*1000), 'ms')

    return resp

    

PRINT_TIMES_A = 0 # 0 1 2 3
def send_socket_message_array(sock, msg, lock = None, bytecnt=200):
    if PRINT_TIMES_A>0: t0 = time.time()
    if not lock is None:
        lock.acquire()
    # sometimes there is a leftover text from another message? check:
    while select.select([sock,],[],[], 0.0)[0]:
        print('=================!!!!!===LEFTOVERS:===')
        leftovers = sock.recv(256)
        print(leftovers)
        if leftovers == b'': # dead socket, have to recreate it
            #print('after blank leftovers 0')
            break
    if PRINT_TIMES_A>2: print('1:', ((time.time()-t0)*1000), 'ms')
    #if msg != 'get':
    #print('sending:  ', msg)
    try:
        sock.sendall(bytes(msg+'\n', 'utf-8'))
        if PRINT_TIMES_A>2: print('2:', ((time.time()-t0)*1000), 'ms')
        r = bytes()
        toreceive = bytecnt
        while toreceive > 0:
            r += sock.recv(toreceive)
            if PRINT_TIMES_A>1: print('3:', ((time.time()-t0)*1000), 'ms')
            #print('received len:', len(r))
            toreceive = bytecnt - len(r)
        resp = array.array('h', r)
        #print('received: array:', resp)
        #print(resp)
    except TimeoutError:
        #print('TIMEOUT')
        resp = array.array('h', [-1])
    except Exception:
        #print(ex)
        resp = array.array('h', [])
    if not lock is None:
        lock.release()
    if PRINT_TIMES_A>0: print('4:', ((time.time()-t0)*1000), 'ms')

    return resp



class MySocket():
    def __init__(self, address, port, description):
        self._address, self._port, self._description = (address, port, description)
        self._lock = threading.Lock()
        self._socket, self.connected = connect_socket(address, port, description)
        
    def send_message(self, msg, term='\n'):
        ret = send_socket_message(self._socket, msg, self._lock, term)
        self.connected = ret != 'timeout'
        if ret == 'dead_socket':
            print('DEAD SOCKET, recreating for ', self._description)
            self._socket.close()
            self._socket, self.connected = connect_socket(self._address, self._port, self._description)            
        return ret

    def send_message_array(self, msg, bytecnt=200):
        ret = send_socket_message_array(self._socket, msg, self._lock, bytecnt)
        self.connected = len(ret) == bytecnt
        if len(ret) == 0:
            print('DEAD SOCKET, recreating for ', self._description)
            self._socket.close()
            self._socket, self.connected = connect_socket(self._address, self._port, self._description)            
        return ret
        
    def close(self):
        self._socket.close()
        
        
        
class MySerial():
    def __init__(self, _description=''):
        self.connected = False
        self._lock = threading.Lock()
        self.connect()
        
    def connect(self):
        if self.connected: # connect only if not connected
            return True
        for i in range(10):  # just connect to the first (and hopefully only) available serial thing
            try:
                self._serial = serial.Serial("/dev/ttyACM"+str(i), 115200, timeout=2)
                global the_usb_socket
                the_usb_socket = self
                self.connected = True
                print('connected to ttyACM'+str(i))
                self._serial.reset_input_buffer() # discard any stuff in the input buffer??
                break
            except Exception as ex:
                print(i, 'ttyACM failed,', ex)
        return self.connected
                
    def send_message(self, msg):
        if not self.connect():
            return ''
        self._lock.acquire()
        self._serial.write(bytes(msg, 'utf-8')+b"\n")
        self._serial.flush() # wait until all is written
        ok = False
        for _ in range(120): 
            if self._serial.in_waiting > 0:
                ok = True
                break
            time.sleep(0.001)
        if ok:
            ret = self._serial.readline()
            #print(ret)
            ret = str(ret, 'utf-8').strip()
            #print(msg, ret)
        else:
            print(msg, ": no response on serial, waiting...")
            self.connected = False
            ret = ''
        self._lock.release()
        return ret        
        
    def send_message_array(self, msg, bytecnt=200):
        if not self.connect():
            return array.array('h', [-1])
        self._lock.acquire()
        if self._serial.in_waiting > 0: # no, doesnt happen
            print('Data already available?? HELP!', self._serial.in_waiting)
            time.sleep(0.2)
            print(self._serial.read())
            self._serial.reset_input_buffer()
        self._serial.write(bytes(msg, 'utf-8')+b"\n")
        self._serial.flush() # wait until all is written
        ok = False
        for _ in range(120): 
            if self._serial.in_waiting > 0:
                ok = True
                break
            time.sleep(0.001)
        if ok:
            #time.sleep(2)
            #print(self._serial.read(self._serial.in_waiting))
            ret = self._serial.read(bytecnt)
            ret = array.array('h', ret)
            #print(msg, ret)
            time.sleep(0.001)
            if self._serial.in_waiting > 0:
                print('More data coming?? HELP!', self._serial.in_waiting)
                time.sleep(0.2)
                print(self._serial.read(self._serial.in_waiting))
                self._serial.reset_input_buffer()
        else:
            print("no response on serial, waiting...")
            self.connected = False
            ret = array.array('h', [-1])
        self._lock.release()
        return ret        
    
    def close(self):
        self._serial.close()
    
    
class MySerialRemote():
    def __init__(self, _description=''):
        if the_usb_socket is None:
            return
        self._usb = the_usb_socket
        self.connected = self._usb.connected
        
    def send_message(self, msg):
        if the_usb_socket is None:
            return ''
        if not self._usb.connected:
            self.connected = False
            return 'tester device not connected'
        ret = self._usb.send_message('uart '+msg)
        self.connected = self._usb.connected
        return ret
    
    def send_message_array(self, msg, bytecnt=200):
        if the_usb_socket is None:
            return ''
        if not self._usb.connected:
            self.connected = False
            return 'tester device not connected'
        ret = self._usb.send_message_array('uart '+msg, bytecnt)
        self.connected = self._usb.connected
        return ret 

    def close(self):
        pass
    

def SocketOrSerial(address, port=0, description=''):
    if isinstance(address, str):
        if address == 'usb':
            return MySerial(description)
    if isinstance(address, tuple):
        return MySocket(address, port, description)
    if address == 'rem':
        return MySerialRemote(description)
    return None



def getDBValue(id):
    r = subprocess.getoutput("timeout 1 ssh csoperator@192.168.2.1 'echo \"" + id + "\" |ReqParP --fmt e 2>/dev/null'")
    # timeout 1 ssh csoperator@192.168.2.1 'echo "CCG S1-1|PR\n" |ReqParP --fmt e'
    #print (r)
    try:
        return [float(v.split('|')[-1]) for v in r.split('\n')]
    except:
        print(time.strftime('%H:%M:%S  '), r)
        cnt = len(id.split('|')) - 1
        return [-1.0 for _ in range(cnt)]
        
        
        
        
        

class ABar():
    def __init__(self, canvas, x=2, y=48, width=164, height=13, minmax=(0.0, 1.0, 2.0), twobars=False, name=''):
        self.canvas = canvas
        self.minmax = minmax
        self.bar_name = name
        self.rect = r = (x, y, x+width, y+height)
        canvas.create_rectangle(r[0]-1, r[1]-1, r[2], r[3], fill='', outline='black')                   # outline: (1,1,width,h) to fill canvas and be visible
        if twobars:
            self.bar_ma = canvas.create_rectangle(*r, fill='#ff00ff', outline='') # fill: (2,2,width,h) to fill the outline without covering it
            self.ma_px = r[2]
        else:
            self.bar_ma = None
        self.bar_mi = canvas.create_rectangle(*r, fill='#44cc44', outline='') # fill: (2,2,width,h) to fill the outline without covering it
        self.mi_px = r[2]
        self.bartxt = canvas.create_text(r[0]+1, r[1]-1, text='NOT CONNECTED', anchor='nw')
        self.text = 'NOT CONNECTED'
        self.clr = '#44cc44'
        if hasattr(self.canvas, 'abars'):
            self.canvas.abars.append(self)
        else:
            self.canvas.abars = [self]
            self.canvas.bind('<Button-3>', self.on_rclick_canvas)
        #print(the_app.chart)
        the_app.the_bars.append(self) # type: ignore


    def update(self, v, v2=0, txt='', bad=False):
        (miok, maok, ma) = self.minmax
        (a, b, c, d) = self.rect
        if self.bar_ma is None:
            v2 = v
        else:
            px = round(a+(c-a)*v2/ma)
            if px != self.ma_px:
                self.canvas.coords(self.bar_ma, a, b, px, d)
                self.ma_px = px
        px = c if bad else round(a+(c-a)*v/ma)
        if px != self.mi_px:
            self.canvas.coords(self.bar_mi, a, b, px, d)
            self.mi_px = px
        clr = '#ff8888' if (v<miok or v2>maok or bad) else '#44cc44'
        #print(minmax, v, v2)
        if clr != self.clr:
            self.canvas.itemconfigure(self.bar_mi, fill=clr)
            self.clr = clr
        if txt != self.text:
            self.canvas.itemconfigure(self.bartxt, text=txt)
            self.text = txt
            
    def update_marks(self):
        self.canvas.delete('y'+str(self.rect[1]))
        self.add_marks([self.minmax[0], self.minmax[1]], [])

    def add_marks(self, major, minor):
        x1, y1, x2, _ = self.rect
        a = (x2-x1)/self.minmax[2]
        for k in major:
            self.canvas.create_line(k*a+x1, y1, k*a+x1, y1+6, tags='y'+str(self.rect[1]))
        for k in minor:
            self.canvas.create_line(k*a+x1, y1, k*a+x1, y1+3, tags='y'+str(self.rect[1]))
            
    def on_rclick_canvas(self, ev):
        bar = None
        for abar in self.canvas.abars:
            if ev.y > abar.rect[1] and ev.y < abar.rect[3]:
                bar = abar
                break
        if bar is None:
            return
        print(bar.minmax)
        toplevel = tki.Toplevel()
        toplevel.geometry('208x200')
        toplevel.transient(self.canvas.winfo_toplevel())
        lbl=tki.Label(toplevel, text=bar.bar_name)
        lbl.place(x=4, y=10)
        lbl=tki.Label(toplevel, text='min value: 0')
        lbl.place(x=4, y=40)
        lbl=tki.Label(toplevel, text='min ok value:')
        lbl.place(x=4, y=70)
        lbl=tki.Label(toplevel, text='max ok value:')
        lbl.place(x=4, y=100)
        lbl=tki.Label(toplevel, text='max value:')
        lbl.place(x=4, y=130)
        var_miok = tki.StringVar()
        var_miok.set(str( bar.minmax[0] ))
        txt_miok = tki.Entry(master=toplevel, textvariable=var_miok)
        txt_miok.place(x=100, y=68, width=100)
        var_maok = tki.StringVar()
        var_maok.set(str( bar.minmax[1] ))
        txt_maok = tki.Entry(master=toplevel, textvariable=var_maok)
        txt_maok.place(x=100, y=98, width=100)
        var_ma = tki.StringVar()
        var_ma.set(str( bar.minmax[2] ))
        txt_ma = tki.Entry(master=toplevel, textvariable=var_ma)
        txt_ma.place(x=100, y=128, width=100)
        def cmd_change(_ev):
            bar.minmax = (float(var_miok.get()), float(var_maok.get()), float(var_ma.get()))
            bar.update_marks()
            the_app.save_minmax() # type: ignore
        def cmd_ok():
            cmd_change(None)
            toplevel.destroy()
        #txt_mi.bind('<Return>', cmd_change)
        #txt_mi.bind('<KP_Enter>', cmd_change)
        #txt_ma.bind('<Return>', cmd_change)
        #txt_ma.bind('<KP_Enter>', cmd_change)
        btn = tki.Button(toplevel, text='Ok', command=cmd_ok)
        btn.place(x=50, y=164)

    
'''class ATextWrapper():
    def __init__(self, item):
        self.item = item
        self.text = item.cget('text')    

    def configure(self, text):
        if self.text != text:
            self.item.configure(text=text)
            self.text = text
            self.item._orig_text = self.text'''

# pylint: disable=protected-access
def change_text(item, text):
    if item._orig_text != text:
        item.configure(text=text)
        item._orig_text = text
        
# pylint: disable=protected-access        
def set_text(item):
    item._orig_text = item.cget('text')
    
    
    
    

class FilamentRamper():
    def __init__(self, box, targetA, rate, ctrl_var, dependent_var, ctrl_var_ui):
        # === ramp filament: ===
        self.btn_ramp_up = tki.Button(master=box, text='Ramp...', command=self.ramp_up)
        self.btn_ramp_up.place(x=220, y=5, height=24)
        self.ramping = False
        self.ramp_target = targetA
        self.ramp_rate = rate # A/min
        self.ramp_stop_flag = False
        self.default_color = box.winfo_toplevel().cget('bg')
        self.ramp_list_x = []
        self.ramp_list_y = []
        self.ramp_window_visible = False
        self.ctrl_var = ctrl_var
        self.dependent_var = dependent_var
        self.ctrl_var_ui = ctrl_var_ui
        
    def ramp_stop(self, destroying=False):
        self.btn_ramp_up.configure(text='Ramp...')
        self.btn_ramp_up.configure(bg=self.default_color)
        self.btn_ramp_up.configure(activebackground='white')
        if not destroying:
            self.btn_ramp_up_2.configure(text='\u25b6 Ramp')
            self.btn_ramp_up_2.configure(bg=self.default_color)
            self.btn_ramp_up_2.configure(activebackground='white')
            self.txt_rampTarget.configure(state='normal')
            self.txt_rampRate.configure(state='normal')
            self.txt_pressure_limit.configure(state='normal')
        self.ramping = False
        self.ramp_stop_flag = False
        
    def ramp_up(self):
        if not self.ramp_window_visible:
            toplevel = tki.Toplevel()
            toplevel.geometry('300x300')
            #toplevel.attributes('-topmost', True) # does nothing
            toplevel.transient(self.btn_ramp_up.winfo_toplevel())
            lbl=tki.Label(toplevel, text='Ramp to           A, rate         A/min')
            lbl.place(x=4, y=10)
            var_rampTarget = tki.StringVar()
            var_rampTarget.set(str(round(self.ramp_target)))
            self.txt_rampTarget = tki.Entry(master=toplevel, textvariable=var_rampTarget)
            self.txt_rampTarget.place(x=64, y=8, width=35)
            var_rampRate = tki.StringVar()
            var_rampRate.set(str(self.ramp_rate))
            self.txt_rampRate = tki.Entry(master=toplevel, textvariable=var_rampRate)
            self.txt_rampRate.place(x=150, y=8, width=27)
            
            self.lbl_pressure_limit = tki.Label(master=toplevel, text='p limit:')
            self.lbl_pressure_limit.place(x=4, y=35)
            var_pressure_limit = tki.StringVar()
            var_pressure_limit.set('1e-6')
            self.txt_pressure_limit = tki.Entry(master=toplevel, textvariable=var_pressure_limit)
            self.txt_pressure_limit.place(x=54, y=34, width=60)
            lbl = tki.Label(master=toplevel, text='mbar')
            lbl.place(x=108, y=35)
            
            self.ramp_list_x = []
            self.ramp_list_y = []
            def cmd_cancel(_ev=None):
                self.ramp_stop(destroying=True)
                self.ramp_window_visible = False
                #toplevel.destroy()
            def cmd_start():
                if not self.ramping:
                    self.ramp_target = float(var_rampTarget.get())
                    self.ramp_rate = float(var_rampRate.get())
                    self.ramp_pressure_limit = float(var_pressure_limit.get())
                    self.txt_rampTarget.configure(state='disabled')
                    self.txt_rampRate.configure(state='disabled')
                    self.txt_pressure_limit.configure(state='disabled')
                    self.btn_ramp_up.configure(text='\u25a0 Stop')
                    self.btn_ramp_up.configure(bg='orange')
                    self.btn_ramp_up.configure(activebackground='yellow')
                    self.btn_ramp_up_2.configure(text='\u25a0 Stop')
                    self.btn_ramp_up_2.configure(bg='orange')
                    self.btn_ramp_up_2.configure(activebackground='yellow')
                    self.ramp_time = time.time()
                    self.ramp_stop_flag = False
                    self.ramping = True
                else:
                    self.ramp_stop()
            #btn = tki.Button(toplevel, text='Cancel', command=toplevel.destroy)
            #btn.place(x=40, y=34)
            self.btn_ramp_up_2 = tki.Button(toplevel, text='\u25b6 Ramp', command=cmd_start)
            self.btn_ramp_up_2.place(x=160, y=34, height=24)
            self.ramp_chart = mychart.Chart(toplevel, 300, 300-60, 'Filament ctrl')
            self.ramp_chart.place(x=0, y=60)
            toplevel.bind('<Destroy>', cmd_cancel)
            self.ramp_window_visible = True
        else:
            self.ramp_stop()
        
        
    def on_get_data(self):
        ctrl_val = self.ctrl_var()
        if self.ramping:
            t = time.time()
            dt = t - self.ramp_time
            self.ramp_time = t
            if g_pressure_S2 > self.ramp_pressure_limit:
                print('pressure too high, ', g_pressure_S2,', waiting with the ramp...')
            else:
                try:
                    # A = s * A/min / s/min
                    dA = dt*self.ramp_rate/60
                    
                    if ctrl_val > self.ramp_target:
                        c = max(self.ramp_target, ctrl_val-dA)
                    else:                    
                        c = min(self.ramp_target, ctrl_val+dA)
                    self.ctrl_var(c)
                    print('A ->', c)
                    if c == self.ramp_target:
                        self.ramp_stop_flag = True
                except:
                    print('==== exception when ramping up ====')
        if self.ramp_window_visible:
            self.ramp_list_x.append(ctrl_val)
            self.ramp_list_y.append(self.dependent_var())

    def on_update_ui(self):
        if self.ramping:
            self.ctrl_var_ui.set('{:.2f}'.format(self.ctrl_var()))
            if g_pressure_S2 > self.ramp_pressure_limit:
                self.lbl_pressure_limit.configure(bg='orange')
            else:
                self.lbl_pressure_limit.configure(bg=self.default_color)
                
        if self.ramp_window_visible:
            self.ramp_chart.draw(self.ramp_list_x, [self.ramp_list_y])
        if self.ramp_stop_flag:
            self.ramp_up()


class FilamentLifetimeTracker():
    def __init__(self, menu, targetA, filename):
        self.menu = menu
        self.threshouldA = targetA/2 # filament considered 'on' if its current is half of its working current
        #self.A_var = ctrl_var     # function that returns the filament's current
        self.filename = filename 
        self.menu.add_separator()
        self.menu.add_command(label='Filament life time: ?? h', command=self.reset_lifetime)
        self.menu_ind = self.menu.index('end')
        
        self.lifetime     = 0.0 # lifetimetime in s
        self.lifetime_old = 0.0 # previously saved lifetime
        self.last_check   = time.time() # last time lifetime_old was updated, as returned by time.time()
        self.on       = 0 # 0 was off, 1 was on
        self.previous_lifetimes_list = []
        
        try:
            f = open(filename, 'r', encoding='utf-8')
            t = f.read()
            f.close()
            tt = t.split('\n')
            self.previous_lifetimes_list = tt[3:]
            self.lifetime_old = float(tt[0])
            self.last_check   = float(tt[1])
            self.on       = int(tt[2])
            self.lifetime = self.lifetime_old
        except Exception as ex:
            print('bad or no filament lifetime file', ex)
            
            
    def update(self, A): # call this every time there is a value of filament current A
        was_on = self.on
        self.on = A > self.threshouldA
        if self.on and was_on:
            time_since_last_check = time.time() - self.last_check
            self.lifetime = self.lifetime_old + time_since_last_check
            if time_since_last_check > 15*60:
                self.savefile()
        if self.on != was_on:
            self.savefile()
 
    def show_lifetime(self):
        self.menu.entryconfig(self.menu_ind, label='Filament life time: {:.1f} h'.format(self.lifetime/3600)+', now '+('ON' if self.on else 'off'))

    def savefile(self):
        self.last_check = time.time()
        self.lifetime_old = self.lifetime
        print('Saving filament lifetime file...')
        try:
            f = open(self.filename, 'w', encoding='utf-8')
            f.write(str(self.lifetime_old)+'\n'+str(self.last_check)+'\n'+('1' if self.on else '0'))
            for p in self.previous_lifetimes_list:
                f.write('\n'+p)
            f.close()
        except Exception as ex:
            print('Exception when saving lifetime file', ex)
        
    def reset_lifetime(self):
        if tkinter.messagebox.askokcancel('Filament', 'Reset lifetime to zero?'):
            self.previous_lifetimes_list.append(
                datetime.datetime.now().strftime('%Y-%m-%d ') + '{:.1f} h'.format(self.lifetime/3600))
            self.lifetime = 0
            self.savefile()
    

# nah, use common.g_pressure_too_low/high that are updated by pressures.Pressure1
'''class GasRegulator():
    def __init__(self, box, y_pos=31, target_min_max=(2.9, 3.0)):
        self.target_min_max = target_min_max
        
        self.var_regulate = tki.IntVar()
        self.var_regulate.set(0)
        chb = tki.Checkbutton(master=box, variable=self.var_regulate, text='Regulate:', command=self.on_click_regulate)
        chb.place(x=37, y=y_pos)
        
        self.var_min = tki.StringVar()
        self.var_min.set(str(target_min_max[0]))
        self.var_min.trace_add('write', self.on_click_regulate)
        self.txt_min = tki.Entry(master=box, textvariable=self.var_min)
        self.txt_min.place(x=124, y=y_pos, width=35)
        
        self.var_max = tki.StringVar()
        self.var_max.set(str(target_min_max[1]))
        self.var_max.trace_add('write', self.on_click_regulate)
        self.txt_max = tki.Entry(master=box, textvariable=self.var_max)
        self.txt_max.place(x=124+35+10, y=y_pos, width=35)
        
        tki.Label(box, text='-').place(x=124+35+2, y=y_pos)
        tki.Label(box, text='e-6 mbar').place(x=124+2*35+10+2, y=y_pos)

        self.regulate = False
        self.last_regulation_time = time.time()

    def on_click_regulate(self, _v=None, _b=None, _c=None):
        self.regulate = self.var_regulate.get()
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
        
    def get(self):
        ret = 0
        if self.regulate and time.time()-self.last_regulation_time>20:
            self.last_regulation_time = time.time()
            p = g_pressure_S2*1e6
            if p < self.target_min_max[0]: ret = 1
            if p > self.target_min_max[1]: ret =-1
            if ret != 0:
                print('Regulating pressure:', 'inc' if ret>0 else 'dec')
        return ret
 '''       
