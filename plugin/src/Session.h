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
    std::map<int, std::string> names() const;          // chop id -> file name
    juce::String nameOf (int chopId) const;

    // --- export
    juce::StringArray lastExportFiles;
    juce::File lastExportFolder;
    void exportAll();
    void startOver();
    // renders a chop into a temp WAV (named like the export) for dragging into a DAW
    juce::File renderForDrag (int chopId);

    // --- preview
    void preview (int chopId, bool loop = false);
    void stopPreview();
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
