import tkinter as tki
import s1s2_main
import pressures, commonPS2, arcfilament, switchingmagnet, magnet_gas, mass_flow_controller, ammeter

#TERM_SERV_ADDR_old = ('192.168.2.7', 3000) # ip_address and port_base
TERM_SERV_ADDR = ('192.168.2.200', 10000) # ip_address and port_base


the_items = [
    #item                 , TERM_SERV_ADDR, N, 'name'            , ctrl, presets          , ctrl_coef, I_read_coef    , V_read_coef   , ctrl_min_max, I_read_min_max           , V_read_min_max           , ctrl_units, I_units, V_units, dctrl  , F_ctrl_coef, F_read_coef      , F_min_max , F_units      
    (pressures.Pressure1, ''            ,-1, ('Pressures','dbman_pressure'), 'S1', []),
    (mass_flow_controller.MassFlowController, TERM_SERV_ADDR, 6, ('Gas MFC',''), 'I' , [               ], 1  , 1, 1     , (0, 65, 100), (1.3, 1.7, 3.0)          , (50 , 90, 250           ), ('flow','%')      , ('flow','%')    , ('p','psi')    , 0.5     , 0   , 0, (0, 27, 30), ' '                                                           , [830, 660, -400, -400]), #arc/filament 5mA, 3kV
    (magnet_gas.MagnetGas, TERM_SERV_ADDR, 7, ('Solenoid/Gas/invert','Pressure/magnet'), 'I' , [ ('1.4', 1.4)  ]     , 2.86757 , 8.7223e-05 ,     0      , (1, 2, 2.5), (1.3, 1.7, 3.0)          , (50 , 90, 250           ), 'A'      , 'A'    , 'V'    , 0.01     , 5.0/10.0   , 0                 , (1.9, 2.5, 10), ' '                                                           , [830, 660, -400, -400]), #arc/filament 5mA, 3kV
    (arcfilament.ArcFilament, TERM_SERV_ADDR, 8, ('S1_Arc/Filament/invert','Arc/filament'), 'I' , [               ], 5.0/100  , 8.379956e-05, 0.007972     , (0, 65, 100), (1.3, 1.7, 3.0)          , (50 , 90, 250           ), '%'      , 'A'    , 'V'    , 0.5     , 5.0/50.0   , 0.001256          , (0, 27, 30), ('I','A')                                                           , [830, 660, -400, -400]), #arc/filament 5mA, 3kV
    (commonPS2.CommonPS  , TERM_SERV_ADDR, 16, ('Extraction','Extraction')      , 'V' , [('14', 14)     ], 5.0/20   , 0.000030523*5  , 0.00004352*20 , None        , (0, 2,  5           )    , (13.5 , 14.5,  20*0+10*2 ), 'kV'     , 'mA'   , 'kV'   , 0.010, []), # 5mA, 20kV
    (commonPS2.CommonPS  , TERM_SERV_ADDR, 13, ('Einzel lens','EinzelLens')     , 'V' , [('9.32' , 9.32)], 5.0/30   , 0.000030523*2.5, 0.00004432*30 , None        , (0, 1, 2.5          )    , (0   ,   10,  30*0+9.5*2), 'kV'     , 'mA'   , 'kV'   , 0.010, []), #3.7mA,  20kV for S2; 2.5mA, 30kV for S1
    (commonPS2.CommonPS  , TERM_SERV_ADDR, 30, ('Pre-acc','Pre-acceleration')         , 'V' , [('40', 40)]     , 5.0/100  , 0.0000352*3    , 0.00004592*100, None        , (0, 1,  3)               , (39.0, 41.0, 100), 'kV', 'mA', 'kV', []), # 3mA, 100kV
    (commonPS2.CommonPS  , TERM_SERV_ADDR, 29, ('Steerer S1','Steerer')     , 'V' , [('0.41' , 0.41)], 5.0/1.0   , 2.529e-5*0,      0 , (0.4, 0.6, 1), (0.4, 0.6, 1)    , (0.4   ,   0.6,  1), 'kV'     , 'kV'   , 'kV'   , 0.002, []), 
    (commonPS2.CommonPS  , TERM_SERV_ADDR, 28, ('Grid lens','Grid')     , 'V' , [('0' , 0.0)], 5.0/1.0   , 2.529e-5, 2.529e-5 , (0.0, 0.1, 1), (0.0, 0.1, 1)    , (0.0   ,   0.1,  1), 'kV'     , 'mA'   , 'kV'   , 0.002, []), 
    (switchingmagnet.SwitchingMagnet, TERM_SERV_ADDR, 32, ('Sw magnet/sw magnet field/hide','Switching magnet'), 'I' , [('H', 4.7),('He', 9.2),('15N', 19.1)], 5/40.0     , 40/32768.0/1.168      , 27.52/32768.0             , (0, 30, 40), (0, 30, 40)           , (0 , 20, 35           ), 'A'      , 'A'    , 'V'    , 0.01     , 0         , 0.00250862       , (0, 9000, 9000), 'G', []),
    (ammeter.Ammeter, 'usb', -1, ('Ammeter','Ammeter')        , 'I' , []               , 0         , 0.025       , 0             , None        , (0, 80, 90)               , (0   ,   0,  0)          , ''      , 'nA'   , ''      , 0                                                                                                                    , [860, 760]), #Ammeter


]

if __name__ == '__main__':
    root = tki.Tk()
    root.geometry('808x1110')
    app = s1s2_main.S1S2(the_items, 'S1')
    root.mainloop()
