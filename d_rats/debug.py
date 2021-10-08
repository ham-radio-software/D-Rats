
from __future__ import print_function
from datetime import datetime


def printlog(arg1, *args):
#List of modules
    modules2print = ['D-Rats',           # main program
                     'Agw',              # d_rats\agw.py
                     'Ax25',             # d_rats\ax25.py  
                     'Cap',              # d_rats\cap.py                     
                     'Chat',             # sessions\chat.py 
                     'Comm',             # d_rats\comm.py
                     'Config',           # d_rats\config.py
                     'config_tips',      # d_rats\config_tips.py
                     'ConnTest',         # d_rats\ui\conntest.py                    
                     'Ddt2',             # d_rats\ddt2.py                     
                     'debug',            # d_rats\debug.py
                     'dPlatform',        # d_rats\dplatform.py   
                     'emailgw',          # d_rats\emailgw.py
                     'Formbuilder',      # d_rats\formbuilder.py     
                     'Formgui',          # d_rats\formgui.py
                     'Gps',              # d_rats\gps.py
                     'Geocode',          # geocode.py      
                     'Mainapp',          # d_rats\mainapp.py
                     'Mainchat',         # d_rats\ui\main_chat.py
                     
                     'MainEvents',       # d_rats\ui\main_events.py                     
                     
                     'MainMsgs',         # d_rats\ui\main_messages.py                     
                     'Mainfiles',        # d_rats\ui\main_files.py
                     'MainStation',      # d_rats\ui\main_stations.py                                        
                     'Mainwind',         # mainwindow.py'
                     'Mapdisplay',       # d_rats\mapdisplay.py   
                     'Mapsrc',           # d_rats\map_sources.py                     
                     'Mapsrcedit',       # d_rats\map_source_editor.py
                     'MscWidget',        # d_rats\miscwidgets.py
                     'Platform',         # d_rats\platform.py
                     'Pluginsrv',        # d_rats\pluginsrv.py   
                     'Msgrouting',       # d_rats\msgrouting.py                    
                     'Qst',              # d_rats\qst.py
                     'RPC',              # d_rats\sessions\rpc.py
                     'SessCoord',        # d_rats\session_coordinator.py
                     'Sessionmgr',       # Sessionmanager.py  
                     'Subst',            # d_rats\subst.py
                     
                     'Transport',        # d_rats\transport.py
                     'Utils',            # d_rats\utils.py
                     'Version',          # d_rats\version.py                     
                     'Wl2k',             # d_rats\wl2k.py
                     
                     #TO DO
                     'Callsigns',       #d_rats\callsigns.py
                     'geocode_ui',      #d_rats\geocode_ui.py
                     'image',           #d_rats\image.py
                     'inputdialog',     #d_rats\inputdialog.py
                     'mailsrv',         #d_rats\mailsrv.py
                     
                     'reqobject',       #d_rats\reqobject.py
                     'sessionmgr',      #d_rats\sessionmgr.py

                     'signals',         #d_rats\signals.py
                     'spell',           #d_rats\spell.py
                     'station_status',  #d_rats\station_status.py



                     'wu',                   #d_rats\wu.py
                     'yencode',              #d_rats\yencode.py
                    
                     'geopy\\distance',       #d_rats\geopy\distance.py
                     'geopy\\geocoders',      #d_rats\geopy\geocoders.py
                     'geopy\\util',           #d_rats\geopy\util.py

                     'sessions\\base',        #d_rats\sessions\base.py
                     'sessions\\chat',        #d_rats\sessions\chat.py
                     'sessions\\control',     #d_rats\sessions\control.py
                     'sessions\\file',        #d_rats\sessions\file.py
                     'sessions\\form',        #d_rats\sessions\form.py

                     'sessions\\sniff',       #d_rats\sessions\sniff.py
                     'sessions\\sock',        #d_rats\sessions\sock.py
                     'sessions\\stateful',    #d_rats\sessions\stateful.py
                     'sessions\\stateless',   #d_rats\sessions\stateless.py

                     'ui\\main_common',       #d_rats\ui\main_common.py
                     ]

    date_time = datetime.now().strftime("%m/%d/%Y %H:%M:%S")  
    if (arg1 in modules2print):   
        print(date_time, arg1, *args)
    else:
        print(date_time, "x", arg1, *args)
