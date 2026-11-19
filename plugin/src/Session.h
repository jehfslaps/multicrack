// Everything the plug-in knows about the current song: stems, chops, names, settings.
// Lives in the processor, so closing the plug-in window loses nothing.
#pragma once

#include "engine/Model.h"

#include <juce_audio_formats/juce_audio_formats.h>
#include <juce_data_structures/juce_data_structures.h>
#include <juce_events/juce_events.h>

#include <functional>
#include <map>
#include <optional>
#include <vector>

namespace xk
{

class PreviewPlayer;

// Per-user settings shared by every Xenakis instance (theme, UI size, output folder ...).
class Settings
{
public:
    Settings();
    juce::PropertiesFile& file() { return *props; }
    juce::String get (const juce::String& key, const juce::String& fallback = {}) { return props->getValue (key, fallback); }
    void set (const juce::String& key, const juce::var& v) { props->setValue (key, v); }   // saved shortly after
private:
    std::unique_ptr<juce::PropertiesFile> props;
};

class Session : public juce::ChangeBroadcaster
{
public:
    explicit Session (PreviewPlayer& player);
    ~Session() override;

    // --- song details
    juce::String artist, song, prefix;
    bool prefixEdited = false;
    juce::File baseDir;
    void setSong (const juce::String& artistName, const juce::String& songName);
    void setPrefix (const juce::String& p);
    juce::String effectivePrefix() const;
    juce::File outputFolder() const;
    void setBaseDir (const juce::File& dir);

    // --- stems
    std::vector<StemPtr> stems;
    std::optional<Song> songGrid;
    void addFiles (const juce::StringArray& paths);
    void removeStem (int stemId);
    void setStemKind (int stemId, const juce::String& kind);
    Stem* stemById (int id) const;

    // --- chops
    std::vector<Chop> chops;
    bool processed = false;
    void processAll();
    Chop* chopById (int id);
    void setApproved (int chopId, bool on);
    void approveAll();
    void approveStem (int stemId);
    void removeStemChops (int stemId);
    void deleteChop (int chopId);
    void setLabel (int chopId, const juce::String& label);
    int approvedCount() const;

    // --- editing (every change can be undone)
    void checkpoint();                                   // remember the chops before a change
    bool undo();
    bool redo();
    bool canUndo() const { return ! undoStack.empty(); }
    bool canRedo() const { return ! redoStack.empty(); }
    void setTrim (int chopId, int start, int end, bool remember = true);
    void resetTrim (int chopId);
    int cloneChop (int chopId);                          // returns the copy's id (placed right after)
    // your own chop: starts at the sound nearest `at` (looking back a little, for when you press
    // N just after hearing it), ends where the next sound starts. Returns its id.
    int newChopAt (int stemId, int at, int afterChopId);
    void setFades (int chopId, double inMs, double outMs, bool remember = true);   // < 0 = automatic
    void setGain (int chopId, double db, bool remember = true);
    void setReverse (int chopId, bool on);
    void setSeam (int chopId, bool on);
    int magnet (int stemId, int s);                      // start dropped near a hit -> its attack
    int snapToBar (int stemId, int s) const;             // loops: nearest bar line
    int toExportCount() const;                          // approved and not saved yet
    int savedCount() const;
    std::map<int, std::string> names() const;          // chop id -> file name
    juce::String nameOf (int chopId) const;

    // --- export
    juce::StringArray lastExportFiles;
    juce::File lastExportFolder;
    int exportCount = 0;                                // goes up after every export
    void exportAll();
    void startOver();
    // renders a chop into a temp WAV (named like the export) for dragging into a DAW
    juce::File renderForDrag (int chopId);

    // --- preview
    void preview (int chopId, bool loop = false);
    void previewStem (int stemId, int fromSample);       // the whole stem from a spot, until stopped
    void stopPreview();
    static constexpr int STEM_PLAY = 1 << 28;            // player ids at or above this play a stem
    int stemPlayFrom = 0, stemPlayLen = 0;               // the part of the stem being played
    PreviewPlayer& player;

    // --- work in the background
    bool busy() const { return busy_; }
    // progress of the background job (any thread may set it; the UI polls it)
    void setProgress (const juce::String& msg, float frac);
    std::pair<juce::String, float> getProgress() const;
    juce::String statusMessage;          // last result, shown in the status LCD / hint
    juce::String error;

    Settings& settings() { return *settings_; }
    juce::AudioFormatManager formats;

    std::function<void (const juce::String&)> onNotice;   // short messages for the UI

private:
    void run (const juce::String& message, std::function<std::function<void()> (std::function<bool()> cancelled)> job);
    void changed();
    void edited();                                       // chop list changed by an edit
    void keepSaved (std::vector<Chop>& restored) const;
    std::vector<std::vector<Chop>> undoStack, redoStack;
    bool busy_ = false;
    juce::CriticalSection progressLock;
    juce::String busyMessage;
    float progress = 0.0f;
    std::atomic<bool> cancel_ { false };
    juce::ThreadPool pool { 1 };
    juce::SharedResourcePointer<Settings> settings_;
    JUCE_DECLARE_WEAK_REFERENCEABLE (Session)
};

} // namespace xk
