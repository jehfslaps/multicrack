// The three pages: Load, Review, Export.
#pragma once

#include "PreviewPlayer.h"
#include "Session.h"
#include "ui/Waveforms.h"
#include "ui/Widgets.h"

#include <map>
#include <memory>

namespace xk::ui
{

// What the pages share: the session, page switching and cached waveforms.
struct Context
{
    explicit Context (Session& s) : session (s) {}
    Session& session;
    std::function<void (int)> go;                    // 0 load, 1 review, 2 export
    std::function<void (const juce::String&)> status;
    bool narrow = false, shortH = false;
    std::shared_ptr<PeakCache> peaks (int stemId);
    void forgetPeaks() { cache.clear(); }

private:
    std::map<int, std::shared_ptr<PeakCache>> cache;
};

// ------------------------------------------------------------------- load
class StemRow;

class LoadPage : public juce::Component, public juce::FileDragAndDropTarget
{
public:
    explicit LoadPage (Context& ctx, Chassis& chassis);
    ~LoadPage() override;
    void refresh();                 // after the session changed
    void setBusy (bool busy, const juce::String& msg, float frac);
    void resized() override;
    bool isInterestedInFileDrag (const juce::StringArray&) override { return true; }
    void filesDropped (const juce::StringArray& files, int, int) override;
    void browseFiles();
    void browseFolder();

private:
    void layoutRows();
    Context& ctx;
    Module songMod { "Song", true }, dropMod, stemsMod { "Stem list" };
    Text capArtist { "Artist", "on_dark_muted", 11, 500, 1.6f, true }, capSong { "Song", "on_dark_muted", 11, 500, 1.6f, true },
        capPrefix { "Prefix", "on_dark_muted", 11, 500, 1.6f, true }, capOut { "Output path", "on_dark_muted", 11, 500, 1.6f, true },
        existsText { "", "ok", 12.5f, 400, 0.2f }, capSpecs { "Output specs", "on_dark_muted", 11, 500, 1.6f, true };
    Field artist, song, prefix, folder;
    HwButton prefixBtn { "", HwButton::icon, "pencil" }, folderBtn { "", HwButton::icon, "folder" },
        changeFolder { "Change location", HwButton::dark, {}, false, 11.5f };
    Lamp existsLamp;
    Separator specSep;
    juce::OwnedArray<Text> specs;
    DropBay drop;
    HwButton browseFilesBtn { "Browse files", HwButton::dark, "file", false, 12.5f },
        browseFolderBtn { "Browse folder", HwButton::dark, "folder", false, 12.5f };
    Outline stemsOutline;
    juce::OwnedArray<Text> heads;
    juce::Viewport viewport;
    juce::Component rowsHolder;
    juce::OwnedArray<StemRow> rows;
    Text empty { juce::String::fromUTF8 ("NO FILES YET  ·  DROP A STEM FOLDER ABOVE TO GET STARTED"), "on_dark_dim", 12.5f, 500, 2.0f };
    IconLabel hintIcon { "bulb", "chassis_text" };
    Text hint { "", "chassis_text", 11.5f, 500, 1.2f, true };
    Separator footSep;
    Trough trough;
    Recess housing;
    HwButton processBtn { "Process all", HwButton::red, {}, true, 16.0f };
    std::unique_ptr<juce::FileChooser> chooser;
    friend class StemRow;
};

// ----------------------------------------------------------------- review
class ChopRow;
class GroupRow;

class ReviewPage : public juce::Component, public juce::KeyListener
{
public:
    explicit ReviewPage (Context& ctx);
    ~ReviewPage() override;
    void refresh();                         // rebuild the list after the session changed
    void tick();                            // playhead (30 Hz)
    void resized() override;
    bool keyPressed (const juce::KeyPress&, juce::Component*) override;
    bool keyPressed (const juce::KeyPress& k) override { return keyPressed (k, this); }
    void select (int chopId, bool play);
    void startDrag (int chopId);
    void mouseDrag (const juce::MouseEvent&) override;   // from the "Drag into your DAW" pad
    void mouseUp (const juce::MouseEvent&) override { padDragged = false; }
    int selected = -1;

private:
    void updateHeader();
    void updateEditor();
    void applyTexts();
    void moveSelection (int delta);
    Context& ctx;
    Module head;
    Text count { "", "on_dark", 21, 600, 2.2f };
    LedMeter meter;
    HwButton approveAll { "Approve all", HwButton::key, "check" }, exportBtn { "Export", HwButton::red, "export" };
    Module editorMod, listMod;
    PanelSplitter split { editorMod, listMod, 0.47f };
    Text edName { "", "on_dark", 15, 500, 0.6f };
    Tile flagTile;
    IconLabel flagIcon { "bulb", "on_dark_muted" };
    Text flagText { "", "on_dark_muted", 12.5f, 500, 0.3f };
    Lcd readout { "", "", 13.5f };
    ChopView view;
    Tile transport;
    HwButton playBtn { "", HwButton::key, "play" }, stopBtn { "", HwButton::key, "stop" };
    LedToggle loopBtn { "Loop", true, "loop" };
    HwButton dragBtn { "Drag into your DAW", HwButton::dark, "drag", false, 11.5f };
    Text dragHint { "Or drag any row below. Arrow keys play the next / previous chop, A approves.", "on_dark_muted", 11.5f, 400, 0.3f };
    juce::OwnedArray<Text> cols;
    juce::Viewport viewport;
    juce::Component rowsHolder;
    juce::OwnedArray<juce::Component> rows;       // GroupRow and ChopRow in order
    std::map<int, ChopRow*> rowById;
    Text empty { juce::String::fromUTF8 ("NOTHING TO REVIEW YET  ·  LOAD STEMS AND PRESS PROCESS ALL"), "on_dark_dim", 12.5f, 500, 2.0f };
    int lastChopCount = -1;
    bool padDragged = false;
    friend class ChopRow;
    friend class GroupRow;
};

// ----------------------------------------------------------------- export
class ExportPage : public juce::Component, private juce::ListBoxModel
{
public:
    explicit ExportPage (Context& ctx);
    void refresh();
    void resized() override;

private:
    int getNumRows() override { return files.size(); }
    void paintListBoxItem (int row, juce::Graphics&, int w, int h, bool selected) override;
    Context& ctx;
    Module box { "Export" };
    Lamp lamp;
    Text title { "NOTHING EXPORTED YET", "on_dark", 22, 600, 2.4f };
    Field path;
    Outline outline;
    juce::ListBox list;
    Text specs { juce::String::fromUTF8 ("24-bit WAV  ·  original sample rate  ·  normalized -0.1 dB  ·  de-clicked  ·  no tags embedded"),
                 "on_dark_muted", 11, 500, 1.3f, true };
    HwButton again { "Chop another song", HwButton::dark }, openBtn { "Open folder", HwButton::key, "folder" };
    juce::StringArray files;
};

} // namespace xk::ui
