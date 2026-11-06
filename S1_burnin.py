import tkinter as tki
import s1s2_main
import commonPS, valve, pressures, commonPS2, arcfilament, magnet_pirani, koven, switchingmagnet, solidfilament, magnet_gas
import mass_flow_controller as mfc
import intensities

TERM_SERV_ADDR = ('192.168.2.200', 10000)
#TERM_SERV_ADDR = ('192.168.2.7', 3000)


the_items = [
    #item                 , TERM_SERV_ADDR, N, 'name'            , ctrl, presets          , ctrl_coef, I_read_coef    , V_read_coef   , ctrl_min_max, I_read_min_max           , V_read_min_max           , ctrl_units, I_units, V_units, dctrl  , F_ctrl_coef, F_read_coef      , F_min_max , F_units      
    (pressures.Pressure1, ''            ,-1, ('Pressure S1','dbman_pressure'), 'S1', []),
    
    (arcfilament.ArcFilament, TERM_SERV_ADDR, 8, ('S1_Arc/Filament','Arc/filament'), 'I' , [               ], 5.0/100  , 8.379956e-05, 0.007972     , (0, 65, 100), (1.3, 1.7, 3.0)          , (50 , 90, 250           ), '%'      , 'A'    , 'V'    , 0.5     , 5.0/50.0   , 0.001256          , (0, 27, 30), ' '                                                           , [830, 660, -400, -400]), #arc/filament 5mA, 3kV
    
    #(arcfilament.ArcFilament, TERM_SERV_ADDR, 26, 'Arc/Filament', 'I' , [               ], 5.0/100  , 3.0/0.719/32768.0, 0.02        , (0, 65, 100), (1.3, 1.7, 3.0)          , (50 , 90, 250           ), '%'      , 'A'    , 'V'    , 0.5     , 5.0/50.0   , 30.0/0.594/32768.0, (0, 27, 30), ' ', []), # 5mA, 3kV
    #(solidfilament.SolidFilament, TERM_SERV_ADDR, 10, 'Solid filament', 'I' , [          ], 0.056929   , 0.003275,            0.0002786 , None        , (0, 80, 90)               , (0   ,   3.5,  6)          , 'A'     , 'A'   , 'V'   , 0.10                                                                                                                    , [860, 760]), #Solid filament
    #(commonPS2.CommonPS  , TERM_SERV_ADDR, 16, 'Extraction'      , 'V' , [('14', 14)     ], 5.0/20   , 0.000030523*5  , 0.00004352*20 , None        , (0, 2,  5           )    , (13.5 , 14.5,  20*0+10*2 ), 'kV'     , 'mA'   , 'kV'   , 0.010, []), # 5mA, 20kV
    #(switchingmagnet.SwitchingMagnet, TERM_SERV_ADDR, 32, 'Sw magnet/sw magnet field', 'I' , [('H', 4.7),('He', 9.4),('15N', 19.1)], 5/40.0     , 40/32768.0/1.168      , 27.52/32768.0             , (0, 30, 40), (0, 30, 40)           , (0 , 20, 35           ), 'A'      , 'A'    , 'V'    , 0.01     , 0         , 0.00250862       , (0, 9000, 9000), 'G'   , [  2,   2, -400, -400]), #sw magnet/field
    #(mfc.MassFlowController, TERM_SERV_ADDR, 6, 'Gas MFC', 'F' , [               ]        , 1       ,      1          , 0          , (0, 0.5,0.5), (0, 0.5, 0.5  )          , (50 , 90, 250           ), 'Sccmpm'      , 'Sccmpm'    , ' '  , 0.001                                                                                                         , [830, 660, -400, -400]), 
    #(magnet_gas.MagnetGas, TERM_SERV_ADDR, 8, 'Solenoid/Gas', 'I' , [ ('1.4', 1.4)  ]     , 5.0/10/1.4*5.5 , 3.0/0.719/32768.0,     0      , (1, 2, 2.5), (1.3, 1.7, 3.0)          , (50 , 90, 250           ), 'A'      , 'A'    , 'V'    , 0.01     , 5.0/10.0   , 0                 , (1.9, 2.5, 10), ' '                                                           , [830, 660, -400, -400]), #arc/filament 5mA, 3kV
    #(commonPS2.CommonPS  , TERM_SERV_ADDR, 16, 'Extraction'      , 'V' , [('14', 14)     ], 5.0/20   , 0.000030523*5  , 0.00004352*20 , None        , (0, 2,  5           )    , (13.5 , 14.5,  20*0+10*2 ), 'kV'     , 'mA'   , 'kV'   , 0.010, []), # 5mA, 20kV
    #(intensities.Intensities, ''            ,-1, ('Intensities','Intensities')),
]

if __name__ == '__main__':
    root = tki.Tk()
    root.title('S1_burnin')
    root.geometry('1168x910')
    app = s1s2_main.S1S2(the_items, 'S1_burnin')
    root.mainloop()
