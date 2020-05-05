@echo off

set dest=%APPDATA%\D-RATS\Form_Templates

mkdir "%dest%"

echo Copying default form templates...
xcopy forms\*.xml "%dest%" /-Y


echo Copying default form stylesheets...
xcopy forms\*.xsl "%dest%" /-Y

echo Complete
pause