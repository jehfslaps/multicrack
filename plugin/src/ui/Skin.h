// Xenakis hardware skin for JUCE: palettes, fonts, generated textures and the drawing kit.
// A port of multicrack/ui/skin/core.py so the plug-in looks like the desktop app.
#pragma once

#include <juce_gui_basics/juce_gui_basics.h>

namespace xk::ui
{

// ------------------------------------------------------------------ palette
void setDark (bool dark);
bool isDark();
juce::Colour C (const char* key, int alpha = -1);

// ------------------------------------------------------------------ metrics
constexpr int H_TOP = 60;     // top bar
constexpr int H_ROW = 50;     // control tiles and switches
constexpr int H_KEY = 40;     // main keys
constexpr int H_FIELD = 34;   // text fields and square buttons beside them
constexpr int H_SMALL = 30;   // small inline buttons
constexpr float RADIUS = 4.0f;

// -------------------------------------------------------------------- fonts
juce::Font font (float px, int weight = 400, float spacing = 0.0f);
float textWidth (const juce::String& s, const juce::Font& f);
void text (juce::Graphics& g, juce::Rectangle<float> r, const juce::String& s, const juce::Font& f,
           juce::Colour c, juce::Justification j = juce::Justification::centredLeft, bool elide = false);

// ----------------------------------------------------------------- textures
enum class Tex { bone, graphite, module };
const juce::Image& texture (Tex kind);
const juce::Image& chassisTexture();
void fillTextured (juce::Graphics& g, const juce::Path& p, const juce::Image& img,
                   juce::Colour tint = juce::Colours::transparentBlack);

// ----------------------------------------------------------------- draw kit
juce::Path rrect (juce::Rectangle<float> r, float rad);
void softShadow (juce::Graphics& g, juce::Rectangle<float> r, float rad, float depth = 6, int alpha = 70, float dy = 2.0f);
void bevelEdges (juce::Graphics& g, juce::Rectangle<float> r, float rad, juce::Colour hi, juce::Colour lo, float w = 1.0f);
void innerShadow (juce::Graphics& g, juce::Rectangle<float> r, float rad, int strength = 120, float size = 7);
void screw (juce::Graphics& g, juce::Point<float> c, float r = 5.0f);
void cornerScrews (juce::Graphics& g, juce::Rectangle<float> r, float inset = 9, float rad = 4.6f);
void led (juce::Graphics& g, juce::Point<float> c, float r, juce::Colour col, bool on, bool glow = true, float glowScale = 3.6f);
void hairlineFrame (juce::Graphics& g, juce::Rectangle<float> r, float rad, juce::Colour c, float w = 1.0f);
void node (juce::Graphics& g, juce::Point<float> c, float r, juce::Colour col, bool filled);
void paintGlass (juce::Graphics& g, juce::Rectangle<float> r, float radius = 4.0f);

// -------------------------------------------------------------------- icons
juce::Path iconPath (const juce::String& name, float s);
void drawIcon (juce::Graphics& g, const juce::String& name, juce::Rectangle<float> r, juce::Colour c,
               float width = 1.6f, bool filled = false);

// --------------------------------------------------------------------- logo
void paintLogoMark (juce::Graphics& g, juce::Point<float> c, float size, juce::Colour col);
void paintLogo (juce::Graphics& g, juce::Rectangle<float> r, bool plate);

// -------------------------------------------------------------- look & feel
class LookAndFeel : public juce::LookAndFeel_V4
{
public:
    LookAndFeel();
    void refreshColours();
    juce::Font getComboBoxFont (juce::ComboBox&) override;
    juce::Font getPopupMenuFont() override;
    juce::Font getLabelFont (juce::Label&) override;
    void drawComboBox (juce::Graphics&, int w, int h, bool down, int bx, int by, int bw, int bh, juce::ComboBox&) override;
    void positionComboBoxText (juce::ComboBox&, juce::Label&) override;
    void drawPopupMenuBackground (juce::Graphics&, int w, int h) override;
    void drawPopupMenuItem (juce::Graphics&, const juce::Rectangle<int>& area, bool isSeparator, bool isActive,
                            bool isHighlighted, bool isTicked, bool hasSubMenu, const juce::String& text,
                            const juce::String& shortcutKeyText, const juce::Drawable* icon,
                            const juce::Colour* textColour) override;
    void drawPopupMenuSectionHeader (juce::Graphics&, const juce::Rectangle<int>&, const juce::String&) override;
    void fillTextEditorBackground (juce::Graphics&, int w, int h, juce::TextEditor&) override;
    void drawTextEditorOutline (juce::Graphics&, int w, int h, juce::TextEditor&) override;
    void drawScrollbar (juce::Graphics&, juce::ScrollBar&, int x, int y, int w, int h, bool vertical, int thumbStart,
                        int thumbSize, bool over, bool down) override;
    int getDefaultScrollbarWidth() override { return 10; }
    void drawTooltip (juce::Graphics&, const juce::String& text, int w, int h) override;
    juce::Rectangle<int> getTooltipBounds (const juce::String& tipText, juce::Point<int> screenPos,
                                           juce::Rectangle<int> parentArea) override;
};

} // namespace xk::ui
