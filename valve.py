import tkinter as tki
#import threading
#import time

import common



class Valve():
    def __init__(self, box, _box2, term_serv_addr, port, _aname=('valve', 'valve')):
        box.place(height=82)
        #self.the_name = aname
        self.chb_valvePosRead = tki.Checkbutton(master=box, text='pos = ??')
        self.chb_valvePosRead.place(x=2, y=4)
        common.set_text(self.chb_valvePosRead)

        self.lbl_gasOnRead = tki.Label(master=box, text='???', bg='orange')
        self.lbl_gasOnRead.place(x=120, y=-16, width=166, height=15)

        btn = tki.Button(master=box, text='+1', command=lambda: self.moveValve(1))
        btn.place(x=100, y=0, width=40, height=16)
        btn = tki.Button(master=box, text='+10', command=lambda: self.moveValve(10))
        btn.place(x=141, y=0, width=40, height=16)
        btn = tki.Button(master=box, text='+100', command=lambda: self.moveValve(100))
        btn.place(x=182, y=0, width=40, height=16)
        btn = tki.Button(master=box, text='-1', command=lambda: self.moveValve(-1))
        btn.place(x=100, y=17, width=40, height=16)
        btn = tki.Button(master=box, text='-10', command=lambda: self.moveValve(-10))
        btn.place(x=141, y=17, width=40, height=16)
        btn = tki.Button(master=box, text='-100', command=lambda: self.moveValve(-100))
        btn.place(x=182, y=17, width=40, height=16)

        '''self.btn_gasOnOff = tki.Button(master=box, text='Gas ???', command=self.gas_toggle)
        self.btn_gasOnOff.place(x=230, y=0)
        self.default_color = self.btn_gasOnOff.cget('bg')'''
        
        self.btn_gas_on = tki.Button(master=box, text='On', command=self.gas_on)
        self.btn_gas_on.place(x=230, y=2, width=30, height=28)

        self.btn_gas_off = tki.Button(master=box, text='Turn off', command=self.gas_off)
        self.btn_gas_off.place(x=280, y=2, width=63, height=28)
        
        #self.var_regulate = tki.IntVar()
        #self.var_regulate.set(0)
        #chb = tki.Checkbutton(master=box, variable=self.var_regulate, text='Regulate S2 pressure', command=self.on_regulate)
        #chb.place(x=100, y=35)
        #self.regulate = False
        #self.last_regulation_time = time.time()

        self.the_checkbuttons = [self.chb_valvePosRead]
        
        self.the_socket = common.MySocket(term_serv_addr, port, 'valve')
        self.pos = -1.0
        if self.the_socket.connected:
            self.gas = self.the_socket.send_message('getGasOnOff')
        else:
            self.gas = '???'
        print('gas is ', self.gas)
        self.gas_update_flag = True
        self.want_gas = False
        
        self.restarted_count = 0
        self.comfails_count = 0

        self.lbl_restarts = tki.Label(master=box, text='rs: 0', font=('', 8))
        self.lbl_restarts.place(x=290, y=30)
        self.lbl_restarts.bind("<ButtonRelease-3>", self.clear_fails)
        self.lbl_comfails = tki.Label(master=box, text='cf: 0', font=('', 8))
        self.lbl_comfails.place(x=290, y=42)
        self.lbl_comfails.bind("<ButtonRelease-3>", self.clear_fails)
        self.fail_count = 0
        
        self.last_names = ['gas', 'on', 'pos']
        
        #self.gas_regulator = common.GasRegulator(box, 34, (2.95, 3.05))
        
        self.updateGasButton()
        #common.send_message(self.the_socket, 'setMin 0.0', self.the_lock)
        #common.send_message(self.the_socket, 'setMax 10.0', self.the_lock)
        
        
    def clear_fails(self, _ev):
        self.restarted_count = 0
        self.comfails_count = 0
        
    #def on_regulate(self):
    #    self.regulate = self.var_regulate.get()
    #    print(self.regulate)
        
    def updateGasButton(self):
        if not self.gas_update_flag:
            return
        #ret = common.send_message(self.the_socket, 'getGasOnOff', self.the_lock)
        self.gas_update_flag = False
        if self.gas == 'off':
            '''self.btn_gasOnOff.config(relief='raised')
            self.btn_gasOnOff.config(text='Gas is OFF')
            self.btn_gasOnOff.config(bg='orange') #self.default_color)'''
            self.lbl_gasOnRead.config(text='Gas is OFF')
            self.lbl_gasOnRead.config(bg='orange')
        elif self.gas == 'on':
            '''self.btn_gasOnOff.config(relief='sunken')
            self.btn_gasOnOff.config(text='Gas is ON')
            self.btn_gasOnOff.config(bg='#44cc44')'''
            self.lbl_gasOnRead.config(text='Gas is ON')
            self.lbl_gasOnRead.config(bg='#44cc44')            
        else:
            '''self.btn_gasOnOff.config(text=self.gas)
            self.btn_gasOnOff.config(bg='orange')'''
            self.lbl_gasOnRead.config(text=self.gas)
            self.lbl_gasOnRead.config(bg='orange')

        
        
        
    def moveValve(self, d):
        print('-->', d)
        ret = self.the_socket.send_message('moveDeltaSteps '+str(d))
        print(ret)
        
    '''def gas_toggle(self):
        self.gas_update_flag = True
        self.gas = common.send_message(self.the_socket, 'getGasOnOff', self.the_lock)
        if self.gas == 'on':
            ret2 = common.send_message(self.the_socket, 'gasOff', self.the_lock)
            self.gas = 'off' if ret2 == 'ok' else ret2
        elif self.gas == 'off':
            ret2 = common.send_message(self.the_socket, 'gasOn', self.the_lock)
            self.gas = 'on' if ret2 == 'ok' else ret2
        self.updateGasButton()'''
        
    def gas_on(self):
        self.gas_update_flag = True
        ret = self.the_socket.send_message('gasOn')
        self.gas = 'on' if ret == 'ok' else ret
        self.want_gas = True
        self.updateGasButton()

    def gas_off(self):
        self.gas_update_flag = True
        ret = self.the_socket.send_message('gasOff')
        self.gas = 'off' if ret == 'ok' else ret
        self.want_gas = False
        self.updateGasButton()

    def switchOff(self):
        self.gas_off()

    def on_destroy(self):
        self.the_socket.close()
        print('valve socket closed.')


    def get_data(self):
        #t0 = time.time()
        v = -1.0
        gas = '???'
        ret = self.the_socket.send_message('get')
        #print('sendsockmess:', round((time.time()-t0)*1000), 'ms')
        if ret != 'timeout':
            ret = ret.split()
            try:
                v = float(ret[0])
                if len(ret) > 1:
                    gas = ret[1]
                if len(ret) > 2:
                    if ret[2] == '1':
                        self.restarted_count += 1
                        self.the_socket.send_message('ok')
                        print('Gas controller was restarted')
                        if self.want_gas:
                            self.the_socket.send_message('gasOn')
                            print('Since gas was needed, gas was switched back on...')

            except:
                print('valve exc:', ret)
        if gas == '???':
            self.comfails_count += 1
        self.pos = v
        if self.gas != gas:
            print('Gas changed...')
            self.gas = gas
            self.gas_update_flag = True
            
        #reg = self.gas_regulator.get()
        if common.g_pressure_regulate != 0 and self.gas == 'on' and v>5 and v<6:
            print('Regulating pressure', common.g_pressure_regulate)
            self.moveValve(5*common.g_pressure_regulate)
            common.g_pressure_regulate = 0
        
        #print('get tot:', round((time.time()-t0)*1000), 'ms')
        self.last_ret = [v,]
        self.last_ctrl = [1.0 if self.gas == 'on' else 0.0]
        
        
    def update_ui(self):
        common.change_text(self.chb_valvePosRead, 'pos = {:.2f}'.format(self.pos))
        self.updateGasButton()
        if self.fail_count != self.restarted_count + self.comfails_count:
            self.lbl_restarts.configure(text='rs: '+str(self.restarted_count))
            self.lbl_comfails.configure(text='cf: '+str(self.comfails_count))
            self.fail_count = self.restarted_count + self.comfails_count

    '''def on_timer(self):
        v = -1.0
        ret = common.send_message(self.the_socket, 'getPos')
        try:
            v = float(ret)
        except:
            print(ret)
        self.chb_valvePosRead.configure(text='pos = {:.2f}'.format(v))
        return [v,]'''


