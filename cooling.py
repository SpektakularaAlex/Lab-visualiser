import tkinter as tki
from tkinter.ttk import Frame
import socket
import select
import mychart
#import subprocess
import time

#from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
#from matplotlib.figure import Figure


TERM_SERV_ADDR = '192.168.2.200' #'192.168.2.7'
THE_PORTS = [7031,]
THE_TITLES= ['LE-2']
UPDATE_PERIOD_MS = 2000
MAX_PTS_PER_GRAPH = 436
AVG_PTS = 350 # perhaps 336 pts per line in the chart, 7 days maybe,
             # 48 pts per day, 2 pts per hour, 1800 s, 2 s per update,
             # 900 updates per pt
S_PER_TIMEUNIT = 3600



def send_message(sock, msg):
    # sometimes there is a leftover text from another message? check:
    while select.select([sock,],[],[], 0.0)[0]:
        print('=================!!!!!===LEFTOVERS:===')
        print(sock.recv(256))
    try:
        sock.sendall(bytes(msg+'\n', 'utf-8'))
        r = bytes()
        while True:
            r += sock.recv(256)
            if b'\n' in r:
                break
        resp = str(r, 'utf-8').strip()
    except TimeoutError:
        print('TIMEOUT')
        resp = 'timeout'
    return resp
    

def connect(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print('connecting', port)
    sock.settimeout(2)
    try:
        sock.connect((TERM_SERV_ADDR, 3000+port))
        print('the socket connected.', port)
    except TimeoutError:
        print('TIMEOUT')
    except:
        print('socket connect exception!', port)
        raise 
    return sock


class Board():
    def __init__(self, master, port, title, ind):
        self.lbl_status = tki.Label(master=master, text='????')
        self.lbl_status.place(x=6, y=4+ind*20)
        self.data_T: list[float] = []
        self.data_L: list[float] = []
        self.avg_T = 0.0
        self.avg_L = 0.0        
        self.socket = connect(port)
        self.title = title
        self.last_T = 0.0
        self.last_L = 0.0

    def read_from_sock(self, cnt):
        status = '??'
        ret = send_message(self.socket, 'get')
        print(self.title, ret)    
        
        ar = ret.split('\t')
        if len(ar)==4:
            try:
                self.last_T = float(ar[0])
                self.last_L = float(ar[1])
                status = ar[3]
            except:
                print(ar, 'is not a number, or sth else')
        else:
            print(ar, 'WRONG NUMBER OF ITEMS')
        
        level = 170 - self.last_L
        
        self.lbl_status.configure(text=self.title+':   {:.2f} oC, \t{:.0f} mm, \t'.format(self.last_T, level)+status)

        if cnt == 1:
            self.avg_T = self.last_T
            self.avg_L = level
            self.data_T.append(self.last_T)
            self.data_L.append(level)
        else:
            self.avg_T += self.last_T
            self.avg_L += level                    
            self.data_T[-1] = self.avg_T/cnt
            self.data_L[-1] = self.avg_L/cnt
        
        if len(self.data_T)>MAX_PTS_PER_GRAPH:
            self.data_T.pop(0)
        if len(self.data_L)>MAX_PTS_PER_GRAPH:
            self.data_L.pop(0)

            

class Cooling(Frame):
    def __init__(self):
        super().__init__()
        self.group = tki.LabelFrame(master=self.master, text='Cooling')
        self.group.place(x=4, y=4, width=350-8, height=102)
        self.the_boards = []
        for i in range(len(THE_PORTS)):
            self.the_boards.append(Board(self.group, THE_PORTS[i], THE_TITLES[i], i))
        
        self.chart = mychart.Chart(self.master, 350, 350)
        self.chart.place(x=0, y=106)
        self.chart2= mychart.Chart(self.master, 350, 350)
        self.chart2.place(x=0, y=106+350)
        self.chart.draw([212e-4, 222e-4, 232e-4, 242e-4, 252e-4], [[2, 4, 6, 8, 16], [1, 3, 5, 7, 9]])
        self.data_x = []
        #self.data_T: list[list[float]] = []
        #self.data_L: list[list[float]] = []
        self.data_T = [b.data_T for b in self.the_boards]
        self.data_L = [b.data_L for b in self.the_boards]
            
        self.avg_cnt = 0
        #self.avg_T: list[float] = [0 for _ in self.the_sockets]
        #self.avg_L: list[float] = [0 for _ in self.the_sockets]
        self.avg_x = 0.0
        self.last_time = 0.0

        #print(getDBValue('CCG S2-1|PR'))
        #self.sendMessage(self.filamentSocket, 'setV 0')

        self.master.bind('<Destroy>', self.on_destroy)
        self.timer_id = None
        self.on_timer()
        
    

    def on_destroy(self, _event):
        # this is called many times though (for each entry?)
        #print('stopping...', self.timer_id)
        if not (self.timer_id is None):
            self.master.after_cancel(self.timer_id)
            self.timer_id = None
            for b in self.the_boards:
                b.socket.close()
            print('Timer deleted.')


    def on_timer(self):
        self.avg_cnt += 1
        if self.avg_cnt > min(AVG_PTS, len(self.data_x)+1):
            self.avg_cnt = 1
        now = time.time()
        dx = (now - self.last_time) / S_PER_TIMEUNIT
        self.last_time = now
        self.data_x = [x-dx for x in self.data_x]
        if self.avg_cnt == 1:
            self.avg_x = now
            self.data_x.append(0)
        else:
            self.avg_x += now
            self.data_x[-1] = (self.avg_x/self.avg_cnt - now)/S_PER_TIMEUNIT
        
        if len(self.data_x)>MAX_PTS_PER_GRAPH:
            self.data_x.pop(0)
            
        for b in self.the_boards:
            b.read_from_sock(self.avg_cnt)
        '''nn = len(self.data_T[0])
        self.data_x = [-nn+i+1 for i in range(nn)]'''
        if len(self.data_x)>1:
            self.chart.draw(self.data_x, self.data_T)
            self.chart2.draw(self.data_x, self.data_L)
        self.timer_id = self.master.after(UPDATE_PERIOD_MS, self.on_timer)




if __name__ == '__main__':
    root = tki.Tk()
    root.title('Cooling')
    root.geometry('350x840')#'350x490'
    app = Cooling()
    root.mainloop()

