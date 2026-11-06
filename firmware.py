import common
import os
import hashlib
import time

TERM_SERV_ADDR =  ('192.168.2.200', 10000)
#TERM_SERV_ADDR = ('192.168.2.7', 3000)

def uploadFile(fnlocal, fnremote, port, term_serv_addr=TERM_SERV_ADDR, restart=True):
    print('sending file ', fnlocal)
    if not os.path.isfile(fnlocal):
        print('File not found!')
        return 
    fsize = os.stat(fnlocal)[6]
    hash = hashlib.sha256(open(fnlocal,'rb').read()).digest().hex() # <=================== 1 or 256
    socket, sockok = common.connect_socket(term_serv_addr, port, 'tmp')
    if not sockok: return
    cmd = 'firmwareUpdate' if restart else 'uploadFile'
    msg = cmd+' '+str(fsize)+' '+fnremote+' '+hash
    print('sending', msg)
    ret = common.send_socket_message(socket, msg)
    print('reply 1:', ret, '[end of reply1]')
    if ret != 'ok':
        socket.close()
        print('Reply 1 was not ok!')
        return
    f = open(fnlocal,'rb')
    cnt = fsize
    while cnt > 0:
        s = f.read(200)  # read at most 200 chars   
        socket.sendall(s)
        cnt -= len(s)
        #print(cnt)
    f.close()
    print('File sent, waiting for confirmation...')
    r = bytes()
    while True:
        try:
            r = socket.recv(256)
            if b'\n' in r:
                break
        except:
            print('waiting...')
    resp = str(r, 'utf-8').strip()
    print('confirmation:', resp)
    socket.close()
    print('DONE SENDING')
    if not restart:
        return
    if resp == 'ok':
        print('waiting for restart...')
        time.sleep(6)
        v = restarted(port, term_serv_addr)
        if v == '1':
            print('was restarted, sending ok...')
        else:
            print('fail!')
            return
        time.sleep(1)
        v = ok(port, term_serv_addr)
        if v == 'ok':
            print('ok, getting version:')
        else:
            print('fail 2!')
        time.sleep(1)
        version(port, term_serv_addr)
        print('=== all done ===')
        
        
def uploadFileNoR(fnlocal, fnremote, port, term_serv_addr=TERM_SERV_ADDR):
    return uploadFile(fnlocal, fnremote, port, term_serv_addr, restart=False)


def dir(port, term_serv_addr=TERM_SERV_ADDR):
    socket, sockok = common.connect_socket(term_serv_addr, port, 'tmp')
    if not sockok: return ''
    ret = common.send_socket_message(socket, 'dir')
    print(ret)
    socket.close()
    return ret
    
def ok(port, term_serv_addr=TERM_SERV_ADDR):
    socket, sockok = common.connect_socket(term_serv_addr, port, 'tmp')
    if not sockok: return ''
    ret = common.send_socket_message(socket, 'ok')
    print(ret)
    socket.close()
    return ret

def version(port, term_serv_addr=TERM_SERV_ADDR):
    socket, sockok = common.connect_socket(term_serv_addr, port, 'tmp')
    if not sockok: return ''
    ret = common.send_socket_message(socket, 'version')
    print(ret)
    socket.close()
    return ret

def restarted(port, term_serv_addr=TERM_SERV_ADDR):
    socket, sockok = common.connect_socket(term_serv_addr, port, 'tmp')
    if not sockok: return ''
    ret = common.send_socket_message(socket, 'restarted')
    print(ret)
    socket.close()
    return ret

def getFile(fnlocal, fnremote, port, term_serv_addr=TERM_SERV_ADDR):
    print('getting file ', fnremote)
    socket, sockok = common.connect_socket(term_serv_addr, port, 'tmp')
    if not sockok: return
    socket.sendall(bytes('getFile '+fnremote+'\n', 'utf-8'))
    r = bytes()
    while True:
        r += socket.recv(256)
        if b'\n' in r:
            break
    rr = r.split(b'\n', 1) # split by the first occurance of newline
    ret = str(rr[0], 'utf-8').strip()
    remains = rr[1]
    print('got:', r)
    print('reply 1:', ret)
    print('remains:', remains)
    rr = ret.split()
    try:
        fsize = int(rr[0])
    except:
        socket.close()
        print('Reply 1 was not ok!')
        return
    remhash = rr[2]
    f = open(fnlocal,'wb')
    f.write(remains)
    cnt = fsize - len(remains)
    while cnt > 0:
        s = socket.recv(200)
        f.write(s)  # read at most 200 chars   
        cnt -= len(s)
        print(cnt)
    f.close()
    socket.close()
    print('File received, checking...')
    if not os.path.isfile(fnlocal):
        print('File not found!')
        return 
    hash = hashlib.sha256(open(fnlocal,'rb').read()).digest().hex()
    if hash == remhash:
        print('Hash matches, done.')
    else:
        print('File hash does NOT match!!')
    return
    
def test(port, cnt = 70, term_serv_addr=TERM_SERV_ADDR):
    socket, sockok = common.connect_socket(term_serv_addr, port, 'tmp')
    if not sockok: return ''
    for i in range(10):
        ret = common.send_socket_message(socket, 'test '+str(i)+' '+str(cnt))
        print(ret)
        time.sleep(0.1)
    socket.close()
    return ret

def updateAllCommonPS(dn):
    uploadFile('/home/s1s2/Documents/pico_filamentPS/main.py', 'main.py', dn) 
    time.sleep(1)
    uploadFileNoR('/home/s1s2/Documents/pico_filamentPS/ads1x15.py', 'ads1x15.py', dn)
    time.sleep(1)
    uploadFileNoR('/home/s1s2/Documents/pico_filamentPS/AD569x.py', 'AD569x.py', dn)
    time.sleep(1)
    uploadFileNoR('/home/s1s2/Documents/pico_filamentPS/mcp4725.py', 'mcp4725.py', dn)
    time.sleep(1)
    uploadFile('/home/s1s2/Documents/pico_filamentPS/device_specific.py', 'device_specific.py', device_N)
    
    
#uploadFile('/home/s1s2/Documents/pico_valve/main.py', 'main.py', 8)

device_N = 27 # fails with 17-25, 32, but is ok on 1,2,4, 16? rare fail on 3??
#updateAllCommonPS(device_N)
#test(device_N, cnt=70) #25, 33, 72, 172, 82, 80; but fine with 79?
#version(device_N)
#uploadFile('/home/s1s2/Documents/pico_filamentPS/main.py', 'main.py', device_N) 
#uploadFileNoR('/home/s1s2/Documents/pico_filamentPS/ads1x15.py', 'ads1x15.py', device_N)
#uploadFileNoR('/home/s1s2/Documents/pico_filamentPS/AD569x.py', 'AD569x.py', device_N)
#uploadFileNoR('/home/s1s2/Documents/pico_filamentPS/mcp4725.py', 'mcp4725.py', device_N)
uploadFile('/home/s1s2/Documents/pico_filamentPS/device_specific.py', 'device_specific.py', device_N)


#uploadFile('/home/s1s2/Documents/pico_koven/device_specific.py', 'device_specific.py', 8)
#uploadFile('/home/s1s2/Documents/pico_koven/pid.py', 'pid.py', 8)

#uploadFile('/home/s1s2/Documents/pico_valve/main.py', 'main.py', device_N) 

#dir(11)
#version(device_N)
#ok(7)
#getFile('/home/s1s2/Documents/pico_filamentPS/ads1x15.py', 'ads1x15.py', 11)
#getFile('/home/s1s2/Documents/tmp.py', 'ads1x15.py', device_N)
#getFile('/home/s1s2/Documents/pico_filamentPS/device_specific_11.py', 'device_specific.py', device_N)
