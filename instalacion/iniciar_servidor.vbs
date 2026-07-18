' Arranca el servidor PERNO TODO sin ventana visible.
' Usado por la tarea programada "PERNO TODO - Servidor" al iniciar sesión.
Dim fso, ws, raiz
Set fso = CreateObject("Scripting.FileSystemObject")
Set ws  = CreateObject("Wscript.Shell")
raiz = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
ws.CurrentDirectory = raiz
ws.Run """" & raiz & "\venv\Scripts\pythonw.exe"" """ & raiz & "\servidor.py""", 0, False
