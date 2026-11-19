// The plug-in window: the chassis with the top bar and the Load / Review / Export pages,
// scaled to the chosen UI size.
#pragma once

#include "PluginProcessor.h"
#include "ui/Pages.h"

namespace xk::ui
{

// Page changes: the new page fades in on top while the page you leave drifts a little the other
// way underneath and fades out behind it. Interrupting carries on from what's on screen.
class PageFade : public juce::Component
{
public:
    PageFade() { setInterceptsMouseClicks (false, false); }
    void start (juce::Component& leaving, juce::Component& arriving, float direction);
    void paint (juce::Graphics&) override;

private:
    struct Layer
    {
        juce::Image img;
        std::unique_ptr<motion::Spring> alpha, offset;
        juce::Component* source = nullptr;
    };
    void tick();
    std::vector<Layer> layers;
    juce::Component::SafePointer<juce::Component> live;
    motion::Spring liveAlpha { 1.0, { 0.30, 1.0 } };
};

class MainView : public Chassis, private juce::ChangeListener, private juce::Timer
{
public:
    explicit MainView (Session& s);
    ~MainView() override;
    void go (int page);
    void resized() override;
    std::function<void (const juce::String& size)> onUiSize;
    // used by the snapshot / test tool
    ReviewPage& review() { return *reviewPage; }
    int currentPage() const { return page; }
    float exportAlpha() const { return exportPage->getAlpha(); }
    void setTheme (bool dark) { lever.setToggleState (dark, juce::sendNotification); applyTheme (dark); }
    static constexpr int MIN_W = 1000, MIN_H = 660, FULL_W = 1300, SHORT_H = 820;

private:
    void changeListenerCallback (juce::ChangeBroadcaster*) override;
    void timerCallback() override;
    void refreshAll();
    void applyTheme (bool dark);
    void showMenu();
    void showTempo();

    Session& session;
    Context ctx { session };
    LookAndFeel lnf;
    Plate brand;
    LogoMark mark;
    Text brandText { "XENAKIS", "plate_text", 28, 700, 5.0f };
    Badge badge { "XK-1  [v" XENAKIS_VERSION "]" };
    StepSelector steps { { "01 LOAD", "02 REVIEW", "03 EXPORT" } };
    Lcd lcd { "SONG TEMPO", juce::String::fromUTF8 ("\xe2\x80\x94 BPM"), 21 };
    LeverSwitch lever;
    HwButton menuBtn { "", HwButton::icon, "menu" };
    std::unique_ptr<LoadPage> loadPage;
    std::unique_ptr<ReviewPage> reviewPage;
    std::unique_ptr<ExportPage> exportPage;
    int page = 0;
    bool wasBusy = false;
    int exportsSeen = 0;   // Session::exportCount last time we looked
    PageFade fade;
    juce::TooltipWindow tooltips { this, 600 };
};

} // namespace xk::ui

class XenakisEditor : public juce::AudioProcessorEditor
{
public:
    explicit XenakisEditor (XenakisProcessor&);
    ~XenakisEditor() override;
    void resized() override;
    void paint (juce::Graphics& g) override { g.fillAll (juce::Colour (0xff1d1e21)); }
    xk::ui::MainView& getView() { return view; }
    void setUiSize (const juce::String& size);

private:
    float scale() const;
    XenakisProcessor& proc;
    xk::ui::MainView view;
    juce::String uiSize;
};
