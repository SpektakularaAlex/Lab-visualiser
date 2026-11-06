import tkinter as tki
import s1s2_main
import commonPS, valve, pressures, commonPS2, arcfilament, magnet_pirani, koven, switchingmagnet, solidfilament, magnet_gas, mass_flow_controller, ammeter

TERM_SERV_ADDR = ('192.168.2.200', 10000)
#TERM_SERV_ADDR = ('192.168.2.7', 3000)


the_items = [
    #item                 , TERM_SERV_ADDR, N, 'name'            , ctrl, presets          , ctrl_coef, I_read_coef    , V_read_coef   , ctrl_min_max, I_read_min_max           , V_read_min_max           , ctrl_units, I_units, V_units, dctrl  , F_ctrl_coef, F_read_coef      , F_min_max , F_units      
    (pressures.Pressure1, ''            ,-1, ('Pressure S2','dbman_pressure'), 'S2', []),
    (solidfilament.SolidFilament, TERM_SERV_ADDR, 10, ('Solid filament','Solid filament'), 'I' , [          ], 0.056929   , 0.003275,            0.0002786 , None        , (0, 80, 90)               , (0   ,   3.5,  6)          , 'A'     , 'A'   , 'V'   , 0.10                                                                                                                    , [860, 760]), #Solid filament
    (ammeter.Ammeter, 'usb', -1, ('Ammeter','Ammeter')        , 'I' , []               , 0         , 0.025       , 0             , None        , (0, 80, 90)               , (0   ,   0,  0)          , ''      , 'nA'   , ''      , 0                                                                                                                    , [860, 760]), #Ammeter
    #(arcfilament.ArcFilament, TERM_SERV_ADDR, 26, ('S2_Arc/Mesh filament/hide','Arc/filament'), 'I' , [               ], 5.0/100  , 3.0/0.719/32768.0, 0.007972     , (0, 65, 100), (1.3, 1.7, 3.0)          , (50 , 90, 250           ), '%'      , 'A'    , 'V'    , 0.5     , 5.0/50.0   , 30.0/0.594/32768.0, (0, 27, 30), ' '                                                           , [830, 660, -400, -400]), #arc/filament 5mA, 3kV
]

if __name__ == '__main__':
    root = tki.Tk()
    root.title('S2_burnin')
    root.geometry('1168x910')
    app = s1s2_main.S1S2(the_items, 'S2_burnin')
    root.mainloop()
