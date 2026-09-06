; Inno Setup Script для VoiceTyping
; Скачать бесплатный компилятор Inno Setup: https://jrsoftware.org/isdl.php

#define MyAppName "VoiceTyping"
#define MyAppVersion "1.3.0"
#define MyAppPublisher "VoiceTyping"
#define MyAppURL "https://github.com/wesiks/VoiceTyping"
#define MyAppExeName "VoiceTyping.exe"

[Setup]
AppId={{D3F9A1B2-56C7-498A-B871-38A2B9C89999}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DisableProgramGroupPage=yes
OutputDir=dist\installer
OutputBaseFilename=VoiceTyping_Setup
SetupIconFile=app.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "autostart"; Description: "Запускать приложение вместе с Windows"; GroupDescription: "Автозагрузка:"

[Files]
Source: "dist\VoiceTyping\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\VoiceTyping\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; WorkingDir: "{app}"
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: autostart; WorkingDir: "{app}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent
