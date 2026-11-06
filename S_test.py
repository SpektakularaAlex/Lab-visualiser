import tkinter as tki
from tkinter import ttk
import s1s2_main
#import arcfilament
#import magnet_pirani
import common
#TERM_SERV_ADDR = '192.168.2.7'
TERM_SERV_ADDR = ('192.168.2.200', 10000)
#from pico_filamentPS.device_specific import DEV_LIST
import valve, commonPS2, arcfilament, magnet_pirani, koven, switchingmagnet, solidfilament
'''
from S1 import the_items as S1_items
from S2 import the_items as S2_items
all_items = S1_items + S2_items


'''
all_items = [    #                                                                                             ,ctrl , [], ctrl coef, I read coef          , V read coef       , ctrl minmax  , I minmax             , V minmax                 , ctrl unit   , Iunit      , Vunit       , step   , ctrl2 coef, 3rd read coef     , 3rd minmax     ,3rd unit, ignore
    (valve.Valve                    , TERM_SERV_ADDR, 9 , ('Gas'                           ,'gas 3x'          )                                                                                                                                                                                                                              , [  2, 830]            ), #gas
    #(magnet_pirani.MagnetPirani     , TERM_SERV_ADDR, 27, ('Magnet/Pirani/invert'          ,'Pressure/magnet' ), 'I' , [], 3.03     , 8.5085e-5            , 0                 , (0.5, 1.5, 2), (0.5, 1.5, 2)        , (50 , 90, 250           ), 'cu'        , 'A'          , 'V'          , 0.01   , 0         , 0.00250862        , (8, 48, 70)    , ('p','mbar'), [890, 860,    2,  720]), #solenoid/pirani
    (commonPS2.CommonPS             , TERM_SERV_ADDR, 27, ('Magnet g6/gas_pirani'          ,'Pressure/magnet' ), 'I' , [], 0.5      , 4.096/32768.0/49     , 4.096/32768.0/1   , (0.5, 1.5, 2), (0.5, 1.5, 2)        , (50 , 90, 250           ), ('out1','V'), ('in4','V'), ('in5','V') , 0.01   , 0.5       , 4.096/32768.0/0.7 , (8, 48, 70)    , ('out2','in7','V')   , [890, 860,    2,  720]), #solenoid/pirani
    #(magnet_gas.MagnetGas          , TERM_SERV_ADDR,  7, ('Solenoid/Gas/invert'           ,'Pressure/magnet' ), 'I' , [], 2.86757  , 8.7223e-05           , 0                 , (1, 2, 2.5)  , (1.3, 1.7, 3.0)      , (50 , 90, 250           ), 'A'         , 'A'        , 'V'         , 0.01   , 5.0/10.0  , 0                 , (1.9, 2.5, 10) , ' '         , [830, 660, -400, -400]), #Solenoid/Gas
    (solidfilament.SolidFilament    , TERM_SERV_ADDR, 10, ('Solid filament'                ,'Solid filament'  ), 'I' , [], 0.5      , 6.144/32768.0/1      , 6.144/32768.0/1   , None         , (0, 80, 90)          , (0   ,   3.5,  6)        , 'A'         , 'A'        , 'V'         , 0.10                                                                  , [860, 760]            ), #Solid filament
    (arcfilament.ArcFilament        , TERM_SERV_ADDR, 26, ('S2_Arc/Mesh filament'          ,'Arc/filament'    ), 'I' , [], 0.5      , 4.096/32768.0/1      , 4.096/32768.0/1   , (0, 65, 100) , (1.3, 1.7, 3.0)      , (50 , 90, 250           ), '%'         , 'A'        , 'V'         , 0.5    , 5.0/50.0  , 30.0/0.594/32768.0, (0, 27, 30)    , ' '         , [830, 660, -400, -400]), #arc/filament 5mA, 3kV
    (commonPS2.CommonPS             , TERM_SERV_ADDR, 14, ('Extraction'                    ,'Extraction'      ), 'V' , [], 0.5      , 6.144/32768.0/1      , 6.144/32768.0/1   , None         , (0, 2,  5*0+0.633*2) , (9.5 , 10.5,  20*0+10*2 ), 'kV'        , 'mA'       , 'kV'        , 0.010                                                                 , [800, 560]            ), #extraction 5mA, 20kV
    (commonPS2.CommonPS             , TERM_SERV_ADDR, 11, ('Einzel lens'                   ,'EinzelLens'      ), 'V' , [], 0.5      , 6.144/32768.0/1      , 6.144/32768.0/1   , None         , (0, 1, 3.7*0+0.3*2)  , (0   ,   10,  20*0+9.5*2), 'kV'        , 'mA'       , 'kV'        , 0.010                                                                 , [390, 560]            ), #einzel lens    3.7mA,  20kV for S2; 2.5mA, 30kV for S1
    (koven.KOven                    , TERM_SERV_ADDR, 15, ('KOven'                         ,' K oven'         ),       [],                                                       (0, 195, 360), (0   , 195,   360)   , (0, 100, 100)                                                       , 1                                                                     , [340, 460]            ), #Koven 5mA, 3kV
    (commonPS2.CommonPS             , TERM_SERV_ADDR, 12, ('NeutrTrap g2'                  ,'Neutral trap'    ), 'V' , [], 0.5      , 6.144/32768.0/2      , 6.144/32768.0/1   , None         , (0, 2,   5*0+0.115*2), (0   ,    2,   3*0+1.1*2), ('out13','V'), ('in14','V'), ('in9','V') , 0.005                                                                 , [290, 360]            ), #neutral trap   5mA, 3kV
    (commonPS2.CommonPS             , TERM_SERV_ADDR, 30, ('Pre-acc'                       ,'Pre-acceleration'), 'V' , [], 0.5      , 6.144/32768.0/1      , 6.144/32768.0/1   , None         , (0, 1,  3*0+0.385*2) , (39.0, 41.0, 100*0+40*2 ), 'kV'        , 'mA'       , 'kV'        , 0.010                                                                 , [152, 260]            ), #pre-accel 3mA, 100kV
    (commonPS2.CommonPS             , TERM_SERV_ADDR, 28, ('Grid lens'                     ,'Grid'            ), 'V' , [], 0.5      , 6.144/32768.0/1      , 6.144/32768.0/1   , (0.0, 0.1, 1), (0.0, 0.1, 1)        , (0.0   ,   0.1,  1)      , 'kV'        , 'mA'       , 'kV'        , 0.002                                                                 , [102, 160]            ), #gridlens
    (commonPS2.CommonPS             , TERM_SERV_ADDR, 29, ('Steerer S2'                    ,'Steerer'         ), 'I' , [], 0.5      , 4.096/32768.0/1      , 4.096/32768.0/1   , (0.4, 0.6, 1), (0.4, 0.6, 1)        , (0.4   ,   0.6,  1)      , 'kV'        , 'kV'       , 'kV'        , 0.002                                                                 , [ 52, 100]            ), #steerer 
    (switchingmagnet.SwitchingMagnet, TERM_SERV_ADDR, 32, ('Sw magnet/sw magnet field/hide','Switching magnet'), 'I' , [], 0.5      , 4.096/32768.0/1      , 4.096/32768.0/1   , (0, 30, 40)  , (0, 30, 40)          , (0 , 20, 35           )  , 'A'         , 'A'        , 'V'         , 0.01   , 0         , 0.00250862        , (0, 9000, 9000), 'G'         , [  2,   2, -400, -400]), #sw magnet/field
]

PIN_STRINGS = {
    'Arc/filament': 'Ark ctrl: pin N \n Filament ctrl: pin M',
    'Solid filament': 'Ark ctrl: pin N \n Filament ctrl: pin M',
    'gas 3x': 'Ark ctrl: pin N \n Filament ctrl: pin M',
    'Pressure/magnet': 'Ark ctrl: pin N \n Filament ctrl: pin M',
    'Extraction': 'Ark ctrl: pin N \n Filament ctrl: pin M',
    'EinzelLens': 'Ark ctrl: pin N \n Filament ctrl: pin M',
    ' K oven': 'Ark ctrl: pin N \n Filament ctrl: pin M',
    'Neutral trap': 'Ark ctrl: pin N \n Filament ctrl: pin M',
    'Pre-acceleration': 'Ark ctrl: pin N \n Filament ctrl: pin M',
    'Grid': 'Ark ctrl: pin N \n Filament ctrl: pin M',
    'Steerer': 'Ark ctrl: pin N \n Filament ctrl: pin M',
    'Switching magnet': 'Ark ctrl: pin N \n Filament ctrl: pin M',
    
}



if __name__ == '__main__':
    root = tki.Tk()
    root.title('S2 test')
    root.geometry('808x866')
    #root.tk.call('wm', 'title', root, 'Mysda')
    
    sok = common.MySerial('local board')
    local_version = sok.send_message('version')
    remote_sok = common.MySerialRemote(sok)
    remote_version = remote_sok.send_message('version')
    #print(DEV_LIST)
    sok.close()
    print('local', local_version)
    print('remote', remote_version)
    local_list = []
    for it in all_items:
        if it[3][1] in local_version:
            local_list.append(it)
    remote_list = []
    for it in all_items:
        if it[3][1] in remote_version:
            remote_list.append(it)
    if len(local_list) == 0:
        print('No local match found!!!')
    if len(remote_list) == 0:
        print('No remote match found!!!')
    if len(local_list) > 1:
        print('more than one local match found!!!')
    if len(remote_list) > 1:
        print('more than one remote match found!!!')
        
    root.withdraw()  # Hide the root window

    # Create the dialog
    dialog = tki.Toplevel(root)
    dialog.title("Card selection")
    dialog.grab_set()  # Make dialog modal

    # Add your widgets
    style = ttk.Style()
    style.map('TCombobox', fieldbackground=[('readonly', 'white')])
    style.map('TCombobox', background=[('readonly', 'white')])
    style.map('TCombobox', foreground=[('readonly', 'black')])
    style.map('TCombobox',
        fieldbackground=[('disabled', '#f0f0f0')],
        background=[('disabled', '#f0f0f0')],
        foreground=[('disabled', '#808080')]
    )
    
    ttk.Label(dialog, text="Card connected to the usb:").pack(padx=20, pady=20)
    combo_local = ttk.Combobox(dialog, width = 27)
    combo_local.pack(padx=20, pady=4)
    combo_local['values'] = tuple([n[3][0] for n in local_list]) if len(local_list)>0 else ('[None]',)
    combo_local.current(0)
    if len(local_list) < 2:
        combo_local.config(state='disabled')
    else:
        combo_local.config(state='readonly')
    
    ttk.Label(dialog, text="Second card connected through fiber:").pack(padx=20, pady=20)
    combo_remote = ttk.Combobox(dialog, width = 27)#, textvariable = n)
    combo_remote.pack(padx=20, pady=4)
    combo_remote['values'] = tuple([n[3][0] for n in remote_list]) if len(remote_list)>0 else ('[None]',)
    combo_remote.current(0)
    if len(remote_list) < 2:
        combo_remote.config(state='disabled')
    else:
        combo_remote.config(state='readonly')

    user_choice = (0,0)

    def on_ok():
        global user_choice
        user_choice = (combo_local.current(), combo_remote.current())
        dialog.destroy()

    ok_button = ttk.Button(dialog, text="OK", command=on_ok)
    ok_button.pack(pady=10)

    # Wait for the dialog to close (starts its own event loop)
    root.wait_window(dialog)


    
    items = ([local_list[user_choice[0]]] if len(local_list)>0 else []) + ([remote_list[user_choice[1]]] if len(remote_list)>0 else [])
    if len(items)>0:
        items[0] = items[0][:1]+('usb',)+items[0][2:] 
    if len(items)>1:
        items[1] = items[1][:1]+('rem',)+items[1][2:] 
    app = s1s2_main.S1S2(items, 'S_test')
    #root.wm_class("MyApp1", "MyApp2")
    #root.tk.call('wm', 'group', root, '.')
    #root.wm_attributes('-topmost', 'MyApp')
    root.deiconify()  # Show the root window
    root.mainloop()
