
from __future__ import print_function
from datetime import datetime




def printlog(arg1, *args):
#List of modules
    modules2print = ['D-Rats',           #main program
                     'Chat',             # sessions\chat.py 
                     'Comm',             # comm.py
                     'Config',           # config.py
                     'Gps',              # d_rats\gps.py
                     'Geocode',          # geocode.py      
                     'Mainapp',          # mainapp.py'
                     'Mainchat',         # d_rats\ui\main_chat.py
                     'Mainfiles',        # d_rats\ui\main_files.py
                     'MainStation',      # d_rats\ui\main_stations.py                                        
                     'Mainwind',         # mainwindow.py'
                     'Mapdisplay',       # d_rats\mapdisplay.py                     
                     'Msgrouting',       # d_rats\msgrouting.py
                     'Qst',              # d_rats\qst.py
                     'RPC',              # d_rats\sessions\rpc.py                     
                     'Sessionmgr',       # Sessionmanager.py                     
                     'Transport',        # transport.py'     
                     'version',          # d_rats\version.py                     

                     #TO DO

                     'Agw',         #d_rats\agw.py
                     'Ax25',         #d_rats\ax25.py
                     'Callsigns',    #d_rats\callsigns.py
                     'Cap',          #d_rats\cap.py
                     'Comm',         #d_rats\comm.py
                     'config',       #d_rats\config.py
                     'config_tips',  #d_rats\config_tips.py
                     'ddt2',         #d_rats\ddt2.py
                     'debug',        #d_rats\debug.py
                     'dplatform',    #d_rats\dplatform.py
                     'emailgw',      #d_rats\emailgw.py
                     'formbuilder',  #d_rats\formbuilder.py
                     'formgui',      #d_rats\formgui.py
                     'geocode_ui',   #d_rats\geocode_ui.py

                     'image',        #d_rats\image.py
                     'inputdialog',  #d_rats\inputdialog.py
                     'mailsrv',      #d_rats\mailsrv.py
                     'map_sources',  #d_rats\map_sources.py
                     'map_source_editor',        #d_rats\map_source_editor.py
                     'miscwidgets',  #d_rats\miscwidgets.py

                     'platform',     #d_rats\platform.py
                     'pluginsrv',    #d_rats\pluginsrv.py                   
                     'reqobject',            #d_rats\reqobject.py
                     'sessionmgr',           #d_rats\sessionmgr.py
                     'session_coordinator',  #d_rats\session_coordinator.py
                     'signals',              #d_rats\signals.py
                     'spell',                #d_rats\spell.py
                     'station_status',       #d_rats\station_status.py
                     'subst',                #d_rats\subst.py
                     'transport',            #d_rats\transport.py
                     'utils',                #d_rats\utils.py

                     'wl2k',                 #d_rats\wl2k.py
                     'wu',                   #d_rats\wu.py
                     'yencode',              #d_rats\yencode.py
                    
                     'geopy\distance',       #d_rats\geopy\distance.py
                     'geopy\geocoders',      #d_rats\geopy\geocoders.py
                     'geopy\util',           #d_rats\geopy\util.py

                     'sessions\base',        #d_rats\sessions\base.py
                     'sessions\chat',        #d_rats\sessions\chat.py
                     'sessions\control',     #d_rats\sessions\control.py
                     'sessions\file',        #d_rats\sessions\file.py
                     'sessions\form',        #d_rats\sessions\form.py

                     'sessions\sniff',       #d_rats\sessions\sniff.py
                     'sessions\sock',        #d_rats\sessions\sock.py
                     'sessions\stateful',    #d_rats\sessions\stateful.py
                     'sessions\stateless',   #d_rats\sessions\stateless.py
                     'ui\conntest',          #d_rats\ui\conntest.py
                     'ui\main_common',       #d_rats\ui\main_common.py
                     'ui\main_events',       #d_rats\ui\main_events.py
                     
                     'ui\main_messages',     #d_rats\ui\main_messages.py
                     
                      ]
    now = datetime.now()
    date_time = datetime.now().strftime("%m/%d/%Y %H:%M:%S")  
    if (arg1 in modules2print):   
        print(date_time, arg1, *args)
        
    else:
        print(date_time, "x", arg1, *args)
        
    