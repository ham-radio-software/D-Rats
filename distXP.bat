
echo building distibution

python setup.py py2exe > dist_0.3.5.log

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

xcopy C:\WINDOWS\system32\USP10.DLL    dist /y
xcopy C:\WINDOWS\system32\OLEAUT32.dll  dist /y
xcopy C:\WINDOWS\system32\USER32.dll    dist /y
xcopy C:\WINDOWS\system32\IMM32.DLL     dist /y
xcopy C:\WINDOWS\system32\MPR.dll       dist /y
xcopy C:\WINDOWS\system32\SHLWAPI.DLL   dist /y
xcopy C:\WINDOWS\system32\ADVAPI32.dll  dist /y
xcopy C:\WINDOWS\system32\msvcrt.dll    dist /y
xcopy C:\WINDOWS\system32\WS2_32.dll    dist /y
xcopy C:\WINDOWS\system32\GDI32.dll     dist /y
xcopy C:\WINDOWS\system32\gdiplus.dll   dist /y
xcopy C:\WINDOWS\system32\NETAPI32.dll  dist /y
xcopy C:\WINDOWS\system32\WINMM.dll     dist /y
xcopy C:\WINDOWS\system32\CRYPT32.dll   dist /y
xcopy C:\WINDOWS\system32\KERNEL32.dll  dist /y
xcopy C:\WINDOWS\system32\MSIMG32.DLL   dist /y
xcopy C:\WINDOWS\system32\MSWSOCK.dll   dist /y
xcopy C:\WINDOWS\system32\WSOCK32.dll   dist /y
xcopy C:\WINDOWS\system32\DNSAPI.DLL    dist /y
xcopy C:\WINDOWS\system32\VERSION.dll   dist /y
xcopy C:\WINDOWS\system32\OLE32.dll     dist /y
xcopy C:\WINDOWS\system32\SHELL32.DLL   dist /y
xcopy C:\WINDOWS\system32\COMDLG32.dll  dist /y
xcopy C:\WINDOWS\system32\COMCTL32.dll  dist /y
xcopy C:\WINDOWS\system32\WINSPOOL.DRV  dist /y



pause

