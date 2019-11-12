# serialtool
a simple serial tool

[about conf file]

This is a ini format file actually.
1. Above section of shortcuts, it's all about logging used in script to debug code.
2. shortcuts use a "key:value" format. Hopefully one key should be unique among the other keys. 

[how to use]

To use it, a execution program should be create first using pyinstaller.

e.g. pyinstaller --onefile --windowed -i favicon.icon serialtool.py
