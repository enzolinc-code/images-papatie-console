Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
root = fso.GetParentFolderName(WScript.ScriptFullName)
python = root & "\.venv\Scripts\pythonw.exe"
If Not fso.FileExists(python) Then
 MsgBox "Run install first: setup.py / install launcher", 48, "Papapai Studio"
 WScript.Quit 1
End If
shell.CurrentDirectory = root
shell.Run Chr(34) & python & Chr(34) & " " & Chr(34) & root & "\launch.py" & Chr(34), 0, False
