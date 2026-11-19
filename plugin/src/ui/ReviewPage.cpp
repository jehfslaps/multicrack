#include "ui/Pages.h"

#include "engine/Render.h"

namespace xk::ui
{

namespace
{
struct ChopCols { int grip, num, play, name, dur, type, approve, del; };

ChopCols chopCols (bool narrow)
{
    if (narrow)
        return { 16, 26, 40, 206, 80, 132, 116, 34 };
    return { 18, 30, 40, 292, 92, 164, 142, 36 };
}

constexpr int ROW_H = 60, GROUP_H = 44, GAP = 12;

juce::String fmtDur (int samples, int sr)
{
    const double t = samples / (double) juce::jmax (1, sr);
    const int m = (int) (t / 60);
    return juce::String (m) + ":" + juce::String (t - 60 * m, 3).paddedLeft ('0', 6);
}

bool isWarning (const std::string& flag)
{
    return ! flag.empty() && flag.rfind ("AI suggestion", 0) != 0;
}

void fillLabelCombo (juce::ComboBox& cb)
{
    int id = 1;
    for (auto& grp : labelGroups())
    {
        cb.addSectionHeading (grp.name);
        for (auto& l : grp.labels)
            cb.addItem (l, id++);
    }
}

void setComboText (juce::ComboBox& cb, const juce::String& t)
{
    for (int i = 0; i < cb.getNumItems(); ++i)
        if (cb.getItemText (i) == t)
        {
            cb.setSelectedItemIndex (i, juce::dontSendNotification);
            return;
        }
    cb.setText (t, juce::dontSendNotification);
}
} // namespace

// ================================================================= group row
class GroupRow : public juce::Component
{
public:
    GroupRow (ReviewPage& p, const Stem& st, int count) : page (p), stemId (st.id)
    {
        name.setText (juce::String (st.name));
        sub.setText (juce::String (st.kind) + juce::String::fromUTF8 ("  \xc2\xb7  ") + juce::String (count) + " chop"
                     + (count == 1 ? "" : "s"));
        addAndMakeVisible (name);
        addAndMakeVisible (sub);
        approve.setTooltip ("Approve every chop from this stem");
        approve.onClick = [this] { page.ctx.session.approveStem (stemId); };
        removeAll.setTooltip ("Remove every chop from this stem");
        removeAll.onClick = [this] { page.ctx.session.removeStemChops (stemId); };
        addAndMakeVisible (approve);
        addAndMakeVisible (removeAll);
    }
    void resized() override
    {
        auto r = getLocalBounds().reduced (16, 0);
        const int bh = H_SMALL;
        removeAll.setBounds (r.removeFromRight (removeAll.widthFor (removeAll.getButtonText())).withSizeKeepingCentre (removeAll.widthFor (removeAll.getButtonText()), bh));
        r.removeFromRight (10);
        approve.setBounds (r.removeFromRight (approve.widthFor (approve.getButtonText())).withSizeKeepingCentre (approve.widthFor (approve.getButtonText()), bh));
        r.removeFromRight (12);
        const int nw = juce::jmin ((int) name.naturalWidth(), r.getWidth() / 2);
        name.setBounds (r.removeFromLeft (nw));
        r.removeFromLeft (12);
        sub.setBounds (r);
    }
    void paint (juce::Graphics& g) override
    {
        auto r = getLocalBounds().toFloat();
        g.setColour (juce::Colour::fromRGBA (0, 0, 0, 70));
        g.fillRect (r);
        g.setColour (juce::Colour::fromRGBA (0, 0, 0, 160));
        g.drawLine (0, 0.5f, r.getWidth(), 0.5f, 1.0f);
        g.setColour (juce::Colour::fromRGBA (255, 255, 255, 12));
        g.drawLine (0, r.getHeight() - 0.5f, r.getWidth(), r.getHeight() - 0.5f, 1.0f);
        g.setColour (C ("outline", 200));
        g.fillRect (r.withWidth (3));
    }

private:
    ReviewPage& page;
    int stemId;
    Text name { "", "on_dark", 13.5f, 600, 0.4f }, sub { "", "on_dark_muted", 11, 500, 1.4f, true };
    HwButton approve { "Approve all", HwButton::dark, {}, false, 10.5f }, removeAll { "Remove all", HwButton::dark, {}, false, 10.5f };
};

// ================================================================== chop row
class ChopRow : public juce::Component, public juce::SettableTooltipClient
{
public:
    ChopRow (ReviewPage& p, int chopId) : page (p), id (chopId)
    {
        for (auto* c : std::initializer_list<juce::Component*> { &grip, &num, &name, &sub, &wave, &dur })
            addAndMakeVisible (c);
        play.setTooltip ("Play (Space)");
        play.onClick = [this] { page.select (id, true); };
        addAndMakeVisible (play);
        fillLabelCombo (type);
        type.setEditableText (false);
        type.onChange = [this] {
            if (type.getSelectedItemIndex() >= 0)
                page.ctx.session.setLabel (id, type.getText());
        };
        addAndMakeVisible (type);
        approve.setTooltip ("Approve (A approves and moves to the next chop)");
        approve.onClick = [this] { page.ctx.session.setApproved (id, approve.getToggleState()); };
        addAndMakeVisible (approve);
        del.setTooltip ("Delete this chop (Delete key)");
        del.onClick = [this] { page.ctx.session.deleteChop (id); };
        addAndMakeVisible (del);
        clone.setTooltip ("Clone this chop (Ctrl+D), then fine-tune the copy");
        clone.onClick = [this] { page.select (id, false); page.cloneSelected(); };
        addAndMakeVisible (clone);
        setTooltip ("Drag this row into your DAW (or any folder) to use the sample right away");
        setMouseCursor (juce::MouseCursor::PointingHandCursor);
    }

    void update (int number, const Chop& c, const Stem& st, const juce::String& fileName)
    {
        num.setText (juce::String (number));
        name.setText (fileName);
        juce::String s = (c.exported.empty() ? juce::String() : juce::String ("Saved") + juce::String::fromUTF8 ("  \xc2\xb7  "))
                       + "Stem: " + juce::String (st.kind);
        if (! c.flag.empty())
            s += juce::String::fromUTF8 ("  \xc2\xb7  ") + juce::String (c.flag);
        sub.setText (s);
        sub.setColourKey (isWarning (c.flag) ? "warn" : "on_dark_muted");
        dur.setText (fmtDur (c.length(), st.sr));
        setComboText (type, juce::String (c.label));
        approve.setToggleState (c.approved, juce::dontSendNotification);
        wave.set (page.ctx.peaks (st.id), c.start, c.end, c.reverse);
    }

    void setSelected (bool on)
    {
        if (on != selected)
        {
            selected = on;
            motion::move (selS, *this, on ? 1 : 0);   // the selection fades across
        }
    }
    void setPlayhead (float f) { wave.setPlayhead (f); }

    void resized() override
    {
        const auto c = chopCols (page.ctx.narrow);
        auto r = getLocalBounds().withTrimmedLeft (12).withTrimmedRight (16);
        const int h = getHeight();
        auto take = [&] (int w) { auto a = r.removeFromLeft (w); r.removeFromLeft (GAP); return a; };
        grip.setBounds (take (c.grip).withSizeKeepingCentre (c.grip, c.grip));
        num.setBounds (take (c.num));
        play.setBounds (take (c.play).withSizeKeepingCentre (c.play, c.play));
        auto nm = take (c.name);
        name.setBounds (nm.getX(), h / 2 - 20, nm.getWidth(), 20);
        sub.setBounds (nm.getX(), h / 2 + 2, nm.getWidth(), 16);
        auto right = r.removeFromRight (c.del);
        del.setBounds (right.withSizeKeepingCentre (c.del, c.del));
        r.removeFromRight (GAP - 4);
        right = r.removeFromRight (c.del);
        clone.setBounds (right.withSizeKeepingCentre (c.del, c.del));
        r.removeFromRight (GAP);
        approve.setBounds (r.removeFromRight (c.approve).withSizeKeepingCentre (c.approve, 34));
        r.removeFromRight (GAP);
        type.setBounds (r.removeFromRight (c.type).withSizeKeepingCentre (c.type, H_SMALL));
        r.removeFromRight (GAP);
        dur.setBounds (r.removeFromRight (c.dur));
        r.removeFromRight (GAP);
        wave.setBounds (r.withSizeKeepingCentre (r.getWidth(), 36));
    }

    void paint (juce::Graphics& g) override
    {
        auto r = getLocalBounds().toFloat();
        const float sl = juce::jlimit (0.0f, 1.0f, selS.getf());
        const float hv = juce::jlimit (0.0f, 1.0f, hovS.getf()) * (1 - sl);
        if (hv > 0.003f)
        {
            g.setColour (C ("row_hover").withMultipliedAlpha (hv));
            g.fillRect (r);
        }
        if (sl > 0.003f)
        {
            g.setColour (C ("row_sel").withMultipliedAlpha (sl));
            g.fillRect (r);
            // the red edge grows from the middle as the row is selected
            const float h = r.getHeight() * (0.35f + 0.65f * sl);
            g.setColour (C ("red_hi").withMultipliedAlpha (juce::jmin (1.0f, sl * 1.5f)));
            g.fillRect (juce::Rectangle<float> (0, (r.getHeight() - h) / 2, 4, h));
        }
        g.setColour (C ("row_line"));
        g.drawLine (8, r.getHeight() - 0.5f, r.getWidth() - 8, r.getHeight() - 0.5f, 1.0f);
    }

    void mouseEnter (const juce::MouseEvent&) override { hovS.to (1); }
    void mouseExit (const juce::MouseEvent&) override { hovS.to (isMouseOver (true) ? 1 : 0); }
    void mouseDown (const juce::MouseEvent&) override { dragged = false; page.select (id, false); }
    void mouseDrag (const juce::MouseEvent& e) override
    {
        if (! dragged && e.getDistanceFromDragStart() > 6)
        {
            dragged = true;
            page.startDrag (id);
        }
    }

private:
    ReviewPage& page;
    int id;
    bool selected = false, dragged = false;
    motion::Spring selS { 0, motion::FADE, this }, hovS { 0, motion::FADE, this };
    IconLabel grip { "grip", "on_dark_dim" };
    Text num { "", "on_dark_muted", 13, 500, 0.4f }, name { "", "on_dark", 13.5f, 500, 0.3f },
        sub { "", "on_dark_muted", 11, 500, 1.1f, true }, dur { "", "on_dark", 13, 400, 0.4f };
    HwButton play { "", HwButton::roundPlay, "play" };
    MiniWave wave;
    juce::ComboBox type;
    ApprovePill approve;
    HwButton del { "", HwButton::icon, "trash" }, clone { "", HwButton::icon, "copy" };
};

// ====================================================================== page
ReviewPage::ReviewPage (Context& c) : ctx (c)
{
    addAndMakeVisible (head);
    head.addAndMakeVisible (count);
    head.addAndMakeVisible (meter);
    head.addAndMakeVisible (approveAll);
    head.addAndMakeVisible (exportBtn);
    head.addAndMakeVisible (undoBtn);
    head.addAndMakeVisible (redoBtn);
    undoBtn.setTooltip ("Undo (Ctrl+Z)");
    redoBtn.setTooltip ("Redo (Ctrl+Y)");
    undoBtn.onClick = [this] { doUndo(); };
    redoBtn.onClick = [this] { doRedo(); };
    approveAll.onClick = [this] { ctx.session.approveAll(); };
    exportBtn.onClick = [this] { ctx.session.exportAll(); };

    addAndMakeVisible (split);
    for (auto* comp : std::initializer_list<juce::Component*> { &edName, &flagTile, &readout, &view, &transport, &loopBtn, &dragBtn,
                                                                &resetBtn, &snapBtn, &zoomTile, &wholeBtn, &fadeIn, &fadeOut, &autoFades,
                                                                &reverseBtn, &gain, &seamBtn, &cloneBtn, &newBtn })
        editorMod.addAndMakeVisible (comp);
    for (auto* comp : std::initializer_list<juce::Component*> { &zoomCap, &zoomOut, &zoomIn, &zoomChop })
        zoomTile.addAndMakeVisible (comp);
    flagTile.alert = false;
    flagTile.addAndMakeVisible (flagIcon);
    flagTile.addAndMakeVisible (flagText);
    transport.addAndMakeVisible (playBtn);
    transport.addAndMakeVisible (stopBtn);
    playBtn.iconSize = stopBtn.iconSize = 17;
    playBtn.setTooltip ("Play (Space)");
    stopBtn.setTooltip ("Stop (Space)");
    playBtn.onClick = [this] { if (selected >= 0) ctx.session.preview (selected, loopBtn.getToggleState()); };
    stopBtn.onClick = [this] { ctx.session.stopPreview(); };
    loopBtn.setTooltip ("Loop playback (L). Loop chops always repeat so you can hear the seam.");
    loopBtn.setToggleState (ctx.session.settings().get ("loop_play", "0") == "1", juce::dontSendNotification);
    loopBtn.onClick = [this] { ctx.session.settings().set ("loop_play", loopBtn.getToggleState() ? "1" : "0"); };
    dragBtn.setTooltip ("Press and drag this into your DAW's playlist or a channel to drop the selected sample there. "
                        "Or drag any row below.");
    dragBtn.addMouseListener (this, false);

    // ---- trim editor
    view.onSeek = [this] (int sample) {
        if (auto* c = ctx.session.chopById (selected))
        {
            followStem = c->stemId;
            ctx.session.previewStem (c->stemId, sample);
            grabKeyboardFocus();
        }
    };
    view.onSelecting = [this] (int a, int b) {
        if (auto* c = ctx.session.chopById (selected))
            if (auto* st = ctx.session.stemById (c->stemId))
                readout.set ("", juce::String ((b - a) / (double) st->sr, 3) + (ctx.narrow ? " S" : " S SELECTED"));
    };
    view.onTrimmed = [this] (int a, int b) {
        if (selected < 0)
            return;
        ctx.session.setTrim (selected, a, b);
        ctx.session.preview (selected, loopBtn.getToggleState());
        grabKeyboardFocus();
    };
    snapBtn.setTooltip ("Snap (S). On: a start dropped within about 12 ms of a hit lines up with its attack, "
                        "and loops slide along the bar grid. Off: no snapping at all.");
    snapBtn.setToggleState (ctx.session.settings().get ("snap_trim", "1") == "1", juce::dontSendNotification);
    snapBtn.onClick = [this] { ctx.session.settings().set ("snap_trim", snapBtn.getToggleState() ? "1" : "0"); updateEditor(); };
    resetBtn.setTooltip ("Put the start and end back where the chop was found");
    resetBtn.onClick = [this] { if (selected >= 0) { ctx.session.resetTrim (selected); shownChop = -1; updateEditor(); } };
    zoomOut.setTooltip ("Zoom out (or scroll the wheel over the waveform)");
    zoomIn.setTooltip ("Zoom in (or scroll the wheel over the waveform)");
    zoomChop.setTooltip ("Zoom to the chop");
    wholeBtn.setTooltip ("Show the entire stem");
    zoomOut.onClick = [this] { view.zoom (1.6); };
    zoomIn.onClick = [this] { view.zoom (0.6); };
    zoomChop.onClick = [this] { view.showChop(); };
    wholeBtn.onClick = [this] { view.showAll(); };
    cloneBtn.setTooltip ("Clone this chop (Ctrl+D), then fine-tune the copy");
    cloneBtn.onClick = [this] { cloneSelected(); };
    newBtn.setTooltip ("Make your own chop (N). Click the waveform to play the stem, then press N (or this button) "
                       "where you hear a sound. It starts on that sound; drag the red flags to fine-tune it.");
    newBtn.onClick = [this] { newChopHere(); };
    fadeIn.autoText = fadeOut.autoText = "AUTO";
    fadeIn.setTooltip ("Fade-in length. Drag up / down (Shift = fine), double-click for automatic.");
    fadeOut.setTooltip ("Fade-out length. Drag up / down (Shift = fine), double-click for automatic.");
    gain.setTooltip ("Every sample is normalized to -0.1 dB. Turn one down from there. Double-click resets.");
    for (auto* vb : { &fadeIn, &fadeOut, &gain })
        vb->onDragStart = [this] { ctx.session.checkpoint(); };
    fadeIn.onChange = [this] (double v) {
        if (auto* c = ctx.session.chopById (selected))
            ctx.session.setFades (selected, v, c->fadeOutMs, false);
    };
    fadeOut.onChange = [this] (double v) {
        if (auto* c = ctx.session.chopById (selected))
            ctx.session.setFades (selected, c->fadeInMs, v, false);
    };
    gain.onChange = [this] (double v) { if (selected >= 0) ctx.session.setGain (selected, v, false); };
    fadeIn.onReset = [this] { if (auto* c = ctx.session.chopById (selected)) ctx.session.setFades (selected, -1, c->fadeOutMs); };
    fadeOut.onReset = [this] { if (auto* c = ctx.session.chopById (selected)) ctx.session.setFades (selected, c->fadeInMs, -1); };
    gain.onReset = [this] { if (selected >= 0) ctx.session.setGain (selected, 0.0); };
    autoFades.setTooltip ("On: automatic de-click fades. Drag a fade to set your own.");
    autoFades.onClick = [this] {
        if (auto* c = ctx.session.chopById (selected))
        {
            if (autoFades.getToggleState())
                ctx.session.setFades (selected, -1, -1);
            else
            {
                auto [din, dout] = render::defaultFadesMs (*c);
                ctx.session.setFades (selected, din, dout);
            }
        }
    };
    reverseBtn.setTooltip ("Play and export this chop backwards (R). The file name gets 'Rev'.");
    reverseBtn.onClick = [this] {
        if (selected >= 0)
        {
            ctx.session.setReverse (selected, reverseBtn.getToggleState());
            ctx.session.preview (selected, loopBtn.getToggleState());
        }
    };
    seamBtn.setTooltip ("Loops: blends the end into what comes just before the start, so it repeats without a click. "
                        "Length stays on the bars.");
    seamBtn.onClick = [this] {
        if (selected >= 0)
        {
            ctx.session.setSeam (selected, seamBtn.getToggleState());
            ctx.session.preview (selected, loopBtn.getToggleState());
        }
    };

    for (auto t : { "#", "File / stem", "Waveform", "Duration", "Type", "Actions" })
        listMod.addAndMakeVisible (cols.add (new Text (t, "header_text", 11, 600, 1.4f, true)));
    viewport.setViewedComponent (&rowsHolder, false);
    viewport.setScrollBarsShown (true, false);
    viewport.setScrollBarThickness (10);
    listMod.addAndMakeVisible (viewport);
    empty.justification = juce::Justification::centred;
    listMod.addAndMakeVisible (empty);
    editorMod.padL = editorMod.padR = 16;
    editorMod.padT = 10;
    editorMod.padB = 12;
    listMod.padL = listMod.padR = 8;
    listMod.padT = 8;
    listMod.padB = 10;
    head.padL = head.padR = 20;
    head.padT = head.padB = 10;
    split.topMin = 330;
    split.bottomMin = 150;
    try
    {
        split.setFraction (ctx.session.settings().get ("review_split", "0.47").getFloatValue());
    }
    catch (...) {}
    split.onMoved = [this] (float f) { ctx.session.settings().set ("review_split", juce::String (f, 4)); };
    setWantsKeyboardFocus (true);
    addKeyListener (this);
    refresh();
}

ReviewPage::~ReviewPage()
{
    dragBtn.removeMouseListener (this);
}

void ReviewPage::refresh()
{
    auto& s = ctx.session;
    const auto names = s.names();
    // rebuild the rows when the set of chops changed
    juce::String key;
    for (auto& ch : s.chops)
        key << ch.id << "," << ch.stemId << ";";
    if (key != getProperties()["rowkey"].toString())
    {
        getProperties().set ("rowkey", key);
        const int scroll = viewport.getViewPositionY();
        rows.clear();
        rowById.clear();
        int number = 0, last = -1;
        for (auto& ch : s.chops)
        {
            auto* st = s.stemById (ch.stemId);
            if (st == nullptr)
                continue;
            if (st->id != last)
            {
                int n = 0;
                for (auto& x : s.chops)
                    n += x.stemId == st->id;
                rowsHolder.addAndMakeVisible (rows.add (new GroupRow (*this, *st, n)));
                last = st->id;
            }
            auto* row = new ChopRow (*this, ch.id);
            rows.add (row);
            rowsHolder.addAndMakeVisible (row);
            rowById[ch.id] = row;
            ++number;
        }
        resized();
        viewport.setViewPosition (0, scroll);
    }
    int number = 0;
    for (auto& ch : s.chops)
        if (auto it = rowById.find (ch.id); it != rowById.end())
        {
            auto* st = s.stemById (ch.stemId);
            auto n = names.find (ch.id);
            it->second->update (++number, ch, *st, n != names.end() ? juce::String (n->second) : juce::String());
        }
    if (selected < 0 || s.chopById (selected) == nullptr)
        selected = s.chops.empty() ? -1 : s.chops.front().id;
    for (auto& [id, row] : rowById)
        row->setSelected (id == selected);
    empty.setVisible (s.chops.empty());
    viewport.setVisible (! s.chops.empty());
    for (auto* t : cols)
        t->setVisible (! s.chops.empty());
    updateHeader();
    updateEditor();
}

void ReviewPage::updateHeader()
{
    auto& s = ctx.session;
    const int n = (int) s.chops.size(), a = s.approvedCount();
    const bool done = n > 0 && a == n;
    const int k = s.toExportCount();
    meter.set (n ? (float) a / n : 0.0f);
    exportBtn.setEnabled (k > 0 && ! s.busy());
    exportBtn.setTooltip (k > 0 ? "Save the " + juce::String (k) + " approved chop" + (k == 1 ? "" : "s") + " to "
                                      + s.outputFolder().getFullPathName() + ". Chops you didn't approve are skipped."
                          : (a > 0 && s.savedCount() > 0) ? juce::String ("Every approved chop is already saved. Approve more to export again.")
                                                          : juce::String ("Approve the chops you want, then export them"));
    approveAll.setEnabled (n > 0 && ! done);
    undoBtn.setEnabled (s.canUndo() && ! s.busy());
    redoBtn.setEnabled (s.canRedo() && ! s.busy());
    resized();
}

void ReviewPage::applyTexts()
{
    // labels that get shorter when the window is narrow
    auto& s = ctx.session;
    const int n = (int) s.chops.size(), a = s.approvedCount();
    const bool narrow = ctx.narrow;
    count.setText (n ? (narrow ? juce::String (a) + "/" + juce::String (n) + " APPROVED"
                               : juce::String (a) + " OF " + juce::String (n) + " APPROVED")
                     : juce::String ("NO CHOPS YET"));
    const int k = s.toExportCount();
    exportBtn.setButtonText (k > 0 ? (narrow ? "Export " + juce::String (k) : "Export " + juce::String (k) + " approved")
                                   : (narrow ? juce::String ("Export") : juce::String ("Export approved")));
    if (auto* c = selected >= 0 ? s.chopById (selected) : nullptr)
        if (auto* st = s.stemById (c->stemId))
            readout.set ("", juce::String (c->length() / (double) st->sr, 3) + (narrow ? " S" : " S SELECTED"));
}

void ReviewPage::updateEditor()
{
    auto& s = ctx.session;
    auto* c = selected >= 0 ? s.chopById (selected) : nullptr;
    auto* st = c ? s.stemById (c->stemId) : nullptr;
    if (c == nullptr || st == nullptr)
    {
        edName.setText ("");
        flagTile.setVisible (false);
        readout.set ("", "");
        view.clear();
        return;
    }
    edName.setText (s.nameOf (c->id));
    const bool warn = isWarning (c->flag);
    flagTile.setVisible (! c->flag.empty());
    flagTile.alert = warn;
    flagTile.repaint();
    flagIcon.set (warn ? "warning" : "bulb", warn ? "warn" : "on_dark_muted");
    flagText.setText (juce::String (c->flag));
    flagText.setColourKey (warn ? "warn" : "on_dark_muted");
    flagTile.setTooltip (juce::String (c->flag));
    // same chop: keep the zoom. Another chop: show it (but stay zoomed out if the whole stem is shown)
    const bool sameChop = shownChop == c->id;
    view.set (ctx.peaks (st->id), st->frames(), st->sr, c->start, c->end, sameChop || view.isWhole());
    shownChop = c->id;
    const int stemId = st->id;
    const bool isLoop = c->kind == "loop";
    if (snapBtn.getToggleState())
    {
        view.snap = isLoop ? std::function<int (int)>() : std::function<int (int)> ([this, stemId] (int x) { return ctx.session.magnet (stemId, x); });
        view.snapMove = isLoop ? std::function<int (int)> ([this, stemId] (int x) { return ctx.session.snapToBar (stemId, x); }) : std::function<int (int)>();
    }
    else
        view.snap = view.snapMove = nullptr;
    loadFx (*c);
    resized();
}

void ReviewPage::loadFx (const Chop& c)
{
    auto* st = ctx.session.stemById (c.stemId);
    const int sr = st ? st->sr : 44100;
    auto [din, dout] = render::defaultFadesMs (c);
    const double fi = c.fadeInMs < 0 ? din : c.fadeInMs, fo = c.fadeOutMs < 0 ? dout : c.fadeOutMs;
    fadeIn.setValue (fi, c.fadeInMs < 0);
    fadeOut.setValue (fo, c.fadeOutMs < 0);
    gain.setValue (c.gainDb);
    autoFades.setToggleState (c.fadeInMs < 0 && c.fadeOutMs < 0, juce::dontSendNotification);
    reverseBtn.setToggleState (c.reverse, juce::dontSendNotification);
    seamBtn.setToggleState (c.seam, juce::dontSendNotification);
    seamBtn.setEnabled (c.kind == "loop");
    resetBtn.setEnabled (c.origStart >= 0 && (c.start != c.origStart || c.end != c.origEnd));
    view.setFx ((int) (fi * sr / 1000.0), (int) (fo * sr / 1000.0), c.reverse);
}

int ReviewPage::playheadSample() const
{
    auto& s = ctx.session;
    const int pid = s.player.playingId();
    const double pos = s.player.position();
    auto* c = s.chopById (selected);
    if (c == nullptr || pos < 0)
        return -1;
    if (pid == Session::STEM_PLAY + c->stemId)
        return s.stemPlayFrom + (int) (pos * s.stemPlayLen);
    if (pid == c->id)
        return c->start + (int) ((c->reverse ? 1.0 - pos : pos) * c->length());
    return -1;
}

void ReviewPage::togglePlay()
{
    auto& s = ctx.session;
    if (s.player.playingId() >= 0)
        s.stopPreview();
    else if (selected >= 0)
        s.preview (selected, loopBtn.getToggleState());
}

void ReviewPage::cloneSelected()
{
    if (selected < 0)
        return;
    const int id = ctx.session.cloneChop (selected);
    if (id >= 0)
    {
        refresh();
        select (id, false);
    }
}

void ReviewPage::newChopHere()
{
    auto& s = ctx.session;
    auto* c = s.chopById (selected);
    if (c == nullptr || ! view.hasStem())
        return;
    const int stemId = c->stemId;
    int at = -1;
    if (s.player.playingId() == Session::STEM_PLAY + stemId)
        at = playheadSample();
    if (at < 0)
        at = (view.viewStart() + view.viewEnd()) / 2;
    const bool keepPlaying = s.player.playingId() == Session::STEM_PLAY + stemId;
    const int id = s.newChopAt (stemId, at, selected);
    if (id < 0)
        return;
    refresh();
    selected = id;
    for (auto& [rid, row] : rowById)
        row->setSelected (rid == id);
    shownChop = id;                 // keep the zoom, so you can keep listening
    updateEditor();
    if (auto* nc = s.chopById (id))
        if (nc->start < view.viewStart() || nc->end > view.viewEnd())
        {
            const int span = view.viewEnd() - view.viewStart();
            view.setView (nc->start - span / 3, nc->start - span / 3 + span, true);
        }
    if (! keepPlaying)
        s.preview (id, false);
    if (ctx.status)
        ctx.status ("Added your own chop. Drag the red flags to fine-tune it.");
    grabKeyboardFocus();
}

void ReviewPage::doUndo()
{
    if (ctx.session.undo())
    {
        shownChop = -1;
        refresh();
    }
}

void ReviewPage::doRedo()
{
    if (ctx.session.redo())
    {
        shownChop = -1;
        refresh();
    }
}

void ReviewPage::select (int chopId, bool play)
{
    if (chopId != selected)
        shownChop = -1;
    selected = chopId;
    for (auto& [id, row] : rowById)
        row->setSelected (id == chopId);
    if (auto it = rowById.find (chopId); it != rowById.end())
    {
        auto b = it->second->getBounds();
        const int top = viewport.getViewPositionY(), h = viewport.getMaximumVisibleHeight();
        if (b.getY() < top)
            viewport.setViewPosition (0, b.getY());
        else if (b.getBottom() > top + h)
            viewport.setViewPosition (0, b.getBottom() - h);
    }
    updateEditor();
    if (play)
        ctx.session.preview (chopId, loopBtn.getToggleState());
    grabKeyboardFocus();
}

void ReviewPage::moveSelection (int delta)
{
    auto& ch = ctx.session.chops;
    if (ch.empty())
        return;
    int i = 0;
    for (int k = 0; k < (int) ch.size(); ++k)
        if (ch[(size_t) k].id == selected)
            i = k;
    i = juce::jlimit (0, (int) ch.size() - 1, i + delta);
    select (ch[(size_t) i].id, true);
}

void ReviewPage::mouseDrag (const juce::MouseEvent& e)
{
    if (e.eventComponent == &dragBtn && ! padDragged && e.getDistanceFromDragStart() > 6 && selected >= 0)
    {
        padDragged = true;
        startDrag (selected);
    }
}

void ReviewPage::startDrag (int chopId)
{
    auto f = ctx.session.renderForDrag (chopId);
    if (f.existsAsFile())
        juce::DragAndDropContainer::performExternalDragDropOfFiles ({ f.getFullPathName() }, false, this);
}

bool ReviewPage::keyPressed (const juce::KeyPress& k, juce::Component*)
{
    auto& s = ctx.session;
    if (k == juce::KeyPress::downKey) { moveSelection (1); return true; }
    if (k == juce::KeyPress::upKey) { moveSelection (-1); return true; }
    if (k == juce::KeyPress::spaceKey) { togglePlay(); return true; }
    const auto ch = juce::CharacterFunctions::toLowerCase (k.getTextCharacter());
    const auto code = k.getKeyCode();
    if (k.getModifiers().isCommandDown())
    {
        if (code == 'Z' || code == 'z')
        {
            if (k.getModifiers().isShiftDown()) doRedo(); else doUndo();
            return true;
        }
        if (code == 'Y' || code == 'y') { doRedo(); return true; }
        if ((code == 'D' || code == 'd') && selected >= 0) { cloneSelected(); return true; }
        return false;
    }
    if (selected < 0)
        return false;
    if (k.getTextCharacter() == 'a' || k.getTextCharacter() == 'A')
    {
        s.setApproved (selected, true);
        moveSelection (1);
        return true;
    }
    if (k == juce::KeyPress::returnKey)
    {
        if (auto* c = s.chopById (selected))
            s.setApproved (selected, ! c->approved);
        return true;
    }
    if (k == juce::KeyPress::deleteKey || k == juce::KeyPress::backspaceKey)
    {
        int next = -1;
        for (size_t i = 0; i < s.chops.size(); ++i)
            if (s.chops[i].id == selected)
                next = i + 1 < s.chops.size() ? s.chops[i + 1].id : (i > 0 ? s.chops[i - 1].id : -1);
        s.deleteChop (selected);
        selected = next;
        refresh();
        return true;
    }
    if (k.getTextCharacter() == 'l' || k.getTextCharacter() == 'L')
    {
        loopBtn.setToggleState (! loopBtn.getToggleState(), juce::sendNotification);
        return true;
    }
    if (ch == 'n') { newChopHere(); return true; }
    if (ch == 'r')
    {
        reverseBtn.setToggleState (! reverseBtn.getToggleState(), juce::sendNotification);
        return true;
    }
    if (ch == 's')
    {
        snapBtn.setToggleState (! snapBtn.getToggleState(), juce::sendNotification);
        return true;
    }
    return false;
}

void ReviewPage::tick()
{
    auto& s = ctx.session;
    const int playing = s.player.playingId();
    const double pos = s.player.position();
    for (auto& [id, row] : rowById)
        row->setPlayhead (id == playing && pos >= 0 ? (float) pos : -1.0f);
    const int ph = playheadSample();
    view.setPlayhead (ph);
    // playing the stem past the right edge: the view follows
    if (ph >= 0 && playing >= Session::STEM_PLAY && ! view.dragging() && ph > view.viewEnd())
    {
        const int span = view.viewEnd() - view.viewStart();
        view.setView (ph - span / 10, ph - span / 10 + span);
    }
}

void ReviewPage::resized()
{
    applyTexts();
    auto r = getLocalBounds().withTrimmedTop (4);
    const bool narrow = ctx.narrow;
    // header
    head.setBounds (r.removeFromTop (62));
    {
        auto c = head.getLocalBounds().reduced (20, 10);
        const int ew = exportBtn.widthFor (narrow ? "Export 999" : "Export 999 approved");
        exportBtn.setBounds (c.removeFromRight (juce::jmax (ew, exportBtn.widthFor (exportBtn.getButtonText()))).withSizeKeepingCentre (juce::jmax (ew, exportBtn.widthFor (exportBtn.getButtonText())), H_KEY));
        c.removeFromRight (10);
        const int aw = juce::jmax (narrow ? 0 : 140, approveAll.widthFor (approveAll.getButtonText()));
        approveAll.setBounds (c.removeFromRight (aw).withSizeKeepingCentre (aw, H_KEY));
        c.removeFromRight (10);
        undoBtn.setButtonText (narrow ? "" : "Undo");
        redoBtn.setButtonText (narrow ? "" : "Redo");
        const int uw = narrow ? 46 : juce::jmax (104, redoBtn.widthFor ("Redo"));
        redoBtn.setBounds (c.removeFromRight (uw).withSizeKeepingCentre (uw, H_KEY));
        c.removeFromRight (8);
        undoBtn.setBounds (c.removeFromRight (uw).withSizeKeepingCentre (uw, H_KEY));
        c.removeFromRight (18);
        count.setFontSpec (narrow ? 17.0f : 21.0f, 600, narrow ? 1.6f : 2.2f);
        const int cw = narrow ? 200 : 290;
        count.setBounds (c.removeFromLeft (cw));
        c.removeFromLeft (10);
        meter.setBounds (c.withWidth (juce::jmin (420, c.getWidth())).withSizeKeepingCentre (juce::jmin (420, c.getWidth()), 30));
    }
    r.removeFromTop (12);
    split.setBounds (r);

    // editor module
    {
        auto c = editorMod.content();
        auto top = c.removeFromTop (32);
        const int rw = narrow ? 170 : 200;
        readout.setBounds (top.removeFromRight (rw));
        top.removeFromRight (12);
        const int nw = juce::jmin ((int) edName.naturalWidth(), top.getWidth() / 2);
        edName.setBounds (top.removeFromLeft (nw));
        top.removeFromLeft (12);
        flagTile.setBounds (top);
        auto ft = flagTile.getLocalBounds().reduced (10, 0);
        flagIcon.setBounds (ft.removeFromLeft (18).withSizeKeepingCentre (18, 18));
        ft.removeFromLeft (8);
        flagText.setBounds (ft);
        c.removeFromTop (8);
        // two rows of controls under the waveform
        auto row2 = c.removeFromBottom (H_ROW);
        c.removeFromBottom (8);
        auto row = c.removeFromBottom (H_ROW);
        c.removeFromBottom (8);
        view.setBounds (c);
        const int G = 8;
        // row 1: play / stop, loop, reset trim, snap, zoom, whole stem, new chop
        transport.setBounds (row.removeFromLeft (5 + 48 + 6 + 48 + 5));
        playBtn.setBounds (5, 5, 48, H_ROW - 10);
        stopBtn.setBounds (5 + 48 + 6, 5, 48, H_ROW - 10);
        row.removeFromLeft (G);
        loopBtn.showState = snapBtn.showState = ! narrow;
        for (auto* t : { &autoFades, &reverseBtn, &seamBtn })
            t->showState = false;           // the LED shows on / off
        loopBtn.setBounds (row.removeFromLeft (loopBtn.naturalWidth()));
        row.removeFromLeft (G);
        resetBtn.setButtonText (narrow ? "Reset" : "Reset trim");
        resetBtn.setBounds (row.removeFromLeft (resetBtn.widthFor (resetBtn.getButtonText())));
        row.removeFromLeft (G);
        snapBtn.setBounds (row.removeFromLeft (snapBtn.naturalWidth()));
        row.removeFromLeft (G);
        newBtn.setButtonText (narrow ? "New" : "New chop");
        newBtn.setBounds (row.removeFromRight (newBtn.widthFor (newBtn.getButtonText())));
        row.removeFromRight (G);
        wholeBtn.setButtonText (narrow ? "Whole" : "Whole stem");
        wholeBtn.setBounds (row.removeFromRight (wholeBtn.widthFor (wholeBtn.getButtonText())));
        row.removeFromRight (G);
        zoomTile.setBounds (row);
        {
            auto z = zoomTile.getLocalBounds().reduced (12, 0);
            zoomCap.setBounds (z.removeFromLeft ((int) zoomCap.naturalWidth() + 4));
            z.removeFromLeft (6);
            const int cw = zoomChop.widthFor ("Chop");
            zoomChop.setBounds (z.removeFromRight (cw).withSizeKeepingCentre (cw, H_SMALL));
            z.removeFromRight (8);
            zoomOut.setBounds (z.removeFromLeft (H_SMALL).withSizeKeepingCentre (H_SMALL, H_SMALL));
            z.removeFromLeft (6);
            zoomIn.setBounds (z.removeFromLeft (H_SMALL).withSizeKeepingCentre (H_SMALL, H_SMALL));
        }
        // row 2: the chop's sound, then copy / drag out
        dragBtn.setButtonText (narrow ? "Drag" : "Drag into your DAW");
        dragBtn.setBounds (row2.removeFromRight (dragBtn.widthFor (dragBtn.getButtonText())));
        row2.removeFromRight (G);
        cloneBtn.setButtonText (narrow ? "" : "Clone");
        cloneBtn.setBounds (row2.removeFromRight (narrow ? 48 : cloneBtn.widthFor ("Clone")));
        row2.removeFromRight (G);
        seamBtn.label = narrow ? "Seam" : "Loop seam";
        autoFades.label = narrow ? "Auto" : "Auto fades";
        reverseBtn.label = narrow ? "Rev" : "Reverse";
        fadeIn.compact = fadeOut.compact = gain.compact = narrow;
        fadeIn.shortCaption = "In";
        fadeOut.shortCaption = "Out";
        gain.shortCaption = "Gain";
        const int fixed = autoFades.naturalWidth() + reverseBtn.naturalWidth() + seamBtn.naturalWidth() + 5 * G;
        const int boxW = juce::jmax (100, (row2.getWidth() - fixed) / 3);
        fadeIn.setBounds (row2.removeFromLeft (boxW));
        row2.removeFromLeft (G);
        fadeOut.setBounds (row2.removeFromLeft (boxW));
        row2.removeFromLeft (G);
        autoFades.setBounds (row2.removeFromLeft (autoFades.naturalWidth()));
        row2.removeFromLeft (G);
        reverseBtn.setBounds (row2.removeFromLeft (reverseBtn.naturalWidth()));
        row2.removeFromLeft (G);
        seamBtn.setBounds (row2.removeFromRight (seamBtn.naturalWidth()));
        row2.removeFromRight (G);
        gain.setBounds (row2);
    }
    // list module
    {
        auto c = listMod.content();
        auto hr = c.removeFromTop (34);
        const auto cc = chopCols (narrow);
        int x = hr.getX() + 12;
        auto put = [&] (int i, int w) { cols[i]->setBounds (x, hr.getY(), w, hr.getHeight()); x += w + GAP; };
        x += cc.grip + GAP;
        put (0, cc.num);
        x += cc.play + GAP;
        put (1, cc.name);
        const int rightW = cc.dur + cc.type + cc.approve + 2 * cc.del + 4 * GAP - 4 + 16 + 10;
        const int waveW = juce::jmax (40, hr.getRight() - x - rightW);
        put (2, waveW);
        put (3, cc.dur);
        put (4, cc.type);
        put (5, cc.approve + 2 * cc.del + 2 * GAP - 4);
        viewport.setBounds (c);
        empty.setBounds (listMod.content());
        const int w = viewport.getMaximumVisibleWidth();
        int y = 0;
        for (auto* row : rows)
        {
            const int h = dynamic_cast<GroupRow*> (row) != nullptr ? GROUP_H : ROW_H;
            row->setBounds (0, y, w, h);
            y += h;
        }
        rowsHolder.setSize (w, y);
    }
}

// ==================================================================== export
ExportPage::ExportPage (Context& c) : ctx (c)
{
    addAndMakeVisible (box);
    for (auto* comp : std::initializer_list<juce::Component*> { &lamp, &title, &path, &outline, &specs, &again, &openBtn, &back })
        box.addAndMakeVisible (comp);
    path.setReadOnly (true);
    outline.addAndMakeVisible (list);
    list.setModel (this);
    list.setRowHeight (34);
    list.setColour (juce::ListBox::backgroundColourId, juce::Colours::transparentBlack);
    again.onClick = [this] { ctx.session.startOver(); ctx.go (0); };
    back.setTooltip ("Approve more chops and export again. Only new ones are added.");
    back.onClick = [this] { ctx.go (1); };
    openBtn.onClick = [this] {
        if (ctx.session.lastExportFolder.isDirectory())
            ctx.session.lastExportFolder.startAsProcess();
    };
    refresh();
}

void ExportPage::refresh()
{
    auto& s = ctx.session;
    files = s.lastExportFiles;
    lamp.setVisible (! files.isEmpty());
    title.setText (files.isEmpty() ? juce::String ("NOTHING EXPORTED YET")
                                   : "EXPORTED " + juce::String (files.size()) + " FILE" + (files.size() == 1 ? "" : "S"));
    path.setText (s.lastExportFolder.getFullPathName(), false);
    openBtn.setEnabled (s.lastExportFolder.isDirectory());
    // chops left that weren't saved: offer to go back, approve more and export again
    back.setVisible (std::any_of (s.chops.begin(), s.chops.end(), [] (const Chop& c) { return c.exported.empty(); }));
    list.updateContent();
    list.repaint();
}

void ExportPage::paintListBoxItem (int row, juce::Graphics& g, int w, int h, bool)
{
    if (! juce::isPositiveAndBelow (row, files.size()))
        return;
    juce::File f (files[row]);
    const auto size = f.getSize();
    const juce::String sz = size > 1000000 ? juce::String (size / 1e6, 1) + " MB" : juce::String (size / 1000) + " KB";
    text (g, { 12, 0, (float) w - 140, (float) h }, f.getFileName(), font (13, 400, 0.3f), C ("on_dark"), juce::Justification::centredLeft, true);
    text (g, { (float) w - 120, 0, 110, (float) h }, sz, font (13, 400, 0.3f), C ("on_dark_muted"));
    g.setColour (C ("row_line"));
    g.drawLine (8, (float) h - 0.5f, (float) w - 8, (float) h - 0.5f, 1.0f);
}

void ExportPage::resized()
{
    auto r = getLocalBounds().withTrimmedTop (4);
    const int w = juce::jlimit (juce::jmin (640, r.getWidth()), 980, r.getWidth() * 6 / 8);
    box.setBounds (r.withSizeKeepingCentre (w, r.getHeight()));
    auto c = box.content();
    auto headR = c.removeFromTop (76);
    lamp.setBounds (headR.removeFromLeft (46).withSizeKeepingCentre (46, 46));
    headR.removeFromLeft (14);
    title.setBounds (headR.removeFromTop (34));
    headR.removeFromTop (6);
    path.setBounds (headR.removeFromTop (H_FIELD));
    c.removeFromTop (14);
    auto buttons = c.removeFromBottom (H_KEY);
    c.removeFromBottom (14);
    specs.setBounds (c.removeFromBottom (18));
    c.removeFromBottom (12);
    outline.setBounds (c);
    list.setBounds (outline.getLocalBounds().reduced (4, 2));
    openBtn.setBounds (buttons.removeFromRight (openBtn.widthFor (openBtn.getButtonText())));
    buttons.removeFromRight (12);
    again.setBounds (buttons.removeFromRight (again.widthFor (again.getButtonText())));
    back.setBounds (buttons.removeFromLeft (back.widthFor (back.getButtonText())));
}

} // namespace xk::ui
