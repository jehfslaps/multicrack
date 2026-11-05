#include "ui/Pages.h"

#include "engine/Naming.h"

namespace xk::ui
{

std::shared_ptr<PeakCache> Context::peaks (int stemId)
{
    auto it = cache.find (stemId);
    if (it != cache.end())
        return it->second;
    for (auto& s : session.stems)
        if (s->id == stemId)
            return cache[stemId] = std::make_shared<PeakCache> (s);
    return nullptr;
}

namespace
{
struct StemCols { int num, name, len, kind, status, remove; };

StemCols stemCols (int width, bool narrow)
{
    StemCols c;
    c.num = narrow ? 30 : 40;
    c.len = narrow ? 0 : 72;
    c.kind = narrow ? 150 : 180;
    c.status = narrow ? 104 : 130;
    c.remove = narrow ? 44 : 70;
    c.name = juce::jmax (80, width - (c.num + c.len + c.kind + c.status + c.remove) - 12 * 5 - 24);
    return c;
}

juce::String fmtLen (double seconds)
{
    const int s = (int) seconds;   // whole seconds, like the desktop app
    return juce::String (s / 60) + ":" + juce::String (s % 60).paddedLeft ('0', 2);
}
} // namespace

// ------------------------------------------------------------------ row
class StemRow : public juce::Component
{
public:
    StemRow (LoadPage& p, int id) : page (p), stemId (id)
    {
        for (auto* c : { &num, &name, &len, &status })
            addAndMakeVisible (c);
        name.elide = true;
        status.elide = true;
        for (auto& k : stemKinds())
            kind.addItem (k.name, kind.getNumItems() + 1);
        kind.setTooltip ("What the AI thinks this file is. Change it if it's wrong.");
        kind.onChange = [this] {
            if (kind.getSelectedItemIndex() >= 0)
                page.ctx.session.setStemKind (stemId, kind.getText());
        };
        addAndMakeVisible (kind);
        remove.setTooltip ("Remove this file");
        remove.onClick = [this] { page.ctx.session.removeStem (stemId); };
        addAndMakeVisible (remove);
    }

    void update (int index, const Stem& st)
    {
        num.setText (juce::String (index + 1));
        name.setText (juce::String (st.name));
        len.setText (fmtLen (st.seconds()));
        int sel = -1;
        for (int i = 0; i < kind.getNumItems(); ++i)
            if (kind.getItemText (i) == juce::String (st.kind))
                sel = i;
        kind.setSelectedItemIndex (sel, juce::dontSendNotification);
        kind.setEnabled (st.mode != "skip" && ! page.ctx.session.busy());
        remove.setEnabled (! page.ctx.session.busy());
        status.setText (juce::String (st.status));
        const bool good = juce::String (st.status).endsWith ("chops");
        status.setColourKey (st.mode == "skip" ? "warn" : good ? "on_dark" : "on_dark_muted");
        status.setFontSpec (13.5f, good ? 500 : 400, 0.3f);
    }

    void resized() override
    {
        const auto c = stemCols (getWidth(), page.ctx.narrow);
        int x = 12;
        const int h = getHeight();
        num.setBounds (x, 0, c.num, h); x += c.num + 12;
        name.setBounds (x, 0, c.name, h); x += c.name + 12;
        len.setVisible (c.len > 0);
        if (c.len) { len.setBounds (x, 0, c.len, h); x += c.len + 12; }
        kind.setBounds (x, (h - H_SMALL) / 2, c.kind, H_SMALL); x += c.kind + 12;
        status.setBounds (x, 0, c.status, h); x += c.status + 12;
        remove.setBounds (x + (c.remove - H_SMALL) / 2, (h - H_SMALL) / 2, H_SMALL, H_SMALL);
    }

    void paint (juce::Graphics& g) override
    {
        g.setColour (C ("row_line"));
        g.drawLine (8, (float) getHeight() - 0.5f, (float) getWidth() - 8, (float) getHeight() - 0.5f, 1.0f);
    }

private:
    LoadPage& page;
    int stemId;
    Text num { "", "on_dark_muted", 13.5f, 400, 0.3f }, name { "", "on_dark", 13.5f, 400, 0.3f },
        len { "", "on_dark", 13.5f, 400, 0.3f }, status { "", "on_dark", 13.5f, 400, 0.3f };
    juce::ComboBox kind;
    HwButton remove { "", HwButton::danger };
};

// ------------------------------------------------------------------ page
LoadPage::LoadPage (Context& c, Chassis& chassis) : ctx (c)
{
    auto& s = ctx.session;
    for (auto* comp : std::initializer_list<juce::Component*> { &songMod, &dropMod, &stemsMod, &hintIcon, &hint, &footSep, &trough, &housing })
        addAndMakeVisible (comp);
    for (auto* comp : std::initializer_list<juce::Component*> { &capArtist, &artist, &capSong, &song, &capPrefix, &prefix, &prefixBtn,
                                                                 &capOut, &folder, &folderBtn, &changeFolder, &existsLamp, &existsText,
                                                                 &specSep, &capSpecs })
        songMod.addAndMakeVisible (comp);
    for (auto t : { "24-bit WAV", "Original sample rate", "Normalized -0.1 dB", "Light de-click", "Up to 3 variations",
                    "No tags embedded" })
        songMod.addAndMakeVisible (specs.add (new Text (juce::String::fromUTF8 ("\xe2\x80\xa2  ") + t, "on_dark_muted", 12.5f, 400, 0.2f)));
    specSep.vertical = false;
    artist.setTextToShowWhenEmpty ("e.g. Taylor Swift", C ("on_dark_dim"));
    song.setTextToShowWhenEmpty ("e.g. Style", C ("on_dark_dim"));
    prefix.setTooltip ("Every file name starts with this. Filled in from the artist and song; type to change it.");
    folder.setReadOnly (true);
    folder.applyFontToAllText (font (12.5f, 400, 0.2f));
    existsText.wrap = true;
    existsText.justification = juce::Justification::topLeft;
    artist.onTextChange = [this] { ctx.session.setSong (artist.getText(), song.getText()); };
    song.onTextChange = [this] { ctx.session.setSong (artist.getText(), song.getText()); };
    prefix.onTextChange = [this] { if (prefix.hasKeyboardFocus (false)) ctx.session.setPrefix (prefix.getText()); };
    prefixBtn.setTooltip ("Edit the prefix");
    prefixBtn.onClick = [this] { prefix.grabKeyboardFocus(); prefix.selectAll(); };
    auto pick = [this] {
        chooser = std::make_unique<juce::FileChooser> ("Choose where song folders go", ctx.session.baseDir);
        chooser->launchAsync (juce::FileBrowserComponent::openMode | juce::FileBrowserComponent::canSelectDirectories,
                              [this] (const juce::FileChooser& fc) {
                                  if (fc.getResult().isDirectory())
                                      ctx.session.setBaseDir (fc.getResult());
                              });
    };
    folderBtn.setTooltip ("Choose where song folders go");
    folderBtn.onClick = pick;
    changeFolder.onClick = pick;

    dropMod.addAndMakeVisible (drop);
    dropMod.addAndMakeVisible (browseFilesBtn);
    dropMod.addAndMakeVisible (browseFolderBtn);
    drop.onDrop = [this] (const juce::StringArray& f) { ctx.session.addFiles (f); };
    drop.onClick = [this] { browseFolder(); };
    browseFilesBtn.onClick = [this] { browseFiles(); };
    browseFolderBtn.onClick = [this] { browseFolder(); };

    stemsMod.addAndMakeVisible (stemsOutline);
    for (auto t : { "#", "File name", "Length", "AI detected", "Status", "Remove" })
        stemsOutline.addAndMakeVisible (heads.add (new Text (t, "header_text", 11, 600, 1.4f, true)));
    viewport.setViewedComponent (&rowsHolder, false);
    viewport.setScrollBarsShown (true, false);
    viewport.setScrollBarThickness (10);
    stemsOutline.addAndMakeVisible (viewport);
    empty.justification = juce::Justification::centred;
    stemsOutline.addAndMakeVisible (empty);

    hint.elide = true;
    housing.screws = true;
    housing.addAndMakeVisible (processBtn);
    processBtn.onClick = [this] {
        ctx.session.processAll();
    };
    chassis.addBus (&songMod, { { &dropMod, 0.5f }, { &stemsMod, 0.25f }, { &stemsMod, 0.7f } });
    juce::ignoreUnused (s);
    refresh();
}

LoadPage::~LoadPage() = default;

void LoadPage::filesDropped (const juce::StringArray& files, int, int)
{
    ctx.session.addFiles (files);
}

void LoadPage::browseFiles()
{
    chooser = std::make_unique<juce::FileChooser> ("Choose stems", ctx.session.baseDir,
                                                   "*.wav;*.wave;*.aif;*.aiff;*.flac;*.mp3;*.ogg;*.m4a;*.w64");
    chooser->launchAsync (juce::FileBrowserComponent::openMode | juce::FileBrowserComponent::canSelectFiles
                              | juce::FileBrowserComponent::canSelectMultipleItems,
                          [this] (const juce::FileChooser& fc) {
                              juce::StringArray paths;
                              for (auto& f : fc.getResults())
                                  paths.add (f.getFullPathName());
                              if (! paths.isEmpty())
                                  ctx.session.addFiles (paths);
                          });
}

void LoadPage::browseFolder()
{
    chooser = std::make_unique<juce::FileChooser> ("Choose a stem folder", ctx.session.baseDir);
    chooser->launchAsync (juce::FileBrowserComponent::openMode | juce::FileBrowserComponent::canSelectDirectories,
                          [this] (const juce::FileChooser& fc) {
                              if (fc.getResult().isDirectory())
                                  ctx.session.addFiles ({ fc.getResult().getFullPathName() });
                          });
}

void LoadPage::refresh()
{
    auto& s = ctx.session;
    if (! artist.hasKeyboardFocus (false) && artist.getText() != s.artist)
        artist.setText (s.artist, false);
    if (! song.hasKeyboardFocus (false) && song.getText() != s.song)
        song.setText (s.song, false);
    if (! prefix.hasKeyboardFocus (false) && prefix.getText() != s.prefix)
        prefix.setText (s.prefix, false);
    const auto out = s.outputFolder();
    folder.setText (out.getFullPathName(), false);
    folder.setCaretPosition (0);
    const bool exists = out.isDirectory();
    existsLamp.setVisible (exists);
    existsText.setText (exists ? "Folder exists. Numbering continues from the last file." : "");
    // rows
    while (rows.size() > (int) s.stems.size())
        rows.removeLast();
    while (rows.size() < (int) s.stems.size())
        rowsHolder.addAndMakeVisible (rows.add (new StemRow (*this, 0)));
    for (size_t i = 0; i < s.stems.size(); ++i)
    {
        // rebuild a row when the stem behind it changed
        auto* r = rows[(int) i];
        if (r->getProperties()["stem"] != juce::var (s.stems[i]->id))
        {
            rows.set ((int) i, new StemRow (*this, s.stems[i]->id), true);
            r = rows[(int) i];
            rowsHolder.addAndMakeVisible (r);
            r->getProperties().set ("stem", s.stems[i]->id);
        }
        r->update ((int) i, *s.stems[i]);
    }
    empty.setVisible (s.stems.empty());
    viewport.setVisible (! s.stems.empty());
    for (auto* h : heads)
        h->setVisible (! s.stems.empty());
    processBtn.setEnabled (! s.stems.empty() && ! s.busy());
    browseFilesBtn.setEnabled (! s.busy());
    browseFolderBtn.setEnabled (! s.busy());
    if (! s.busy())
    {
        hint.setText (s.error.isNotEmpty() ? s.error
                      : s.statusMessage.isNotEmpty() ? s.statusMessage
                                                     : "Tip: drag and drop stems or a folder, check the AI detection, then process.");
        hint.setColourKey (s.error.isNotEmpty() ? "warn" : "chassis_text");
        trough.set (0);
    }
    resized();
}

void LoadPage::setBusy (bool busy, const juce::String& msg, float frac)
{
    if (busy)
    {
        hint.setText (msg);
        hint.setColourKey ("chassis_text");
        trough.set (frac);
    }
}

void LoadPage::resized()
{
    auto r = getLocalBounds().withTrimmedTop (4);
    const bool narrow = ctx.narrow;
    // footer
    auto foot = r.removeFromBottom (78);
    r.removeFromBottom (12);
    auto fr = foot.withTrimmedLeft (6);
    const int procW = narrow ? 260 : 320;
    housing.setBounds (fr.removeFromRight (procW).withSizeKeepingCentre (procW, 76));
    processBtn.setBounds (housing.getLocalBounds().reduced (16, 12));
    fr.removeFromRight (14);
    hintIcon.setBounds (fr.removeFromLeft (22).withSizeKeepingCentre (22, 22));
    fr.removeFromLeft (14);
    const int troughW = juce::jmin (520, fr.getWidth() * 2 / 5);
    trough.setBounds (fr.removeFromRight (troughW).withSizeKeepingCentre (troughW, 24));
    fr.removeFromRight (14);
    footSep.setBounds (fr.removeFromRight (10).reduced (0, 12));
    fr.removeFromRight (14);
    hint.setBounds (fr);

    // song module
    const int leftW = narrow ? 284 : 340;
    songMod.setBounds (r.removeFromLeft (leftW));
    r.removeFromLeft (30);
    {
        auto c = songMod.content();
        int y = c.getY();
        auto place = [&] (juce::Component& comp, int h, int gapAfter) {
            comp.setBounds (c.getX(), y, c.getWidth(), h);
            y += h + gapAfter;
        };
        place (capArtist, 18, 4);
        place (artist, H_FIELD, 10);
        place (capSong, 18, 4);
        place (song, H_FIELD, 14);
        place (capPrefix, 18, 4);
        prefix.setBounds (c.getX(), y, c.getWidth() - H_FIELD - 6, H_FIELD);
        prefixBtn.setBounds (c.getRight() - H_FIELD, y, H_FIELD, H_FIELD);
        y += H_FIELD + 14;
        place (capOut, 18, 4);
        folder.setBounds (c.getX(), y, c.getWidth() - H_FIELD - 6, H_FIELD);
        folderBtn.setBounds (c.getRight() - H_FIELD, y, H_FIELD, H_FIELD);
        y += H_FIELD + 8;
        changeFolder.setBounds (c.getX(), y, changeFolder.widthFor (changeFolder.getButtonText()), H_SMALL);
        y += H_SMALL + 10;
        existsLamp.setBounds (c.getX() - 6, y - 4, 26, 26);
        existsText.setBounds (c.getX() + 22, y, c.getWidth() - 22, 52);
        y += 58;
        const bool showSpecs = ! ctx.shortH && y + 30 + 6 * 23 < c.getBottom();
        for (auto* comp : std::initializer_list<juce::Component*> { &specSep, &capSpecs })
            comp->setVisible (showSpecs);
        for (auto* t : specs)
            t->setVisible (showSpecs);
        if (showSpecs)
        {
            place (specSep, 10, 6);
            place (capSpecs, 18, 6);
            for (auto* t : specs)
                place (*t, 17, 6);
        }
    }

    // drop module
    dropMod.setBounds (r.removeFromTop (150));
    {
        auto c = dropMod.getLocalBounds().reduced (16, 14);
        const int bw = narrow ? 196 : 236;
        auto col = c.removeFromRight (bw);
        browseFilesBtn.setBounds (col.removeFromTop (H_KEY));
        col.removeFromTop (12);
        browseFolderBtn.setBounds (col.removeFromTop (H_KEY));
        c.removeFromRight (18);
        drop.setBounds (c);
    }
    r.removeFromTop (12);
    stemsMod.setBounds (r);
    stemsOutline.setBounds (stemsMod.content().withTrimmedTop (-4));
    {
        auto o = stemsOutline.getLocalBounds().reduced (4, 2);
        auto hr = o.removeFromTop (38);
        const auto cc = stemCols (o.getWidth() - 10, narrow);
        int x = hr.getX() + 12;
        const int widths[] = { cc.num, cc.name, cc.len, cc.kind, cc.status, cc.remove };
        for (int i = 0; i < heads.size(); ++i)
        {
            heads[i]->setVisible (widths[i] > 0 && ! ctx.session.stems.empty());
            if (i == 5)
                heads[i]->setText (narrow ? "" : "Remove");
            if (widths[i] > 0)
            {
                heads[i]->setBounds (x, hr.getY(), widths[i], hr.getHeight());
                x += widths[i] + 12;
            }
        }
        viewport.setBounds (o);
        empty.setBounds (stemsOutline.getLocalBounds());
        layoutRows();
    }
}

void LoadPage::layoutRows()
{
    const int w = viewport.getMaximumVisibleWidth();
    rowsHolder.setSize (w, 44 * rows.size());
    for (int i = 0; i < rows.size(); ++i)
        rows[i]->setBounds (0, i * 44, w, 44);
}

} // namespace xk::ui
