#include "PluginEditor.h"

namespace xk::ui
{

MainView::MainView (Session& s) : session (s)
{
    applyTheme (session.settings().get ("theme", "light") == "dark");
    setLookAndFeel (&lnf);
    juce::LookAndFeel::setDefaultLookAndFeel (&lnf);
    ctx.go = [this] (int p) { go (p); };
    addAndMakeVisible (brand);
    brand.addAndMakeVisible (mark);
    brand.addAndMakeVisible (brandText);
    brand.addAndMakeVisible (badge);
    brandText.elide = false;
    addAndMakeVisible (steps);
    steps.onClick = [this] (int p) { go (p); };
    addAndMakeVisible (lcd);
    addAndMakeVisible (lever);
    lever.setToggleState (isDark(), juce::dontSendNotification);
    lever.setTooltip ("Light / dark");
    lever.onClick = [this] {
        applyTheme (lever.getToggleState());
        session.settings().set ("theme", lever.getToggleState() ? "dark" : "light");
    };
    addAndMakeVisible (menuBtn);
    menuBtn.setTooltip ("Menu");
    menuBtn.onClick = [this] { showMenu(); };
    loadPage = std::make_unique<LoadPage> (ctx, *this);
    reviewPage = std::make_unique<ReviewPage> (ctx);
    exportPage = std::make_unique<ExportPage> (ctx);
    addChildComponent (*loadPage);
    addChildComponent (*reviewPage);
    addChildComponent (*exportPage);
    session.addChangeListener (this);
    exportsSeen = session.lastExportFiles.size();
    lastExportFolder = session.lastExportFolder.getFullPathName();
    go (session.chops.empty() ? 0 : 1);
    refreshAll();
    startTimerHz (30);
}

MainView::~MainView()
{
    session.removeChangeListener (this);
    juce::LookAndFeel::setDefaultLookAndFeel (nullptr);
    setLookAndFeel (nullptr);
}

void MainView::applyTheme (bool dark)
{
    setDark (dark);
    lnf.refreshColours();
    sendLookAndFeelChange();
    repaint();
}

void MainView::go (int p)
{
    page = p;
    loadPage->setVisible (p == 0);
    reviewPage->setVisible (p == 1);
    exportPage->setVisible (p == 2);
    steps.setCurrent (p);
    if (p == 1)
    {
        reviewPage->refresh();
        reviewPage->grabKeyboardFocus();
    }
    repaint();
}

void MainView::showTempo()
{
    const auto bpm = session.songGrid ? session.songGrid->bpm : 0.0;
    lcd.set (getWidth() < FULL_W ? "TEMPO" : "SONG TEMPO", bpm > 0 ? juce::String (bpm, 2).trimCharactersAtEnd ("0").trimCharactersAtEnd (".") + " BPM"
                                   : juce::String::fromUTF8 ("\xe2\x80\x94 BPM"));
}

void MainView::refreshAll()
{
    steps.setStepEnabled (1, ! session.stems.empty() || ! session.chops.empty());
    steps.setStepEnabled (2, session.lastExportFolder.isDirectory());
    loadPage->refresh();
    if (reviewPage->isVisible() || ! session.chops.empty())
        reviewPage->refresh();
    exportPage->refresh();
    if (! session.busy())
        showTempo();
}

void MainView::changeListenerCallback (juce::ChangeBroadcaster*)
{
    const bool busy = session.busy();
    // finished processing: go to review. finished exporting: go to export.
    if (wasBusy && ! busy)
    {
        if (session.lastExportFiles.size() > 0 && session.lastExportFolder.getFullPathName() != lastExportFolder)
        {
            lastExportFolder = session.lastExportFolder.getFullPathName();
            refreshAll();
            go (2);
            wasBusy = busy;
            return;
        }
        if (session.processed && page == 0 && ! session.chops.empty() && session.error.isEmpty())
        {
            refreshAll();
            go (1);
            wasBusy = busy;
            return;
        }
    }
    if (session.lastExportFiles.isEmpty())
        lastExportFolder.clear();
    wasBusy = busy;
    refreshAll();
}

void MainView::timerCallback()
{
    if (session.busy())
    {
        auto [msg, frac] = session.getProgress();
        lcd.set ("BUSY", msg.toUpperCase());
        loadPage->setBusy (true, msg, frac);
    }
    if (reviewPage->isVisible())
        reviewPage->tick();
}

void MainView::showMenu()
{
    juce::PopupMenu m, sizes;
    const auto cur = session.settings().get ("ui_size", "medium");
    sizes.addItem (11, "Small", true, cur == "small");
    sizes.addItem (12, "Medium (default)", true, cur == "medium");
    sizes.addItem (13, "Large", true, cur == "large");
    m.addItem (1, "Start over", ! session.busy());
    m.addSeparator();
    m.addSubMenu ("UI size", sizes);
    m.addSeparator();
    m.addItem (2, "About Xenakis");
    m.showMenuAsync (juce::PopupMenu::Options().withTargetComponent (&menuBtn), [this] (int r) {
        if (r == 1)
        {
            session.startOver();
            go (0);
        }
        else if (r >= 11 && r <= 13 && onUiSize)
            onUiSize (r == 11 ? "small" : r == 12 ? "medium" : "large");
        else if (r == 2)
            juce::AlertWindow::showAsync (juce::MessageBoxOptions()
                                              .withIconType (juce::MessageBoxIconType::NoIcon)
                                              .withTitle ("Xenakis " XENAKIS_VERSION)
                                              .withMessage ("Chops stems and multitracks into clean, labeled samples, right inside "
                                                            "your DAW.\n\nNamed for Iannis Xenakis, who built sound and buildings out "
                                                            "of straight lines.\n\nFont: IBM Plex Mono (OFL).")
                                              .withButton ("OK", 1),
                                          nullptr);
    });
}

void MainView::resized()
{
    ctx.narrow = getWidth() < FULL_W;
    if (! session.busy())
        showTempo();
    ctx.shortH = getHeight() < SHORT_H;
    auto r = getLocalBounds().reduced (20, 0).withTrimmedTop (18).withTrimmedBottom (16);
    auto top = r.removeFromTop (H_TOP);
    r.removeFromTop (12);
    menuBtn.setBounds (top.removeFromRight (H_TOP));
    top.removeFromRight (12);
    lever.setBounds (top.removeFromRight (132));
    top.removeFromRight (12);
    // brand plate
    brandText.setFontSpec (ctx.narrow ? 22.0f : 28.0f, 700, ctx.narrow ? 3.5f : 5.0f);
    badge.setVisible (! ctx.narrow);
    const int textW = (int) brandText.naturalWidth();
    const int brandW = 18 + 40 + 12 + textW + (ctx.narrow ? 0 : 6 + badge.naturalWidth()) + 18;
    brand.setBounds (top.removeFromLeft (brandW));
    {
        auto b = brand.getLocalBounds().reduced (18, 4);
        mark.setBounds (b.removeFromLeft (40).withSizeKeepingCentre (40, 40));
        b.removeFromLeft (12);
        brandText.setBounds (b.removeFromLeft (textW));
        b.removeFromLeft (6);
        if (! ctx.narrow)
            badge.setBounds (b.removeFromLeft (badge.naturalWidth()).withSizeKeepingCentre (badge.naturalWidth(), 30));
    }
    top.removeFromLeft (12);
    steps.setCompact (ctx.narrow);
    steps.setBounds (top.removeFromLeft (steps.minWidth()));
    top.removeFromLeft (12);
    lcd.setBounds (top);
    for (auto* p : std::initializer_list<juce::Component*> { loadPage.get(), reviewPage.get(), exportPage.get() })
        p->setBounds (r);
}

} // namespace xk::ui

// ================================================================== editor
XenakisEditor::XenakisEditor (XenakisProcessor& p) : AudioProcessorEditor (p), proc (p), view (p.session)
{
    uiSize = proc.session.settings().get ("ui_size", "medium");
    addAndMakeVisible (view);
    view.onUiSize = [this] (const juce::String& s) { setUiSize (s); };
    const float s = scale();
    const int w = proc.session.settings().get ("editor_w", "0").getIntValue();
    const int h = proc.session.settings().get ("editor_h", "0").getIntValue();
    setResizable (true, true);
    setResizeLimits ((int) (xk::ui::MainView::MIN_W * s), (int) (xk::ui::MainView::MIN_H * s), 4000, 3000);
    if (w > 100 && h > 100)
        setSize (juce::jmax (w, (int) (xk::ui::MainView::MIN_W * s)), juce::jmax (h, (int) (xk::ui::MainView::MIN_H * s)));
    else
        setSize ((int) (1480 * s), (int) (940 * s));
}

XenakisEditor::~XenakisEditor() = default;

float XenakisEditor::scale() const
{
    return uiSize == "small" ? 0.75f : uiSize == "large" ? 1.0f : 0.85f;
}

void XenakisEditor::setUiSize (const juce::String& s)
{
    uiSize = s;
    proc.session.settings().set ("ui_size", s);
    const float k = scale();
    setResizeLimits ((int) (xk::ui::MainView::MIN_W * k), (int) (xk::ui::MainView::MIN_H * k), 4000, 3000);
    setSize (juce::jmax (getWidth(), (int) (xk::ui::MainView::MIN_W * k)), juce::jmax (getHeight(), (int) (xk::ui::MainView::MIN_H * k)));
    resized();
}

void XenakisEditor::resized()
{
    const float s = scale();
    view.setTransform (juce::AffineTransform::scale (s));
    view.setBounds (0, 0, juce::roundToInt (getWidth() / s), juce::roundToInt (getHeight() / s));
    proc.session.settings().set ("editor_w", getWidth());
    proc.session.settings().set ("editor_h", getHeight());
}
