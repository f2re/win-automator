#ifndef AppVersion
  #define AppVersion "0.0.0-dev"
#endif
#ifndef SourceDir
  #define SourceDir "..\dist\WinAutomator"
#endif
#ifndef OutputDir
  #define OutputDir "..\dist"
#endif

[Setup]
AppId={{4C24900F-EDFD-4AF1-8B1C-8E12C878EE6A}
AppName=Win Automator
AppVersion={#AppVersion}
AppPublisher=f2re
AppPublisherURL=https://github.com/f2re/win-automator
AppSupportURL=https://github.com/f2re/win-automator/issues
AppUpdatesURL=https://github.com/f2re/win-automator/releases/latest
DefaultDirName={localappdata}\Programs\Win Automator
DefaultGroupName=Win Automator
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
MinVersion=6.1sp1
OutputDir={#OutputDir}
OutputBaseFilename=WinAutomator-{#AppVersion}-Setup-win-x64
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\WinAutomator.exe
VersionInfoCompany=f2re
VersionInfoDescription=Trainable Windows desktop automation
VersionInfoProductName=Win Automator
VersionInfoProductVersion={#AppVersion}

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Дополнительные ярлыки:"; Flags: unchecked

[Icons]
Name: "{autoprograms}\Win Automator"; Filename: "{app}\WinAutomator.exe"; WorkingDir: "{app}"
Name: "{autoprograms}\Win Automator — сбор отладки"; Filename: "{app}\WinAutomator.exe"; Parameters: "--debug-capture"; WorkingDir: "{app}"; Comment: "Записать диагностический пакет для разработчика"
Name: "{autodesktop}\Win Automator"; Filename: "{app}\WinAutomator.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\WinAutomator.exe"; Description: "Запустить Win Automator"; Flags: nowait postinstall skipifsilent
