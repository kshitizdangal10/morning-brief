' Launches start_dashboard.bat with its console window hidden - used by the
' "MorningBriefDashboard" Task Scheduler task to auto-start the dashboard
' server silently at login (the browser tab it opens is still visible;
' only the command-window is hidden). See CLAUDE.md for how this is wired up.
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run Chr(34) & "C:\Users\kshitiz D\Documents\Agent-Worksplace\start_dashboard.bat" & Chr(34), 0, False
