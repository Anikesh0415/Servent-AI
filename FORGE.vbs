Set WshShell = CreateObject("WScript.Shell")
strPath = WshShell.CurrentDirectory & "\Start_FORGE_App.bat"
WshShell.Run Chr(34) & strPath & Chr(34), 0, False
Set WshShell = Nothing
