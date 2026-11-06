import tkinter as tki
import s1s2_main
import commonPS, valve, pressures, commonPS2, arcfilament, magnet_pirani, koven, switchingmagnet

TERM_SERV_ADDR = '192.168.2.7'


the_items = [
    #item                 , TERM_SERV_ADDR, N, 'name'            , ctrl, presets          , ctrl_coef, I_read_coef    , V_read_coef   , ctrl_min_max, I_read_min_max           , V_read_min_max           , ctrl_units, I_units, V_units, dctrl  , F_ctrl_coef, F_read_coef      , F_min_max , F_units      
    #(pressures.Pressure1, ''            ,-1, 'Pressures', 'S2'),
    #(koven.KOven         , TERM_SERV_ADDR, 8, 'KOven'    , [('190',  190)], (0   , 195,   360) , (0   , 195,   360), (0, 100, 100), 1), # 5mA, 3kV
    (arcfilament.ArcFilament, TERM_SERV_ADDR, 3, 'Arc/Filament', 'I' , [               ], 5.0/100  , 3.0/0.719/32768.0, 0.02        , (0, 65, 100), (1.3, 1.7, 3.0)          , (50 , 90, 250           ), '%'      , 'A'    , 'V'    , 0.5     , 5.0/50.0   , 30.0/0.594/32768.0, (0, 27, 30), ' '), # 5mA, 3kV
    #(valve.Valve        , '192.168.2.1', 22333-3000, 'Gas'    ),
]

if __name__ == '__main__':
    root = tki.Tk()
    root.title('Stest')
    root.geometry('1168x910')
    app = s1s2_main.S1S2(the_items, 'Stest')
    root.mainloop()
