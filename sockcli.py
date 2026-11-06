import socket
import time

print('creating')
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
print('connecting')
s.settimeout(10)
try:
    s.connect(('192.168.2.7', 3006))
    sendStr = 'get'
    print('sending:  ', sendStr)
    s.sendall(bytes(sendStr+'\n', 'utf-8'))
    time.sleep(0.2)
    
    sendStr = 'setV 0.1'
    print('sending:  ', sendStr)
    s.sendall(bytes(sendStr+'\n', 'utf-8'))
    time.sleep(0.2)

    sendStr = 'get'
    print('sending:  ', sendStr)
    s.sendall(bytes(sendStr+'\n', 'utf-8'))
    time.sleep(0.2)

    resp = str(s.recv(256), 'utf-8').strip()
    print('received: ', resp)
except TimeoutError:
    print('TIMEOUT')
print('closing')
s.close()
print('done.')
