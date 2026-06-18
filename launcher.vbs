' launcher.vbs for yt-dlp Convenient GUI
' Resolves pythonw.exe (venv first, then system PATH) and launches run.py silently.

Dim WshShell, FSO, AppDir, VenvPython, SysPython, Args

Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")

AppDir = FSO.GetParentFolderName(WScript.ScriptFullName)

' 1. Try venv pythonw first
VenvPython = FSO.BuildPath(AppDir, "venv\Scripts\pythonw.exe")
If FSO.FileExists(VenvPython) Then
    SysPython = VenvPython
Else
    ' 2. Fallback to system pythonw via PATH
    SysPython = "pythonw.exe"
End If

Args = """" & FSO.BuildPath(AppDir, "run.py") & """"

WshShell.CurrentDirectory = AppDir
WshShell.Run """" & SysPython & """ " & Args, 0, False