; Inno Setup Script для VoiceTyping
; Скачать бесплатный компилятор Inno Setup: https://jrsoftware.org/isdl.php

#define MyAppName "VoiceTyping"
#define MyAppVersion "1.4.0"
#define MyAppPublisher "VoiceTyping"
#define MyAppURL "https://github.com/wesiks/VoiceTyping"
#define MyAppExeName "VoiceTyping.exe"
#define FeedbackEmail "fasok2010@gmail.com"

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
CloseApplications=yes
RestartApplications=no

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

[UninstallRun]
Filename: "{cmd}"; Parameters: "/C taskkill /F /IM VoiceTyping.exe /T"; Flags: runhidden; RunOnceId: "KillVoiceTyping"

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "VoiceTyping"; Flags: dontcreatekey uninsdeletevalue

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
Type: filesandordirs; Name: "{userappdata}\VoiceTyping"

[Code]
function InitializeUninstall(): Boolean;
var
  Form: TSetupForm;
  LblTitle, LblReason, LblComment: TLabel;
  ComboReason: TNewComboBox;
  MemoComment: TNewMemo;
  BtnSubmit, BtnSkip: TNewButton;
  WinHttpReq: Variant;
  Payload: String;
begin
  Result := True;
  Form := TSetupForm.Create(nil);
  try
    Form.ClientWidth := ScaleX(460);
    Form.ClientHeight := ScaleY(340);
    Form.Caption := 'Удаление VoiceTyping';
    Form.Position := poScreenCenter;

    LblTitle := TLabel.Create(Form);
    LblTitle.Parent := Form;
    LblTitle.Left := ScaleX(24);
    LblTitle.Top := ScaleY(18);
    LblTitle.Width := ScaleX(410);
    LblTitle.Caption := 'Пожалуйста, расскажите, почему вы удаляете VoiceTyping?';
    LblTitle.Font.Style := [fsBold];
    LblTitle.Font.Size := 10;

    LblReason := TLabel.Create(Form);
    LblReason.Parent := Form;
    LblReason.Left := ScaleX(24);
    LblReason.Top := ScaleY(52);
    LblReason.Caption := 'Основная причина:';

    ComboReason := TNewComboBox.Create(Form);
    ComboReason.Parent := Form;
    ComboReason.Left := ScaleX(24);
    ComboReason.Top := ScaleY(74);
    ComboReason.Width := ScaleX(410);
    ComboReason.Style := csDropDownList;
    ComboReason.Items.Add('Сложно настроить / непонятно как получить API-ключ');
    ComboReason.Items.Add('Ошибки или неточности при распознавании речи');
    ComboReason.Items.Add('Приложение зависает или нестабильно работает');
    ComboReason.Items.Add('Не хватает нужных функций и настроек');
    ComboReason.Items.Add('Временное удаление / переустановка');
    ComboReason.Items.Add('Другая причина');
    ComboReason.ItemIndex := 0;

    LblComment := TLabel.Create(Form);
    LblComment.Parent := Form;
    LblComment.Left := ScaleX(24);
    LblComment.Top := ScaleY(116);
    LblComment.Caption := 'Что нам улучшить? (любые замечания или пожелания):';

    MemoComment := TNewMemo.Create(Form);
    MemoComment.Parent := Form;
    MemoComment.Left := ScaleX(24);
    MemoComment.Top := ScaleY(138);
    MemoComment.Width := ScaleX(410);
    MemoComment.Height := ScaleY(120);

    BtnSubmit := TNewButton.Create(Form);
    BtnSubmit.Parent := Form;
    BtnSubmit.Left := ScaleX(180);
    BtnSubmit.Top := ScaleY(280);
    BtnSubmit.Width := ScaleX(155);
    BtnSubmit.Height := ScaleY(32);
    BtnSubmit.Caption := 'Отправить отзыв и удалить';
    BtnSubmit.ModalResult := mrOk;
    BtnSubmit.Default := True;

    BtnSkip := TNewButton.Create(Form);
    BtnSkip.Parent := Form;
    BtnSkip.Left := ScaleX(345);
    BtnSkip.Top := ScaleY(280);
    BtnSkip.Width := ScaleX(90);
    BtnSkip.Height := ScaleY(32);
    BtnSkip.Caption := 'Пропустить';
    BtnSkip.ModalResult := mrCancel;

    if Form.ShowModal() = mrOk then
    begin
      try
        Payload := '{"reason":"' + ComboReason.Text + '","comment":"' + MemoComment.Text + '","version":"' + '{#MyAppVersion}' + '"}';
        WinHttpReq := CreateOleObject('WinHttp.WinHttpRequest.5.1');
        WinHttpReq.Open('POST', 'https://formsubmit.co/ajax/' + '{#FeedbackEmail}', False);
        WinHttpReq.SetRequestHeader('Content-Type', 'application/json');
        WinHttpReq.SetTimeouts(2000, 2000, 3000, 3000);
        WinHttpReq.Send(Payload);
      except
      end;
    end;
  finally
    Form.Free();
  end;
end;
