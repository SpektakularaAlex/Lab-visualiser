import socket
import threading

class SingleConnectionSocketServer():
    def __init__(self, port, on_data_proc):
        self.port = port
        self.on_data_proc = on_data_proc
        self._stop_flag = False
        self.connected = False
        self.the_server_thread = threading.Thread(target=self.the_server_thread_function)
        self.the_server_thread.daemon = True
        self.the_server_thread.start()

    def the_server_thread_function(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('', self.port))
            except:
                print('Server socket '+str(self.port)+' already in use, will not listen.')
                return
            s.listen(10)
            print('>>>> socket server: listening on port ',self.port)
            while not self._stop_flag:
                self.connected = False
                conn, addr = s.accept()
                with conn:
                    print('>>>> socket server: connected by ', addr)
                    self.connected = True
                    if self._stop_flag:
                        print('>>>> socket server got a stop event, closing.')
                        break
                    conn.settimeout(2.0)
                    while not self._stop_flag:
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
                        rep = self.on_data_proc(data)
                        if not rep is None:
                            conn.sendall(rep)
            self.connected = False
            s.close()
            print('>>>> socket server closed <<<<<<<')

    def stop(self):
        self._stop_flag = True
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.2)
        print('sending shutdown socket...')
        try:
            s.connect(('localhost', self.port))
        except Exception as ex:
            print('exception when connecting shutdown socket in stop_the_socket_server', ex)
        s.close()
        print('sending shutdown socket completed, waiting for socket server thread to finish...')
        self.the_server_thread.join()
        print('socket server stopped')
