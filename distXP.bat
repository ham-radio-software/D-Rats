
echo building distibution

python setup.py py2exe > compile.log

echo copying files

xcopy  forms  .\dist\forms /s /d /y /f /i
xcopy  images .\dist\images /s /d /y /f /i
xcopy  locale .\dist\locale /s /d /y /f /i
xcopy  share  .\dist\share /s /d /y /f /i
xcopy  ui     .\dist\ui /s /d /y /f /i
xcopy  xp-specific-files\*.* dist /s /d /y /f /i

xcopy C:\Python27\Lib\site-packages\gtk-2.0\runtime\share\themes       dist\share\themes /s /d /y /f /i
xcopy C:\Python27\Lib\site-packages\gtk-2.0\runtime\lib                dist\lib /s /d /y /f /i
xcopy C:\Python27\lib\site-packages\gtk-2.0\runtime\bin\libxml2-2.dll  dist  /y

rem D-Rats also depends from these OS c:libraries, 
rem which in theory should be inovked from the OS and not distributed 
rem but by trial and errors need to be added to the package otherwise 
rem it will not work correctly
xcopy C:\WINDOWS\system32\ADVAPI32.dll  dist /y
xcopy C:\WINDOWS\system32\COMDLG32.dll  dist /y
xcopy C:\WINDOWS\system32\COMCTL32.dll  dist /y
xcopy C:\WINDOWS\system32\CRYPT32.dll   dist /y

xcopy C:\WINDOWS\system32\GDI32.dll     dist /y
xcopy C:\WINDOWS\system32\gdiplus.dll   dist /y

xcopy C:\WINDOWS\system32\KERNEL32.dll  dist /y

xcopy C:\WINDOWS\system32\MPR.dll       dist /y
xcopy C:\WINDOWS\system32\msvcrt.dll    dist /y
xcopy C:\WINDOWS\system32\MSIMG32.DLL   dist /y
xcopy C:\WINDOWS\system32\MSWSOCK.dll   dist /y


xcopy C:\WINDOWS\system32\OLE32.dll     dist /y
xcopy C:\WINDOWS\system32\OLEAUT32.dll  dist /y

xcopy C:\WINDOWS\system32\SHELL32.DLL   dist /y
xcopy C:\WINDOWS\system32\SHLWAPI.DLL   dist /y

xcopy C:\WINDOWS\system32\USER32.dll    dist /y
xcopy C:\WINDOWS\system32\USP10.DLL    dist /y
xcopy C:\WINDOWS\system32\VERSION.dll   dist /y
xcopy C:\WINDOWS\system32\WINMM.dll     dist /y
xcopy C:\WINDOWS\system32\WINSPOOL.DRV  dist /y


rem D-Rats also depends from these libraries, but shall not be distributed as otherwise will 
rem interfere with the ones already present in the user need to be invoked from OS 
rem xcopy C:\WINDOWS\system32\DNSAPI.DLL    dist /y
rem xcopy C:\WINDOWS\system32\IMM32.DLL     dist /y
rem xcopy C:\WINDOWS\system32\NETAPI32.dll  dist /y
rem xcopy C:\WINDOWS\system32\WS2_32.dll    dist /y
rem xcopy C:\WINDOWS\system32\WSOCK32.dll   dist /y

rem adding lzhuff_1.exe
xcopy .\libexec\lzhuf_1.exe .\dist\libexec\lzhuf_1.exe /y

pause

