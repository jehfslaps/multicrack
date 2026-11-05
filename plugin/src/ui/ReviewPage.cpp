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
        setTooltip ("Drag this row into your DAW (or any folder) to use the sample right away");
        setMouseCursor (juce::MouseCursor::PointingHandCursor);
    }

    void update (int number, const Chop& c, const Stem& st, const juce::String& fileName)
    {
        num.setText (juce::String (number));
        name.setText (fileName);
        juce::String s = "Stem: " + juce::String (st.kind);
        if (! c.flag.empty())
            s += juce::String::fromUTF8 ("  \xc2\xb7  ") + juce::String (c.flag);
        sub.setText (s);
        sub.setColourKey (isWarning (c.flag) ? "warn" : "on_dark_muted");
        dur.setText (fmtDur (c.length(), st.sr));
        setComboText (type, juce::String (c.label));
        approve.setToggleState (c.approved, juce::dontSendNotification);
        wave.set (page.ctx.peaks (st.id), c.start, c.end, c.reverse);
    }

    void setSelected (bool on) { if (on != selected) { selected = on; repaint(); } }
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
        if (selected)
        {
            g.setColour (C ("row_sel"));
            g.fillRect (r);
            g.setColour (C ("red_hi"));
            g.fillRect (r.withWidth (4));
        }
        else if (isMouseOver (true))
        {
            g.setColour (C ("row_hover"));
            g.fillRect (r);
        }
        g.setColour (C ("row_line"));
        g.drawLine (8, r.getHeight() - 0.5f, r.getWidth() - 8, r.getHeight() - 0.5f, 1.0f);
    }

    void mouseEnter (const juce::MouseEvent&) override { repaint(); }
    void mouseExit (const juce::MouseEvent&) override { repaint(); }
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
    IconLabel grip { "grip", "on_dark_dim" };
    Text num { "", "on_dark_muted", 13, 500, 0.4f }, name { "", "on_dark", 13.5f, 500, 0.3f },
        sub { "", "on_dark_muted", 11, 500, 1.1f, true }, dur { "", "on_dark", 13, 400, 0.4f };
    HwButton play { "", HwButton::roundPlay, "play" };
    MiniWave wave;
    juce::ComboBox type;
    ApprovePill approve;
    HwButton del { "", HwButton::icon, "trash" };
};

// ====================================================================== page
ReviewPage::ReviewPage (Context& c) : ctx (c)
{
    addAndMakeVisible (head);
    head.addAndMakeVisible (count);
    head.addAndMakeVisible (meter);
    head.addAndMakeVisible (approveAll);
    head.addAndMakeVisible (exportBtn);
    approveAll.onClick = [this] { ctx.session.approveAll(); };
    exportBtn.onClick = [this] { ctx.session.exportAll(); };

    addAndMakeVisible (split);
    for (auto* comp : std::initializer_list<juce::Component*> { &edName, &flagTile, &readout, &view, &transport, &loopBtn, &dragBtn, &dragHint })
        editorMod.addAndMakeVisible (comp);
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
    dragBtn.setTooltip ("Press and drag this into your DAW's playlist or a channel to drop the selected sample there");
    dragBtn.addMouseListener (this, false);
    dragHint.elide = true;
    view.onClickAt = [this] (int) { if (selected >= 0) ctx.session.preview (selected, loopBtn.getToggleState()); };

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
    split.topMin = 250;
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
    meter.set (n ? (float) a / n : 0.0f);
    exportBtn.setEnabled (done && ! s.busy());
    exportBtn.setTooltip (done ? "Write every sample to " + s.outputFolder().getFullPathName() : "Approve every chop to export");
    approveAll.setEnabled (n > 0 && ! done);
    resized();
}

void ReviewPage::applyTexts()
{
    // labels that get shorter when the window is narrow
    auto& s = ctx.session;
    const int n = (int) s.chops.size(), a = s.approvedCount();
    const bool done = n > 0 && a == n, narrow = ctx.narrow;
    count.setText (n ? (narrow ? juce::String (a) + "/" + juce::String (n) + " APPROVED"
                               : juce::String (a) + " OF " + juce::String (n) + " APPROVED")
                     : juce::String ("NO CHOPS YET"));
    exportBtn.setButtonText (done ? (narrow ? juce::String ("Export all") : "Export " + juce::String (n) + " files")
                                  : (narrow ? juce::String ("Export") : juce::String ("Export (approve all)")));
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
    view.set (ctx.peaks (st->id), st->frames(), st->sr, c->start, c->end);
    resized();
}

void ReviewPage::select (int chopId, bool play)
{
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
    if (k == juce::KeyPress::spaceKey)
    {
        if (s.player.playingId() >= 0) s.stopPreview();
        else if (selected >= 0) s.preview (selected, loopBtn.getToggleState());
        return true;
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
    return false;
}

void ReviewPage::tick()
{
    auto& s = ctx.session;
    const int playing = s.player.playingId();
    const double pos = s.player.position();
    for (auto& [id, row] : rowById)
        row->setPlayhead (id == playing && pos >= 0 ? (float) pos : -1.0f);
    if (playing == selected && pos >= 0)
        if (auto* c = s.chopById (selected))
        {
            const double p = c->reverse ? 1.0 - pos : pos;
            view.setPlayhead (c->start + (int) (p * c->length()));
            return;
        }
    view.setPlayhead (-1);
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
        const int ew = exportBtn.widthFor (narrow ? "Export all" : "Export (approve all)");
        exportBtn.setBounds (c.removeFromRight (juce::jmax (ew, exportBtn.widthFor (exportBtn.getButtonText()))).withSizeKeepingCentre (juce::jmax (ew, exportBtn.widthFor (exportBtn.getButtonText())), H_KEY));
        c.removeFromRight (10);
        const int aw = juce::jmax (narrow ? 0 : 140, approveAll.widthFor (approveAll.getButtonText()));
        approveAll.setBounds (c.removeFromRight (aw).withSizeKeepingCentre (aw, H_KEY));
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
        auto row = c.removeFromBottom (H_ROW);
        c.removeFromBottom (8);
        view.setBounds (c);
        transport.setBounds (row.removeFromLeft (5 + 48 + 6 + 48 + 5));
        playBtn.setBounds (5, 5, 48, H_ROW - 10);
        stopBtn.setBounds (5 + 48 + 6, 5, 48, H_ROW - 10);
        row.removeFromLeft (8);
        loopBtn.showState = ! narrow;
        loopBtn.setBounds (row.removeFromLeft (loopBtn.naturalWidth()));
        row.removeFromLeft (8);
        dragBtn.setButtonText (narrow ? "Drag to DAW" : "Drag into your DAW");
        dragBtn.setBounds (row.removeFromLeft (dragBtn.widthFor (dragBtn.getButtonText())));
        row.removeFromLeft (14);
        dragHint.setBounds (row);
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
        const int rightW = cc.dur + cc.type + cc.approve + cc.del + 3 * GAP + 16 + 10;
        const int waveW = juce::jmax (40, hr.getRight() - x - rightW);
        put (2, waveW);
        put (3, cc.dur);
        put (4, cc.type);
        put (5, cc.approve + cc.del + GAP);
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
    for (auto* comp : std::initializer_list<juce::Component*> { &lamp, &title, &path, &outline, &specs, &again, &openBtn })
        box.addAndMakeVisible (comp);
    path.setReadOnly (true);
    outline.addAndMakeVisible (list);
    list.setModel (this);
    list.setRowHeight (34);
    list.setColour (juce::ListBox::backgroundColourId, juce::Colours::transparentBlack);
    again.onClick = [this] { ctx.session.startOver(); ctx.go (0); };
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
}

} // namespace xk::ui
