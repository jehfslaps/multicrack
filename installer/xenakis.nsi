; Xenakis - Windows installer (NSIS 3, Modern UI 2)
; makensis -DVERSION=1.0 -DNUMVER=1.0.0.0 -DSTAGE=<folder> -DOUTFILE=<exe> xenakis.nsi
;   STAGE holds: Xenakis.exe, Xenakis.vst3\, Xenakis.clap, README.txt, licenses\
; Installs the desktop app, the VST3 and the CLAP plug-in (each one a tick box), an uninstaller,
; Start-menu and desktop shortcuts. Running it again updates in place (the app's own updater does
; exactly that). Your settings and chops are never touched.
Unicode true
Target amd64-unicode
ManifestDPIAware true
SetCompressor /SOLID lzma

!ifndef VERSION
  !define VERSION "1.0"
!endif
!ifndef NUMVER
  !define NUMVER "1.0.0.0"
!endif
!define APP "Xenakis"
!define PUBLISHER "slapworx"
!define UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\slapworx Xenakis"
!define UNINST_EXE "Uninstall Xenakis.exe"

Name "Xenakis ${VERSION}"
Caption "Xenakis ${VERSION} setup"
UninstallCaption "Uninstall Xenakis"
OutFile "${OUTFILE}"
InstallDir "$PROGRAMFILES64\slapworx\Xenakis"
RequestExecutionLevel admin
BrandingText "slapworx · slapworx.net"
VIProductVersion "${NUMVER}"
VIAddVersionKey "ProductName" "Xenakis"
VIAddVersionKey "CompanyName" "slapworx"
VIAddVersionKey "FileDescription" "Xenakis installer"
VIAddVersionKey "FileVersion" "${VERSION}"
VIAddVersionKey "ProductVersion" "${VERSION}"
VIAddVersionKey "LegalCopyright" "slapworx"

!include "MUI2.nsh"
!include "x64.nsh"
!include "LogicLib.nsh"
!include "Sections.nsh"

!define MUI_ICON "Xenakis.ico"
!define MUI_UNICON "Xenakis.ico"
!define MUI_WELCOMEFINISHPAGE_BITMAP "side.bmp"
!define MUI_UNWELCOMEFINISHPAGE_BITMAP "side.bmp"
!define MUI_HEADERIMAGE
!define MUI_HEADERIMAGE_RIGHT
!define MUI_HEADERIMAGE_BITMAP "header.bmp"
!define MUI_HEADERIMAGE_UNBITMAP "header.bmp"
!define MUI_ABORTWARNING

!define MUI_WELCOMEPAGE_TITLE "Xenakis ${VERSION}"
!define MUI_WELCOMEPAGE_TEXT "Chops stems and multitracks into clean, labeled one-shots and loops.$\r$\n$\r$\nThis installs:$\r$\n  •  the Xenakis desktop app$\r$\n  •  the Xenakis plug-in for your DAW (VST3 and CLAP)$\r$\n$\r$\nPlease close your DAW and Xenakis before you continue, so the files can be replaced."
Var FinishText

!insertmacro MUI_PAGE_WELCOME
!define MUI_COMPONENTSPAGE_TEXT_TOP "Tick what you want. If you're not sure, keep all three."
!insertmacro MUI_PAGE_COMPONENTS
!define MUI_PAGE_CUSTOMFUNCTION_PRE CheckRunning
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_TITLE "Xenakis is installed"
!define MUI_FINISHPAGE_TEXT "$FinishText"
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_TEXT "Open Xenakis now"
!define MUI_FINISHPAGE_RUN_FUNCTION LaunchApp
!define MUI_PAGE_CUSTOMFUNCTION_PRE FinishPre
!define MUI_PAGE_CUSTOMFUNCTION_SHOW FinishShow
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!define MUI_PAGE_CUSTOMFUNCTION_PRE un.CheckRunning
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

; ------------------------------------------------------------------ the parts (tick boxes)
Section "-checks"
  ${If} ${Silent}
    Call CheckRunning   ; (the pages, and their checks, are skipped in a silent install)
  ${EndIf}
SectionEnd

Section "-core"
  SetShellVarContext all
  SetOutPath "$INSTDIR"
  File "${STAGE}/README.txt"
  SetOutPath "$INSTDIR\licenses"
  File "${STAGE}/licenses/*.*"
  WriteUninstaller "$INSTDIR\${UNINST_EXE}"
  CreateDirectory "$SMPROGRAMS\slapworx"
  CreateShortcut "$SMPROGRAMS\slapworx\Uninstall Xenakis.lnk" "$INSTDIR\${UNINST_EXE}"
  CreateShortcut "$SMPROGRAMS\slapworx\Xenakis read me.lnk" "$INSTDIR\README.txt"
  WriteRegStr HKLM "${UNINST_KEY}" "DisplayName" "Xenakis (slapworx)"
  WriteRegStr HKLM "${UNINST_KEY}" "DisplayVersion" "${VERSION}"
  WriteRegStr HKLM "${UNINST_KEY}" "Publisher" "${PUBLISHER}"
  WriteRegStr HKLM "${UNINST_KEY}" "URLInfoAbout" "https://slapworx.net"
  WriteRegStr HKLM "${UNINST_KEY}" "DisplayIcon" "$INSTDIR\${UNINST_EXE}"
  WriteRegStr HKLM "${UNINST_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKLM "${UNINST_KEY}" "UninstallString" '"$INSTDIR\${UNINST_EXE}"'
  WriteRegStr HKLM "${UNINST_KEY}" "QuietUninstallString" '"$INSTDIR\${UNINST_EXE}" /S'
  WriteRegDWORD HKLM "${UNINST_KEY}" "NoModify" 1
  WriteRegDWORD HKLM "${UNINST_KEY}" "NoRepair" 1
SectionEnd

Section "Desktop app" SecApp
  SetShellVarContext all
  SetOutPath "$INSTDIR"
  File "${STAGE}/Xenakis.exe"
  Delete "$INSTDIR\Xenakis.exe.old"
  CreateShortcut "$SMPROGRAMS\slapworx\Xenakis.lnk" "$INSTDIR\Xenakis.exe"
  CreateShortcut "$DESKTOP\Xenakis.lnk" "$INSTDIR\Xenakis.exe"
  WriteRegDWORD HKLM "${UNINST_KEY}" "App" 1
SectionEnd

Section "VST3 plug-in" SecVST3
  ; a VST3 is a folder: replace the whole thing so no old files linger
  RMDir /r "$COMMONFILES64\VST3\Xenakis.vst3"
  SetOutPath "$COMMONFILES64\VST3"
  File /r "${STAGE}/Xenakis.vst3"
  WriteRegDWORD HKLM "${UNINST_KEY}" "VST3" 1
SectionEnd

Section "CLAP plug-in" SecCLAP
  SetOutPath "$COMMONFILES64\CLAP"
  File "${STAGE}/Xenakis.clap"
  WriteRegDWORD HKLM "${UNINST_KEY}" "CLAP" 1
SectionEnd

!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${SecApp} "Xenakis on its own: a window you open from the Start menu or desktop."
  !insertmacro MUI_DESCRIPTION_TEXT ${SecVST3} "The plug-in for FL Studio, Ableton Live, Studio One, Cubase, Reaper and almost every other DAW."
  !insertmacro MUI_DESCRIPTION_TEXT ${SecCLAP} "The same plug-in for DAWs that load CLAP (FL Studio 2024 and newer, Bitwig, Reaper). Fine to have both."
!insertmacro MUI_FUNCTION_DESCRIPTION_END

; ------------------------------------------------------------------ start up
Function .onInit
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP "Xenakis needs 64-bit Windows."
    Abort
  ${EndIf}
  SetRegView 64
  ; installing again (or updating): keep the same tick boxes as last time
  ClearErrors
  ReadRegStr $0 HKLM "${UNINST_KEY}" "DisplayVersion"
  ${IfNot} ${Errors}
    ReadRegDWORD $0 HKLM "${UNINST_KEY}" "App"
    ${If} $0 != 1
      !insertmacro UnselectSection ${SecApp}
    ${EndIf}
    ReadRegDWORD $0 HKLM "${UNINST_KEY}" "VST3"
    ${If} $0 != 1
      !insertmacro UnselectSection ${SecVST3}
    ${EndIf}
    ReadRegDWORD $0 HKLM "${UNINST_KEY}" "CLAP"
    ${If} $0 != 1
      !insertmacro UnselectSection ${SecCLAP}
    ${EndIf}
  ${EndIf}
FunctionEnd

Function .onSelChange
  ; at least one thing has to be ticked
  ${IfNot} ${SectionIsSelected} ${SecApp}
  ${AndIfNot} ${SectionIsSelected} ${SecVST3}
  ${AndIfNot} ${SectionIsSelected} ${SecCLAP}
    GetDlgItem $0 $HWNDPARENT 1
    EnableWindow $0 0
  ${Else}
    GetDlgItem $0 $HWNDPARENT 1
    EnableWindow $0 1
  ${EndIf}
FunctionEnd

; ------------------------------------------------------------------ is something still running?
; $R0 = tasklist filter (a program file name, may end in *), $R3 = text to look for in the list.
; Sets $R1 to 1 if it is running.
!macro _Daw UN EXE FIND LABEL
  StrCpy $R0 "${EXE}"
  StrCpy $R3 "${FIND}"
  Call ${UN}IsRunning
  ${If} $R1 == 1
  ${AndIf} $3 == ""
    StrCpy $3 "${LABEL}"
  ${EndIf}
!macroend

!macro _Checks UN
Function ${UN}IsRunning
  StrCpy $R1 0
  nsExec::ExecToStack '"$SYSDIR\tasklist.exe" /NH /FI "IMAGENAME eq $R0"'
  Pop $0
  Pop $1
  StrCmp $0 0 0 done
  ; look for $R3 anywhere in the list (StrCmp ignores upper/lower case)
  StrLen $4 $R3
  StrCpy $5 0
  next:
    StrCpy $6 $1 $4 $5
    StrCmp $6 "" done
    StrCmp $6 $R3 found
    IntOp $5 $5 + 1
    Goto next
  found:
    StrCpy $R1 1
  done:
FunctionEnd

; Gives Xenakis a few seconds to close (it closes itself when it starts an update), then asks.
; Then asks to close any DAW that may have the plug-in open.
Function ${UN}CheckRunning
  StrCpy $R2 0
  wait:
    StrCpy $R0 "Xenakis.exe"
    StrCpy $R3 "Xenakis.exe"
    Call ${UN}IsRunning
    ${If} $R1 == 1
      IntOp $R2 $R2 + 1
      ${If} $R2 < 10
        Sleep 1000
        Goto wait
      ${EndIf}
      MessageBox MB_RETRYCANCEL|MB_ICONEXCLAMATION "Xenakis is still open.$\r$\n$\r$\nClose it, then click Retry." /SD IDCANCEL IDRETRY wait
      Quit
    ${EndIf}
  daws:
    StrCpy $3 ""
    !insertmacro _Daw "${UN}" "FL64.exe" "FL64.exe" "FL Studio"
    !insertmacro _Daw "${UN}" "FL.exe" "FL.exe" "FL Studio"
    !insertmacro _Daw "${UN}" "Ableton Live*" "Ableton Live" "Ableton Live"
    !insertmacro _Daw "${UN}" "reaper.exe" "reaper.exe" "Reaper"
    !insertmacro _Daw "${UN}" "Bitwig Studio.exe" "Bitwig Studio.exe" "Bitwig Studio"
    !insertmacro _Daw "${UN}" "Studio One.exe" "Studio One.exe" "Studio One"
    !insertmacro _Daw "${UN}" "Cubase*" "Cubase" "Cubase"
    !insertmacro _Daw "${UN}" "Reason.exe" "Reason.exe" "Reason"
    ${If} $3 != ""
      MessageBox MB_ABORTRETRYIGNORE|MB_ICONEXCLAMATION "Please close $3 first, so the plug-in files can be replaced.$\r$\n$\r$\nRetry: I closed it.$\r$\nIgnore: carry on anyway." /SD IDIGNORE IDRETRY daws IDIGNORE done
      Quit
    ${EndIf}
  done:
FunctionEnd
!macroend
!insertmacro _Checks ""
!insertmacro _Checks "un."

; ------------------------------------------------------------------ the last page
Function FinishPre
  StrCpy $FinishText ""
  ${If} ${SectionIsSelected} ${SecVST3}
  ${OrIf} ${SectionIsSelected} ${SecCLAP}
    StrCpy $FinishText "Plug-in: open your DAW and scan for new plug-ins.$\r$\nFL Studio: Options > Manage plugins > Find installed plugins.$\r$\nXenakis shows up under slapworx.$\r$\n$\r$\n"
  ${EndIf}
  ${If} ${SectionIsSelected} ${SecApp}
    StrCpy $FinishText "$FinishTextDesktop app: it's on your desktop and in the Start menu (slapworx folder)."
  ${EndIf}
FunctionEnd

Function FinishShow
  ${IfNot} ${SectionIsSelected} ${SecApp}
    ShowWindow $mui.FinishPage.Run 0
    SendMessage $mui.FinishPage.Run ${BM_SETCHECK} ${BST_UNCHECKED} 0
  ${EndIf}
FunctionEnd

Function LaunchApp
  ; through Explorer, so Xenakis opens as you (not as administrator) and drag-and-drop into
  ; your DAW keeps working
  Exec '"$WINDIR\explorer.exe" "$INSTDIR\Xenakis.exe"'
FunctionEnd

; ------------------------------------------------------------------ uninstall
Function un.onInit
  SetRegView 64
FunctionEnd

Section "Uninstall"
  SetShellVarContext all
  ${If} ${Silent}
    Call un.CheckRunning
  ${EndIf}
  RMDir /r "$COMMONFILES64\VST3\Xenakis.vst3"
  Delete "$COMMONFILES64\CLAP\Xenakis.clap"
  Delete "$DESKTOP\Xenakis.lnk"
  Delete "$SMPROGRAMS\slapworx\Xenakis.lnk"
  Delete "$SMPROGRAMS\slapworx\Xenakis read me.lnk"
  Delete "$SMPROGRAMS\slapworx\Uninstall Xenakis.lnk"
  RMDir "$SMPROGRAMS\slapworx"
  Delete "$INSTDIR\Xenakis.exe"
  Delete "$INSTDIR\Xenakis.exe.old"
  Delete "$INSTDIR\README.txt"
  RMDir /r "$INSTDIR\licenses"
  Delete "$INSTDIR\${UNINST_EXE}"
  RMDir "$INSTDIR"
  RMDir "$PROGRAMFILES64\slapworx"
  DeleteRegKey HKLM "${UNINST_KEY}"
  ; your settings and the samples you exported are left alone
SectionEnd
