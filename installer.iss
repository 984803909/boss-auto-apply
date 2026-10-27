; Boss 直聘投递助手安装脚本。
; 编译： "C:\Users\98480\AppData\Local\Programs\Inno Setup 6\ISCC.exe" installer.iss
; 产物： dist\BossAutoApply-Setup-1.0.0.exe
;
; 只打包程序本身。config.yaml、data\applied.csv、data\edge_user_data
; 都是用户数据，第一次安装时放一份默认配置，升级和卸载都不碰。

#define AppVersion "1.0.0"

[Setup]
AppId={{7C2E9B14-5A61-4F0D-9C33-2B8E6D4A1F70}
AppName=Boss直聘投递助手
AppVersion={#AppVersion}
AppVerName=Boss直聘投递助手 {#AppVersion}
AppPublisher=BossAutoApply
VersionInfoVersion={#AppVersion}.0
VersionInfoDescription=Boss直聘投递助手安装程序
DefaultDirName={localappdata}\BossAutoApply
DefaultGroupName=Boss直聘投递助手
SetupIconFile=assets\app-icon.ico
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=BossAutoApply-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\BossAutoApply.exe
CloseApplications=yes
RestartApplications=no
; 程序启动时创建这个互斥体，安装和卸载前先确认它没在运行。
AppMutex=BossAutoApply

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加选项:"

[Files]
; 程序文件，每次安装都覆盖。
; Excludes 只写文件名：data\ 会连 _internal\data（城市数据）一起排除掉。
Source: "dist\BossAutoApply\*"; DestDir: "{app}"; Excludes: "config.yaml,applied.csv,category_log.csv"; Flags: ignoreversion recursesubdirs createallsubdirs
; 默认配置只在第一次安装时放一份，升级不覆盖用户改过的。
Source: "config.example.yaml"; DestDir: "{app}"; DestName: "config.yaml"; Flags: onlyifdoesntexist uninsneveruninstall

[Icons]
Name: "{group}\Boss直聘投递助手"; Filename: "{app}\BossAutoApply.exe"
Name: "{group}\卸载 Boss直聘投递助手"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Boss直聘投递助手"; Filename: "{app}\BossAutoApply.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\BossAutoApply.exe"; Description: "启动 Boss直聘投递助手"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; 只清掉卸载后剩下的空目录，config.yaml 和 data\ 一律保留。
Type: dirifempty; Name: "{app}"
