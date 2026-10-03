' Starts SleekKeys with no console window. Stop it from the settings page ("Quit SleekKeys") or run stop.bat.
Set sh = CreateObject("WScript.Shell")
dir = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))
sh.CurrentDirectory = dir
sh.Run "pythonw """ & dir & "sleekkeys.py""", 0, False
