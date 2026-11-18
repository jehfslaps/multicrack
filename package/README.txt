Xenakis  -  stem chopper  -  by slapworx
version 1.0  -  Windows 10 / 11, 64-bit  -  desktop app + plug-in (VST3 + CLAP)
slapworx.net


WHAT Xenakis IS
---------------
Xenakis chops stems and multitracks into clean, labeled one-shots and loops.
Drop in a song's stems, press Process all, listen through every chop, keep
the good ones, and export. Every file is named and sorted for you, like
TS_Style_Kick_01.wav.

- KNOWS WHAT EACH STEM IS. Kick, snare, hats, drum loops, FX, vocals,
  guitar, synth... from the file name, and a built-in sound-recognition
  model listens when the name is unclear.
- DRUMS: up to 3 distinct hits per sound, plus one loop per groove
  (2, 4, 8 or 16 bars) with every hit chopped out of it.
- FX, VOCALS, MELODIC PARTS: impacts, risers, adlibs, phrases, stabs and
  chords, each with its full tail.
- REVIEW: play, trim, fade, reverse, change the type and approve each chop.
- OUTPUT: 24-bit WAV at the original sample rate, normalized to -0.1 dB,
  one folder per song. Nothing is ever overwritten.

Two ways to use it:
  Desktop app   A window of its own (Start menu or desktop: Xenakis).
  Plug-in       Inside your DAW (VST3 or CLAP). Drag chops straight from the
                list into your project.


INSTALL
-------
1. Close your DAW (and Xenakis, if it's open).
2. Double-click "Install Xenakis.exe".
   If Windows says "Windows protected your PC", click More info > Run anyway.
   The picture "Windows warning - how to install.png" shows where to click.
3. Keep all three ticked (Desktop app, VST3 plug-in, CLAP plug-in), or untick
   what you don't need > Install.
4. Plug-in: open your DAW and scan for new plug-ins.
     FL Studio:     Options > Manage plugins > Find installed plugins
     Ableton Live:  Settings > Plug-ins > Rescan
     Reaper:        Options > Preferences > Plug-ins > VST / CLAP > Re-scan
   Xenakis shows up under slapworx. Load it as an effect on any mixer track.

Where it goes:
  Desktop app   C:\Program Files\slapworx\Xenakis\Xenakis.exe
  VST3          C:\Program Files\Common Files\VST3\Xenakis.vst3
  CLAP          C:\Program Files\Common Files\CLAP\Xenakis.clap

Updates: the desktop app checks when it starts. Click Update and it runs the
new installer for you (Windows asks for permission). Or run a newer
"Install Xenakis.exe" over the top: your settings are kept.

Uninstall: Settings > Apps > Installed apps > Xenakis (slapworx) > Uninstall.
Your settings and the samples you exported are left alone.

Plug-in by hand instead: copy what's in "manual install" to the VST3 and
CLAP folders above (right-click the zip > Properties > Unblock first).


HOW IT WORKS
------------
1. LOAD     Type the artist and song, then drop in the stems (or the whole
            stem folder). Change any stem's type before processing if it
            guessed wrong.
2. REVIEW   Every chop with its waveform. Play it, fix the type, approve it.
            When everything is green, export.
3. EXPORT   Desktop app: one folder on your Desktop, for example
            "Taylor Swift - Style (Chopped)". Plug-in: drag chops from the
            list into your project, or export them all to a folder.


KEYS ON THE REVIEW PAGE (desktop app)
-------------------------------------
Up / Down    move through the chops and play each one
Space        play / stop
A            approve and jump to the next chop
Enter        approve / un-approve
Delete       delete the chop
Ctrl+D       clone the chop
Ctrl+Z / Y   undo / redo
R            reverse on / off
L            loop playback on / off
S            snap on / off


THE PLUG-IN
-----------
Load it as an effect on any track. Chops you audition play through that
track's output; the "Preview level" parameter sets how loud.
This version of the plug-in does loading, chopping, the review list
(play, approve, change the type, delete, drag out) and export. The trim
editor, fades, undo and the sound-recognition model are in the desktop app
for now and come to the plug-in next.
Menu (top right) > UI size: Small, Medium or Large, in both.


KNOWN LIMITS
------------
- Windows only for now. Mac is coming.
- The installer isn't signed with a paid certificate yet, so Windows shows
  its "protected your PC" warning the first time (see the picture).


CREDITS
-------
Named for Iannis Xenakis, who built music and buildings out of straight
lines. Built with JUCE, CLAP, Qt for Python, sherpa-onnx and the CED-mini
model; font IBM Plex Mono (SIL Open Font License). Details and licenses are
in the licenses folder.
