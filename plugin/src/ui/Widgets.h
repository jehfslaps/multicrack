// Hardware-style widgets (port of multicrack/ui/skin/widgets.py).
#pragma once

#include "ui/Skin.h"

#include <functional>

namespace xk::ui
{

// ===================================================================== surfaces
class Chassis : public juce::Component
{
public:
    // a vertical bus right of `from`, tapping each target at a height fraction
    void addBus (juce::Component* from, std::vector<std::pair<juce::Component*, float>> targets);
    void paint (juce::Graphics&) override;
    void paintOverChildren (juce::Graphics&) override;

private:
    struct Bus { juce::Component* from; std::vector<std::pair<juce::Component*, float>> targets; };
    std::vector<Bus> buses;
};

class Module : public juce::Component
{
public:
    explicit Module (juce::String title = {}, bool outline = false, bool screws = true);
    juce::Rectangle<int> content() const;     // where children go
    void setTitle (const juce::String& t) { title = t; repaint(); }
    void setAlert (bool a) { alert = a; repaint(); }
    void paint (juce::Graphics&) override;
    int padL = 16, padT = 12, padR = 16, padB = 14;
    float titlePx = 15.0f;

private:
    juce::String title;
    bool outline, screws, alert = false;
};

class Plate : public juce::Component { public: void paint (juce::Graphics&) override; };
class Recess : public juce::Component { public: bool screws = false; void paint (juce::Graphics&) override; };
class Outline : public juce::Component { public: void paint (juce::Graphics&) override; };

class Tile : public juce::Component, public juce::SettableTooltipClient
{
public:
    bool alert = false;
    void paint (juce::Graphics&) override;
};

// ======================================================================= labels
class Text : public juce::Component
{
public:
    Text (juce::String text = {}, const char* colourKey = "on_dark", float px = 13, int weight = 400,
          float spacing = 0.3f, bool caps = false);
    void setText (const juce::String& t) { if (t != text) { text = t; repaint(); } }
    const juce::String& getText() const { return text; }
    void setColourKey (const char* k) { key = k; repaint(); }
    void setFontSpec (float px, int weight, float spacing) { fpx = px; fw = weight; fsp = spacing; repaint(); }
    juce::Justification justification = juce::Justification::centredLeft;
    bool elide = true, wrap = false;
    float naturalWidth() const;
    void paint (juce::Graphics&) override;

private:
    juce::String text;
    const char* key;
    float fpx;
    int fw;
    float fsp;
    bool caps;
};

// ====================================================================== buttons
class HwButton : public juce::Button
{
public:
    enum Variant { key, dark, red, icon, roundPlay, danger };
    HwButton (const juce::String& text, Variant v, juce::String iconName = {}, bool led = false, float px = 12.0f);
    int widthFor (const juce::String& text) const;
    int naturalWidth() const { return juce::jmax (floorW, widthFor (getButtonText())); }
    int floorW = 0;
    float iconSize = 16.0f;
    void paintButton (juce::Graphics&, bool over, bool down) override;

private:
    juce::Font textFont() const;
    Variant variant;
    juce::String iconName;
    bool hasLed;
    float px;
};

class LedToggle : public juce::Button
{
public:
    LedToggle (const juce::String& label, bool green = true, juce::String iconName = {});
    bool showState = true;
    juce::String label;
    int naturalWidth() const;
    void paintButton (juce::Graphics&, bool over, bool down) override;

private:
    bool green;
    juce::String iconName;
};

class StepSelector : public juce::Component
{
public:
    explicit StepSelector (juce::StringArray names);
    std::function<void (int)> onClick;
    void setCurrent (int i) { current = i; repaint(); }
    void setStepEnabled (int i, bool on) { enabled.set (i, on); repaint(); }
    void setCompact (bool c) { compact = c; repaint(); }
    int minWidth() const;
    void paint (juce::Graphics&) override;
    void mouseMove (const juce::MouseEvent&) override;
    void mouseExit (const juce::MouseEvent&) override;
    void mouseDown (const juce::MouseEvent&) override;

private:
    juce::Rectangle<float> cell (int i) const;
    juce::StringArray names;
    juce::Array<bool> enabled;
    int current = 0, hover = -1;
    bool compact = false;
};

class LeverSwitch : public juce::Button
{
public:
    LeverSwitch() : juce::Button ("theme") { setClickingTogglesState (true); }
    void paintButton (juce::Graphics&, bool over, bool down) override;
};

class Lcd : public juce::Component
{
public:
    Lcd (juce::String caption, juce::String value, float valuePx = 20.0f)
        : caption (std::move (caption)), value (std::move (value)), valuePx (valuePx) {}
    void set (const juce::String& cap, const juce::String& val) { caption = cap; value = val; repaint(); }
    void paint (juce::Graphics&) override;

private:
    juce::String caption, value;
    float valuePx;
};

class LedMeter : public juce::Component
{
public:
    void set (float f) { frac = juce::jlimit (0.0f, 1.0f, f); repaint(); }
    int segments = 28;
    void paint (juce::Graphics&) override;

private:
    float frac = 0;
};

class Trough : public juce::Component
{
public:
    void set (float f) { frac = juce::jlimit (0.0f, 1.0f, f); repaint(); }
    void paint (juce::Graphics&) override;

private:
    float frac = 0;
};

class DropBay : public juce::Component, public juce::FileDragAndDropTarget
{
public:
    std::function<void (const juce::StringArray&)> onDrop;
    std::function<void()> onClick;
    bool isInterestedInFileDrag (const juce::StringArray&) override { return true; }
    void fileDragEnter (const juce::StringArray&, int, int) override { hover = true; repaint(); }
    void fileDragExit (const juce::StringArray&) override { hover = false; repaint(); }
    void filesDropped (const juce::StringArray& files, int, int) override;
    void mouseUp (const juce::MouseEvent&) override { if (onClick) onClick(); }
    void paint (juce::Graphics&) override;

private:
    bool hover = false;
};

class IconLabel : public juce::Component
{
public:
    IconLabel (juce::String icon, const char* colourKey) : icon (std::move (icon)), key (colourKey) { setInterceptsMouseClicks (false, false); }
    void set (const juce::String& i, const char* k) { icon = i; key = k; repaint(); }
    void paint (juce::Graphics& g) override { drawIcon (g, icon, getLocalBounds().toFloat(), C (key), 1.5f); }

private:
    juce::String icon;
    const char* key;
};

class Lamp : public juce::Component
{
public:
    bool on = true;
    void paint (juce::Graphics&) override;
};

class ApprovePill : public juce::Button
{
public:
    ApprovePill() : juce::Button ("approve") { setClickingTogglesState (true); }
    void paintButton (juce::Graphics&, bool over, bool down) override;
};

class Badge : public juce::Component
{
public:
    explicit Badge (juce::String t) : text (std::move (t)) {}
    int naturalWidth() const;
    void paint (juce::Graphics&) override;

private:
    juce::String text;
};

class LogoMark : public juce::Component
{
public:
    void paint (juce::Graphics& g) override { paintLogo (g, getLocalBounds().toFloat(), false); }
};

class Separator : public juce::Component
{
public:
    bool vertical = true;
    void paint (juce::Graphics&) override;
};

// ======================================================================= fields
class Field : public juce::TextEditor
{
public:
    Field();
    void lookAndFeelChanged() override;
};

// ===================================================================== divider
// Draggable grip between a top and bottom panel. The top panel can be collapsed completely.
class PanelSplitter : public juce::Component, public juce::SettableTooltipClient
{
public:
    PanelSplitter (juce::Component& top, juce::Component& bottom, float defaultTop = 0.47f);
    std::function<void (float)> onMoved;       // fraction of the height for the top panel
    int topMin = 260, bottomMin = 150, grip = 18;
    void setFraction (float f);                // <= 0 collapses the top panel
    float fraction() const { return frac; }
    bool topHidden() const { return frac <= 0.0f; }
    void reset() { setFraction (defaultTop); if (onMoved) onMoved (frac); }
    void resized() override;
    void paint (juce::Graphics&) override;
    void mouseMove (const juce::MouseEvent&) override;
    void mouseDown (const juce::MouseEvent&) override;
    void mouseDrag (const juce::MouseEvent&) override;
    void mouseUp (const juce::MouseEvent&) override;
    void mouseDoubleClick (const juce::MouseEvent&) override;
    void mouseExit (const juce::MouseEvent&) override { hover = false; repaint(); }

private:
    juce::Rectangle<int> gripArea() const;
    juce::Component& top;
    juce::Component& bottom;
    float frac, defaultTop;
    bool hover = false, dragging = false;
    int dragOffset = 0;
};

} // namespace xk::ui
