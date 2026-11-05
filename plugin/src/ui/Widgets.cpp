#include "ui/Widgets.h"

namespace xk::ui
{

// ================================================================== chassis
void Chassis::addBus (juce::Component* from, std::vector<std::pair<juce::Component*, float>> targets)
{
    buses.push_back ({ from, std::move (targets) });
}

void Chassis::paint (juce::Graphics& g)
{
    auto r = getLocalBounds().toFloat();
    g.fillAll (C ("chassis"));
    fillTextured (g, rrect (r, 0), chassisTexture());
    const auto grime = C ("grime");
    const float depth = 70.0f;
    auto edge = [&] (juce::Rectangle<float> rect, juce::Point<float> a, juce::Point<float> b) {
        g.setGradientFill (juce::ColourGradient (grime.withAlpha ((juce::uint8) 70), a, grime.withAlpha ((juce::uint8) 0), b, false));
        g.fillRect (rect);
    };
    edge (r.withHeight (depth), r.getTopLeft(), r.getTopLeft().translated (0, depth));
    edge (r.withTrimmedTop (r.getHeight() - depth), r.getBottomLeft(), r.getBottomLeft().translated (0, -depth));
    edge (r.withWidth (depth), r.getTopLeft(), r.getTopLeft().translated (depth, 0));
    edge (r.withTrimmedLeft (r.getWidth() - depth), r.getTopRight(), r.getTopRight().translated (-depth, 0));
    bevelEdges (g, r.reduced (1), 3, C ("chassis_hi", 200), C ("chassis_lo", 230), 1.5f);
    cornerScrews (g, r, 10, 4.8f);
}

void Chassis::paintOverChildren (juce::Graphics& g)
{
    // schematic bus wires in the gap right of a module
    auto shown = [this] (juce::Component* c) {
        for (; c != nullptr && c != this; c = c->getParentComponent())
            if (! c->isVisible())
                return false;
        return c == this;
    };
    for (auto& b : buses)
    {
        if (b.from == nullptr || ! shown (b.from))
            continue;
        auto ra = getLocalArea (b.from->getParentComponent(), b.from->getBounds()).toFloat();
        std::vector<std::pair<float, float>> taps;   // (x of target, y)
        for (auto& [w, f] : b.targets)
        {
            if (w == nullptr || ! shown (w))
                continue;
            auto rw = getLocalArea (w->getParentComponent(), w->getBounds()).toFloat();
            taps.push_back ({ rw.getX(), rw.getY() + rw.getHeight() * f });
        }
        if (taps.empty())
            continue;
        const float xb = (ra.getRight() + taps[0].first) / 2;
        float y0 = ra.getY() + ra.getHeight() * 0.08f, y1 = ra.getY() + ra.getHeight() * 0.92f;
        for (auto& t : taps)
        {
            y0 = juce::jmin (y0, t.second);
            y1 = juce::jmax (y1, t.second);
        }
        g.setColour (C ("wire", 210));
        g.drawLine (xb, y0, xb, y1, 1.3f);
        for (auto& t : taps)
        {
            g.setColour (C ("wire", 210));
            g.drawLine (ra.getRight() + 1, t.second, t.first - 1, t.second, 1.3f);
            node (g, { xb, t.second }, 2.6f, C ("wire"), true);
            node (g, { t.first - 3, t.second }, 2.4f, C ("wire"), false);
        }
        node (g, { xb, y0 }, 3.0f, C ("wire"), false);
        node (g, { xb, y1 }, 3.0f, C ("wire"), false);
    }
}

// =================================================================== module
Module::Module (juce::String t, bool o, bool s) : title (std::move (t)), outline (o), screws (s) {}

juce::Rectangle<int> Module::content() const
{
    const int titleH = title.isNotEmpty() ? 34 : 0;
    const int extra = outline ? 10 : 0;
    return getLocalBounds().withTrimmedLeft (padL + extra).withTrimmedRight (padR + extra)
        .withTrimmedTop (padT + titleH + extra).withTrimmedBottom (padB + extra);
}

void Module::paint (juce::Graphics& g)
{
    auto r = getLocalBounds().toFloat().withTrimmedLeft (3).withTrimmedRight (3).withTrimmedTop (2).withTrimmedBottom (5);
    softShadow (g, r, 5, 6, 90, 2.5f);
    auto path = rrect (r, 5);
    g.setColour (C ("module"));
    g.fillPath (path);
    fillTextured (g, path, texture (Tex::module));
    bevelEdges (g, r, 5, C ("module_hi"), C ("module_lo"), 1.6f);
    hairlineFrame (g, r.reduced (1.5f), 4, juce::Colour::fromRGBA (0, 0, 0, 120), 1.0f);
    if (screws)
        cornerScrews (g, r, 9, 4.3f);
    const int titleH = title.isNotEmpty() ? 34 : 0;
    if (title.isNotEmpty())
        ui::text (g, { r.getX() + 20, r.getY() + 8, r.getWidth() - 60, 26 }, title.toUpperCase(), font (titlePx, 600, 2.2f), C ("on_dark"));
    if (outline)
    {
        juce::Rectangle<float> o (r.getX() + 12, r.getY() + titleH + 6, r.getWidth() - 24, r.getHeight() - titleH - 18);
        hairlineFrame (g, o, 5, alert ? C ("warn") : C ("outline", 200), 1.1f);
    }
}

void Plate::paint (juce::Graphics& g)
{
    auto r = getLocalBounds().toFloat().withTrimmedLeft (2).withTrimmedRight (2).withTrimmedTop (2).withTrimmedBottom (4);
    softShadow (g, r, 5, 5, 70, 2);
    auto path = rrect (r, 5);
    g.setColour (C ("plate"));
    g.fillPath (path);
    fillTextured (g, path, chassisTexture(), juce::Colour::fromRGBA (255, 255, 255, isDark() ? 8 : 30));
    bevelEdges (g, r, 5, C ("chassis_hi"), C ("chassis_lo"), 1.6f);
    hairlineFrame (g, r.reduced (0.5f), 5, juce::Colour::fromRGBA (0, 0, 0, 90), 0.8f);
    cornerScrews (g, r, 8, 3.8f);
}

void Recess::paint (juce::Graphics& g)
{
    auto r = getLocalBounds().toFloat().reduced (1);
    auto path = rrect (r, 5);
    g.setColour (juce::Colour (0xff141517));
    g.fillPath (path);
    fillTextured (g, path, texture (Tex::module), juce::Colour::fromRGBA (0, 0, 0, 90));
    innerShadow (g, r, 5, 170, 8);
    bevelEdges (g, r, 5, C ("chassis_lo", 230), C ("chassis_hi", 230), 1.4f);
    if (screws)
        cornerScrews (g, r, 8, 3.6f);
}

void Outline::paint (juce::Graphics& g)
{
    hairlineFrame (g, getLocalBounds().toFloat(), 5, C ("outline", 210), 1.1f);
}

void Tile::paint (juce::Graphics& g)
{
    auto r = getLocalBounds().toFloat().reduced (0.5f);
    g.setGradientFill (juce::ColourGradient (juce::Colour (0xff2a2c30), r.getX(), r.getY(), juce::Colour (0xff222326), r.getX(), r.getBottom(), false));
    g.fillRoundedRectangle (r, 4);
    g.setColour (alert ? C ("warn") : juce::Colour (0xff3c3f44));
    g.drawRoundedRectangle (r, 4, alert ? 1.1f : 1.0f);
    g.setColour (juce::Colour::fromRGBA (255, 255, 255, 14));
    g.drawLine (r.getX() + 4, r.getY() + 1.2f, r.getRight() - 4, r.getY() + 1.2f, 1.0f);
}

// ===================================================================== text
Text::Text (juce::String t, const char* k, float px, int weight, float spacing, bool c)
    : text (std::move (t)), key (k), fpx (px), fw (weight), fsp (spacing), caps (c)
{
    setInterceptsMouseClicks (false, false);
}

float Text::naturalWidth() const
{
    return textWidth (caps ? text.toUpperCase() : text, font (fpx, fw, fsp)) + 2;
}

void Text::paint (juce::Graphics& g)
{
    const auto s = caps ? text.toUpperCase() : text;
    const auto f = font (fpx, fw, fsp);
    if (wrap)
    {
        g.setFont (f);
        g.setColour (C (key));
        g.drawFittedText (s, getLocalBounds(), justification, 4, 1.0f);
        return;
    }
    ui::text (g, getLocalBounds().toFloat(), s, f, C (key), justification, elide);
}

// ================================================================== buttons
HwButton::HwButton (const juce::String& t, Variant v, juce::String icon, bool led, float p)
    : juce::Button (t), variant (v), iconName (std::move (icon)), hasLed (led), px (p)
{
    setButtonText (t);
    setMouseCursor (juce::MouseCursor::PointingHandCursor);
    setWantsKeyboardFocus (false);
}

juce::Font HwButton::textFont() const
{
    const int w = (variant == key || variant == red) ? 600 : 500;
    return font (px, w, (variant != dark || px >= 12) ? 1.4f : 1.0f);
}

int HwButton::widthFor (const juce::String& t) const
{
    if (variant == icon || variant == roundPlay || variant == danger)
        return getHeight();
    float w = textWidth (t.toUpperCase(), textFont()) + 34;
    if (iconName.isNotEmpty())
        w += iconSize + 10;
    if (hasLed)
        w += 26;
    return (int) std::ceil (w);
}

void HwButton::paintButton (juce::Graphics& g, bool over, bool down)
{
    auto r = getLocalBounds().toFloat().withTrimmedLeft (1.5f).withTrimmedRight (1.5f).withTrimmedTop (1.5f).withTrimmedBottom (2.5f);
    const bool en = isEnabled();
    if (down)
        r = r.translated (0, 1);
    juce::Colour txt = C ("on_dark"), ic = C ("on_dark");
    if (variant == key)
    {
        if (en)
        {
            softShadow (g, r, 4, down ? 3.0f : 5.0f, 90, down ? 0.8f : 2.2f);
            auto top = C ("key_hi"), mid = C ("key"), bot = C ("key_lo");
            if (over) { top = top.brighter (0.03f); mid = mid.brighter (0.04f); }
            if (down) { top = mid.darker (0.04f); mid = mid.darker (0.06f); }
            juce::ColourGradient cg (top, r.getX(), r.getY(), bot, r.getX(), r.getBottom(), false);
            cg.addColour (0.55, mid);
            g.setGradientFill (cg);
            g.fillRoundedRectangle (r, RADIUS);
            g.setColour (juce::Colour::fromRGBA (20, 18, 16, 200));
            g.drawRoundedRectangle (r, RADIUS, 1.0f);
            g.setColour (juce::Colour::fromRGBA (255, 255, 255, 170));
            g.drawLine (r.getX() + 3, r.getY() + 1.4f, r.getRight() - 3, r.getY() + 1.4f, 1.0f);
            g.setColour (juce::Colour::fromRGBA (0, 0, 0, 50));
            g.drawLine (r.getX() + 3, r.getBottom() - 1.4f, r.getRight() - 3, r.getBottom() - 1.4f, 1.0f);
            txt = ic = C ("key_text");
        }
        else
        {
            g.setColour (juce::Colour (0xff3a3b3e));
            g.fillRoundedRectangle (r, RADIUS);
            g.setColour (juce::Colour (0xff4a4c50));
            g.drawRoundedRectangle (r, RADIUS, 1.0f);
            txt = ic = juce::Colour (0xff7c7a75);
        }
    }
    else if (variant == red)
    {
        if (en)
        {
            juce::ColourGradient gl (juce::Colour::fromRGBA (255, 70, 50, (juce::uint8) (over ? 70 : 40)), r.getCentreX(), r.getCentreY(),
                                     juce::Colour::fromRGBA (255, 70, 50, 0), r.getCentreX() + r.getWidth() * 0.7f, r.getCentreY(), true);
            g.setGradientFill (gl);
            g.fillRoundedRectangle (r.expanded (6), 9);
            softShadow (g, r, 4, 4, 100, 1.5f);
            auto hi = C ("red_hi"), mid = C ("red"), lo = C ("red_lo");
            if (over) { hi = hi.brighter (0.08f); mid = mid.brighter (0.08f); }
            if (down) { hi = mid; mid = mid.darker (0.1f); }
            juce::ColourGradient cg (hi, r.getX(), r.getY(), lo, r.getX(), r.getBottom(), false);
            cg.addColour (0.6, mid);
            g.setGradientFill (cg);
            g.fillRoundedRectangle (r, RADIUS);
            g.setColour (juce::Colour::fromRGBA (40, 10, 6, 220));
            g.drawRoundedRectangle (r, RADIUS, 1.2f);
            g.setColour (juce::Colour::fromRGBA (255, 220, 200, 110));
            g.drawLine (r.getX() + 3, r.getY() + 1.5f, r.getRight() - 3, r.getY() + 1.5f, 1.0f);
            txt = ic = juce::Colour (0xfffff3ec);
        }
        else
        {
            g.setColour (juce::Colour (0xff3a3b3e));
            g.fillRoundedRectangle (r, RADIUS);
            g.setColour (juce::Colour (0xff4c4e52));
            g.drawRoundedRectangle (r, RADIUS, 1.0f);
            txt = ic = juce::Colour (0xff85827c);
        }
    }
    else if (variant == danger)
    {
        const auto col = en ? C ("warn") : juce::Colour (0xff5a5a5a);
        if (en)
        {
            g.setColour (juce::Colour::fromRGBA (232, 100, 78, (juce::uint8) (over ? 40 : 14)));
            g.fillRoundedRectangle (r, 3);
        }
        g.setColour (col);
        g.drawRoundedRectangle (r, 3, 1.2f);
        drawIcon (g, "x", r.reduced (7), col, 1.8f);
        return;
    }
    else if (variant == roundPlay)
    {
        const auto c = r.getCentre();
        const float rad = juce::jmin (r.getWidth(), r.getHeight()) / 2;
        softShadow (g, juce::Rectangle<float> (2 * rad, 2 * rad).withCentre (c), rad, 3, 80, 1.5f);
        juce::ColourGradient cg (over ? juce::Colour (0xff46494e) : juce::Colour (0xff3a3c40), c.x, c.y - rad * 0.5f,
                                 juce::Colour (0xff121314), c.x, c.y - rad * 0.5f + rad * 1.6f, true);
        g.setGradientFill (cg);
        const auto e = juce::Rectangle<float> (2 * (rad - 1), 2 * (rad - 1)).withCentre (c);
        g.fillEllipse (e);
        g.setColour (over ? juce::Colour (0xffc9c4ba) : juce::Colour (0xff8e8a83));
        g.drawEllipse (e, 1.5f);
        drawIcon (g, iconName.isEmpty() ? "play" : iconName,
                  juce::Rectangle<float> (rad * 1.1f, rad * 1.1f).withCentre (c.translated (1, 0)), juce::Colour (0xfff3efe7));
        return;
    }
    else   // dark / icon
    {
        juce::ColourGradient cg (over ? juce::Colour (0xff2c2f33) : juce::Colour (0xff24262a), r.getX(), r.getY(),
                                 juce::Colour (0xff17181a), r.getX(), r.getBottom(), false);
        if (down)
            cg = juce::ColourGradient (juce::Colour (0xff141516), r.getX(), r.getY(), juce::Colour (0xff17181a), r.getX(), r.getBottom(), false);
        g.setGradientFill (cg);
        g.fillRoundedRectangle (r, RADIUS);
        auto border = en ? juce::Colour (0xff8a867f) : juce::Colour (0xff45474b);
        if (over && en)
            border = juce::Colour (0xffd9d4ca);
        if (getToggleState())
            border = C ("red_hi");
        g.setColour (border);
        g.drawRoundedRectangle (r, RADIUS, 1.1f);
        txt = ic = en ? C ("on_dark") : juce::Colour (0xff6d6a65);
        if (variant == icon)
        {
            drawIcon (g, iconName, r.reduced (8), ic, 1.5f);
            return;
        }
    }
    // contents: [led] [icon] TEXT
    const auto f = textFont();
    const auto label = getButtonText().toUpperCase();
    const float tw = textWidth (label, f);
    const float iw = iconName.isNotEmpty() ? iconSize + 9 : 0;
    const float lw = hasLed ? 24.0f : 0.0f;
    float x = r.getCentreX() - (lw + iw + tw) / 2;
    if (hasLed)
    {
        led (g, { x + 7, r.getCentreY() }, 6.0f, C ("led_red"), en);
        x += lw;
    }
    if (iconName.isNotEmpty())
    {
        drawIcon (g, iconName, { x, r.getCentreY() - iconSize / 2, iconSize, iconSize }, ic, 1.7f);
        x += iw;
    }
    ui::text (g, { x, r.getY(), tw + 6, r.getHeight() }, label, f, txt);
}

LedToggle::LedToggle (const juce::String& l, bool g, juce::String icon)
    : juce::Button (l), label (l), green (g), iconName (std::move (icon))
{
    setClickingTogglesState (true);
    setMouseCursor (juce::MouseCursor::PointingHandCursor);
    setWantsKeyboardFocus (false);
}

int LedToggle::naturalWidth() const
{
    const auto f = font (12, 600, 1.4f);
    float w = 30 + textWidth ((label + (showState ? "  ON" : "")).toUpperCase(), f) + 22;
    if (iconName.isNotEmpty())
        w += 26;
    return (int) std::ceil (w);
}

void LedToggle::paintButton (juce::Graphics& g, bool over, bool)
{
    auto r = getLocalBounds().toFloat().reduced (1);
    const bool en = isEnabled(), on = getToggleState() && en;
    g.setGradientFill (juce::ColourGradient (over && en ? juce::Colour (0xff2c2e32) : juce::Colour (0xff26282b), r.getX(), r.getY(),
                                             juce::Colour (0xff1c1d20), r.getX(), r.getBottom(), false));
    g.fillRoundedRectangle (r, RADIUS);
    g.setColour (en ? juce::Colour (0xff4a4d52) : juce::Colour (0xff36383c));
    g.drawRoundedRectangle (r, RADIUS, 1.0f);
    const auto col = green ? C ("led_green") : C ("led_red");
    led (g, { r.getX() + 17, r.getCentreY() }, 5.2f, col, on);
    float x = r.getX() + 32;
    if (iconName.isNotEmpty())
    {
        drawIcon (g, iconName, { x, r.getCentreY() - 9, 18, 18 }, on ? col : C ("on_dark_muted"), 1.7f);
        x += 26;
    }
    const auto f = font (12, 600, 1.4f);
    const auto l = label.toUpperCase();
    ui::text (g, { x, r.getY(), r.getWidth(), r.getHeight() }, l, f, en ? C ("on_dark") : juce::Colour (0xff6d6a65));
    if (showState)
        ui::text (g, { x + textWidth (l, f) + 10, r.getY(), 60, r.getHeight() }, getToggleState() ? "ON" : "OFF", f,
              on ? col : C ("on_dark_dim"));
}

// ============================================================ step selector
StepSelector::StepSelector (juce::StringArray n) : names (std::move (n))
{
    for (int i = 0; i < names.size(); ++i)
        enabled.add (true);
    setMouseCursor (juce::MouseCursor::PointingHandCursor);
}

int StepSelector::minWidth() const
{
    const auto f = font (compact ? 11.0f : 12.0f, 600, compact ? 0.8f : 1.6f);
    float cellW = 0;
    for (auto& n : names)
        cellW = juce::jmax (cellW, textWidth (n.toUpperCase(), f));
    return (int) ((cellW + (compact ? 44 : 52)) * names.size() + 4 * names.size() + 14);
}

juce::Rectangle<float> StepSelector::cell (int i) const
{
    auto r = getLocalBounds().toFloat().reduced (7);
    const float w = r.getWidth() / names.size();
    return { r.getX() + i * w + 2, r.getY(), w - 4, r.getHeight() };
}

void StepSelector::mouseMove (const juce::MouseEvent& e)
{
    int h = -1;
    for (int i = 0; i < names.size(); ++i)
        if (cell (i).contains (e.position))
            h = i;
    if (h != hover) { hover = h; repaint(); }
}

void StepSelector::mouseExit (const juce::MouseEvent&) { hover = -1; repaint(); }

void StepSelector::mouseDown (const juce::MouseEvent& e)
{
    for (int i = 0; i < names.size(); ++i)
        if (cell (i).contains (e.position) && enabled[i] && onClick)
            onClick (i);
}

void StepSelector::paint (juce::Graphics& g)
{
    auto r = getLocalBounds().toFloat().reduced (1);
    auto path = rrect (r, 5);
    g.setColour (juce::Colour (0xff141517));
    g.fillPath (path);
    fillTextured (g, path, texture (Tex::module), juce::Colour::fromRGBA (0, 0, 0, 100));
    innerShadow (g, r, 5, 170, 8);
    bevelEdges (g, r, 5, C ("chassis_lo", 230), C ("chassis_hi", 230), 1.4f);
    for (int i = 0; i < names.size(); ++i)
    {
        const auto c = cell (i);
        const bool active = i == current, en = enabled[i];
        const auto base = (hover == i && en) ? juce::Colour (0xff2a2c30) : juce::Colour (0xff232528);
        g.setGradientFill (juce::ColourGradient (active ? juce::Colour (0xff1c1d20) : base.brighter (0.12f), c.getX(), c.getY(),
                                                 juce::Colour (0xff17181a), c.getX(), c.getBottom(), false));
        g.fillRoundedRectangle (c, 3);
        g.setColour (juce::Colour (0xff3f4247));
        g.drawRoundedRectangle (c, 3, 1.0f);
        if (! active)
        {
            g.setColour (juce::Colour::fromRGBA (255, 255, 255, 18));
            g.drawLine (c.getX() + 3, c.getY() + 1.3f, c.getRight() - 3, c.getY() + 1.3f, 1.0f);
        }
        const float lx = compact ? 14.0f : 18.0f, tx = compact ? 26.0f : 34.0f;
        led (g, { c.getX() + lx, c.getCentreY() }, compact ? 4.8f : 5.5f, C ("led_red"), active);
        const auto num = names[i].upToFirstOccurrenceOf (" ", false, false);
        const auto nm = names[i].fromFirstOccurrenceOf (" ", false, false).toUpperCase();
        const auto f = font (compact ? 11.0f : 12.0f, active ? 600 : 500, compact ? 0.8f : 1.6f);
        const auto col = active ? C ("on_dark") : (en ? C ("on_dark_muted") : C ("on_dark_dim"));
        ui::text (g, { c.getX() + tx, c.getY(), 30, c.getHeight() }, num, f, active ? C ("led_red") : col);
        ui::text (g, { c.getX() + tx + textWidth (num, f) + (compact ? 5 : 8), c.getY(), c.getWidth(), c.getHeight() }, nm, f, col);
    }
}

// ============================================================ lever switch
void LeverSwitch::paintButton (juce::Graphics& g, bool, bool)
{
    auto r = getLocalBounds().toFloat().reduced (1);
    auto path = rrect (r, 5);
    g.setColour (juce::Colour (0xff141517));
    g.fillPath (path);
    fillTextured (g, path, texture (Tex::module), juce::Colour::fromRGBA (0, 0, 0, 100));
    innerShadow (g, r, 5, 160, 8);
    bevelEdges (g, r, 5, C ("chassis_lo", 230), C ("chassis_hi", 230), 1.4f);
    const juce::Point<float> c (r.getX() + 30, r.getCentreY());
    juce::ColourGradient nut (juce::Colour (0xffe9e7e2), c.x - 3, c.y - 4, juce::Colour (0xff3e3d3a), c.x - 3 + 16, c.y - 4, true);
    nut.addColour (0.6, juce::Colour (0xff8e8b85));
    g.setGradientFill (nut);
    g.fillEllipse (juce::Rectangle<float> (22, 22).withCentre (c));
    g.setColour (juce::Colour::fromRGBA (0, 0, 0, 160));
    g.drawEllipse (juce::Rectangle<float> (22, 22).withCentre (c), 0.8f);
    g.setColour (juce::Colour (0xff2a2a2a));
    g.fillEllipse (juce::Rectangle<float> (9, 9).withCentre (c));
    const bool down = getToggleState();
    const juce::Point<float> tip (c.x + 2, c.y + (down ? 15.0f : -15.0f));
    g.setColour (juce::Colour::fromRGBA (0, 0, 0, 90));
    g.drawLine (c.x + 1, c.y + 1.5f, tip.x + 1, tip.y + 1.5f, 6.5f);
    juce::ColourGradient lg (juce::Colour (0xff7a7874), c.x - 3, 0, juce::Colour (0xff8e8b86), c.x + 4, 0, false);
    lg.addColour (0.4, juce::Colour (0xfff4f2ee));
    g.setGradientFill (lg);
    juce::Path stick;
    stick.startNewSubPath (c);
    stick.lineTo (tip);
    g.strokePath (stick, juce::PathStrokeType (5.2f, juce::PathStrokeType::curved, juce::PathStrokeType::rounded));
    juce::ColourGradient tg (juce::Colours::white, tip.x - 1.5f, tip.y - 1.5f, juce::Colour (0xff9c9993), tip.x + 4.5f, tip.y - 1.5f, true);
    g.setGradientFill (tg);
    g.fillEllipse (juce::Rectangle<float> (8.6f, 8.6f).withCentre (tip));
    const auto f = font (11.5f, 600, 1.6f);
    ui::text (g, { r.getX() + 52, r.getY() + 4, 80, r.getHeight() / 2 - 4 }, "LIGHT", f, down ? C ("on_dark_dim") : C ("on_dark"));
    ui::text (g, { r.getX() + 52, r.getCentreY(), 80, r.getHeight() / 2 - 4 }, "DARK", f, down ? C ("on_dark") : C ("on_dark_dim"));
}

// ===================================================================== lcd
void Lcd::paint (juce::Graphics& g)
{
    auto r = getLocalBounds().toFloat().reduced (1);
    auto path = rrect (r, 5);
    g.setGradientFill (juce::ColourGradient (juce::Colour (0xff0e0f10), r.getX(), r.getY(), juce::Colour (0xff16181a), r.getX(), r.getBottom(), false));
    g.fillPath (path);
    innerShadow (g, r, 5, 200, 9);
    bevelEdges (g, r, 5, C ("chassis_lo", 230), C ("chassis_hi", 230), 1.4f);
    {
        juce::Graphics::ScopedSaveState ss (g);
        g.reduceClipRegion (path);
        g.setColour (juce::Colour::fromRGBA (255, 255, 255, 7));
        for (float y = r.getY() + 2; y < r.getBottom(); y += 3)
            g.drawHorizontalLine ((int) y, r.getX(), r.getRight());
        g.setGradientFill (juce::ColourGradient (juce::Colour::fromRGBA (255, 255, 255, 14), r.getX(), r.getY(),
                                                 juce::Colour::fromRGBA (255, 255, 255, 0), r.getX(), r.getY() + r.getHeight() * 0.5f, false));
        g.fillRect (r.withHeight (r.getHeight() * 0.5f));
    }
    auto inner = r.withTrimmedLeft (16).withTrimmedRight (14).withTrimmedTop (4).withTrimmedBottom (4);
    if (caption.isNotEmpty())
    {
        ui::text (g, { inner.getX(), inner.getY() + 2, inner.getWidth(), 15 }, caption.toUpperCase(), font (10.5f, 500, 1.8f), C ("on_dark_muted"), juce::Justification::centredLeft, true);
        ui::text (g, { inner.getX(), inner.getY() + 16, inner.getWidth(), inner.getHeight() - 16 }, value, font (valuePx, 500, 1.4f), C ("glass_text"), juce::Justification::centredLeft, true);
    }
    else
        ui::text (g, inner, value, font (valuePx, 500, 1.4f), C ("glass_text"), juce::Justification::centredLeft, true);
}

// ================================================================== meters
void LedMeter::paint (juce::Graphics& g)
{
    auto r = getLocalBounds().toFloat().reduced (1);
    g.setColour (juce::Colour (0xff0d0e0f));
    g.fillRoundedRectangle (r, 3);
    innerShadow (g, r, 3, 200, 6);
    g.setColour (juce::Colour (0xff3a3d42));
    g.drawRoundedRectangle (r, 3, 1.0f);
    auto inner = r.reduced (6);
    const int n = segments;
    const float gap = 2.5f, w = (inner.getWidth() - gap * (n - 1)) / n;
    const int lit = frac < 1 ? (int) std::round (frac * n) : n;
    const auto on = C ("led_green");
    for (int i = 0; i < n; ++i)
    {
        juce::Rectangle<float> seg (inner.getX() + i * (w + gap), inner.getY(), w, inner.getHeight());
        if (i < lit)
        {
            g.setColour (on.withAlpha ((juce::uint8) 60));
            g.fillRoundedRectangle (seg.expanded (1.5f), 2);
            g.setGradientFill (juce::ColourGradient (on.brighter (0.4f), seg.getX(), seg.getY(), on.darker (0.1f), seg.getX(), seg.getBottom(), false));
        }
        else
            g.setColour (juce::Colour::fromRGBA (40, 70, 50, 120));
        g.fillRoundedRectangle (seg, 1.5f);
    }
}

void Trough::paint (juce::Graphics& g)
{
    auto r = getLocalBounds().toFloat().withTrimmedRight (58);
    r = r.withHeight (14).withY (((float) getHeight() - 14) / 2);
    g.setColour (juce::Colour (0xff16171a));
    g.fillRoundedRectangle (r, 7);
    innerShadow (g, r, 7, 200, 6);
    g.setColour (C ("chassis_lo"));
    g.drawRoundedRectangle (r, 7, 1.0f);
    if (frac > 0)
    {
        juce::Rectangle<float> fr (r.getX() + 2, r.getY() + 2, (r.getWidth() - 4) * frac, r.getHeight() - 4);
        g.setGradientFill (juce::ColourGradient (C ("red_hi"), fr.getX(), fr.getY(), C ("red_lo"), fr.getX(), fr.getBottom(), false));
        g.fillRoundedRectangle (fr, 5);
    }
    ui::text (g, { r.getRight() + 10, 0, 48, (float) getHeight() }, juce::String ((int) std::round (frac * 100)) + "%", font (12.5f, 500, 1.0f), C ("chassis_text"));
}

// ================================================================ drop bay
void DropBay::filesDropped (const juce::StringArray& files, int, int)
{
    hover = false;
    repaint();
    if (onDrop)
        onDrop (files);
}

void DropBay::paint (juce::Graphics& g)
{
    auto r = getLocalBounds().toFloat().reduced (2);
    if (hover)
    {
        g.setColour (juce::Colour::fromRGBA (200, 80, 60, 30));
        g.fillRoundedRectangle (r, 5);
    }
    const juce::String label = "DROP STEMS OR A WHOLE STEM FOLDER HERE";
    float px = 13.5f, sp = 3.0f;
    while (px > 9.5f && textWidth (label, font (px, 500, sp)) > r.getWidth() - 24)
    {
        px -= 0.5f;
        sp = juce::jmax (0.8f, sp - 0.3f);
    }
    juce::Path border;
    border.addRoundedRectangle (r, 5);
    juce::Path dashed;
    const float dashes[] = { 4.0f, 3.0f };
    juce::PathStrokeType (1.2f).createDashedStroke (dashed, border, dashes, 2);
    g.setColour (hover ? C ("warn") : juce::Colour (0xff8c8880));
    g.fillPath (dashed);
    juce::Rectangle<float> box (r.getCentreX() - 27, r.getY() + r.getHeight() * 0.2f, 54, 40);
    g.setColour (C ("on_dark"));
    g.drawRoundedRectangle (box, 3, 1.4f);
    drawIcon (g, "upload", box.reduced (13, 6), C ("on_dark"), 1.5f);
    ui::text (g, { r.getX(), box.getBottom() + 12, r.getWidth(), 24 }, label, font (px, 500, sp), C ("on_dark"), juce::Justification::centred);
}

// ==================================================================== misc
void Lamp::paint (juce::Graphics& g)
{
    const float half = juce::jmin (getWidth(), getHeight()) / 2.0f, r = half / 2.3f;
    led (g, getLocalBounds().toFloat().getCentre(), r, C ("led_green"), on, true, half / r - 0.05f);
}

void ApprovePill::paintButton (juce::Graphics& g, bool over, bool)
{
    auto r = getLocalBounds().toFloat().withTrimmedLeft (1).withTrimmedRight (1).withTrimmedTop (2).withTrimmedBottom (2);
    const bool on = getToggleState();
    g.setGradientFill (juce::ColourGradient (over ? juce::Colour (0xff2a2c30) : juce::Colour (0xff232528), r.getX(), r.getY(),
                                             juce::Colour (0xff18191b), r.getX(), r.getBottom(), false));
    g.fillRoundedRectangle (r, RADIUS);
    g.setColour (on ? juce::Colour::fromRGBA (75, 224, 122, 140) : juce::Colour (0xff45484d));
    g.drawRoundedRectangle (r, RADIUS, 1.0f);
    led (g, { r.getX() + 15, r.getCentreY() }, 4.8f, C ("led_green"), on);
    const auto col = on ? C ("on_dark") : C ("on_dark_muted");
    drawIcon (g, "check", { r.getX() + 28, r.getCentreY() - 8, 16, 16 }, on ? C ("led_green") : col, 2.0f);
    const float px = getWidth() >= 130 ? 11.5f : 10.5f;
    ui::text (g, r.withTrimmedLeft (50), on ? "APPROVED" : "APPROVE", font (px, 600, px > 11 ? 1.3f : 0.8f), col);
}

int Badge::naturalWidth() const
{
    return (int) textWidth (text, font (12.5f, 500, 1.2f)) + 26;
}

void Badge::paint (juce::Graphics& g)
{
    auto r = getLocalBounds().toFloat().reduced (1);
    g.setColour (juce::Colour::fromRGBA (0, 0, 0, 18));
    g.fillRoundedRectangle (r, 3);
    g.setColour (juce::Colour::fromRGBA (0, 0, 0, 110));
    g.drawRoundedRectangle (r, 3, 1.0f);
    g.setColour (juce::Colour::fromRGBA (255, 255, 255, 60));
    g.drawLine (r.getX() + 2, r.getBottom() + 0.5f, r.getRight() - 2, r.getBottom() + 0.5f, 1.0f);
    ui::text (g, r, text, font (12.5f, 500, 1.2f), C ("plate_text"), juce::Justification::centred);
}

void Separator::paint (juce::Graphics& g)
{
    if (vertical)
    {
        const float x = getWidth() / 2.0f;
        g.setColour (juce::Colour::fromRGBA (0, 0, 0, 160));
        g.drawLine (x, 4, x, (float) getHeight() - 4, 1.0f);
        g.setColour (juce::Colour::fromRGBA (255, 255, 255, 20));
        g.drawLine (x + 1, 4, x + 1, (float) getHeight() - 4, 1.0f);
    }
    else
    {
        const float y = getHeight() / 2.0f;
        g.setColour (juce::Colour::fromRGBA (0, 0, 0, 160));
        g.drawLine (4, y, (float) getWidth() - 4, y, 1.0f);
        g.setColour (juce::Colour::fromRGBA (255, 255, 255, 20));
        g.drawLine (4, y + 1, (float) getWidth() - 4, y + 1, 1.0f);
    }
}

// =================================================================== field
Field::Field()
{
    setFont (font (14.0f, 400, 0.2f));
    setIndents (10, 8);
    setJustification (juce::Justification::centredLeft);
    setSelectAllWhenFocused (false);
}

void Field::lookAndFeelChanged()
{
    juce::TextEditor::lookAndFeelChanged();
    applyFontToAllText (font (14.0f, 400, 0.2f));
}

// ================================================================ divider
PanelSplitter::PanelSplitter (juce::Component& t, juce::Component& b, float def)
    : top (t), bottom (b), frac (def), defaultTop (def)
{
    addAndMakeVisible (top);
    addAndMakeVisible (bottom);
    setTooltip ("Drag to give the editor or the list more room. Drag all the way up to hide the editor. "
                "Double-click to reset.");
}

void PanelSplitter::setFraction (float f)
{
    frac = f <= 0.0f ? 0.0f : juce::jlimit (0.0f, 0.95f, f);
    resized();
    repaint();
}

void PanelSplitter::resized()
{
    const int h = getHeight(), w = getWidth();
    const int avail = juce::jmax (0, h - grip);
    int t = 0;
    if (frac > 0)
    {
        t = (int) std::round (avail * frac);
        t = juce::jlimit (juce::jmin (topMin, avail - bottomMin), juce::jmax (0, avail - bottomMin), t);
        t = juce::jmax (0, t);
    }
    top.setVisible (t > 0);
    top.setBounds (0, 0, w, t);
    bottom.setBounds (0, t + grip, w, juce::jmax (0, h - t - grip));
}

juce::Rectangle<int> PanelSplitter::gripArea() const
{
    return { 0, top.isVisible() ? top.getBottom() : 0, getWidth(), grip };
}

void PanelSplitter::paint (juce::Graphics& g)
{
    auto r = gripArea().toFloat();
    const float cy = r.getCentreY();
    const float gw = 72, gh = 10;
    juce::Rectangle<float> gr (r.getCentreX() - gw / 2, cy - gh / 2, gw, gh);
    for (auto [x0, x1] : { std::pair { r.getX() + 14, gr.getX() - 10 }, std::pair { gr.getRight() + 10, r.getRight() - 14 } })
    {
        if (x1 - x0 < 8)
            continue;
        g.setColour (C ("chassis_lo", 200));
        g.drawLine (x0, cy - 0.5f, x1, cy - 0.5f, 1.0f);
        g.setColour (C ("chassis_hi", 200));
        g.drawLine (x0, cy + 0.5f, x1, cy + 0.5f, 1.0f);
    }
    softShadow (g, gr, 3, 2, 70, 1.2f);
    g.setGradientFill (juce::ColourGradient ((hover || dragging) ? juce::Colours::white : C ("key_hi"), gr.getX(), gr.getY(),
                                             C ("key_lo"), gr.getX(), gr.getBottom(), false));
    g.fillRoundedRectangle (gr, 3);
    g.setColour (juce::Colour::fromRGBA (20, 18, 16, 200));
    g.drawRoundedRectangle (gr, 3, 1.0f);
    g.setColour (juce::Colour::fromRGBA (40, 36, 32, 170));
    for (float dx : { -9.0f, -3.0f, 3.0f, 9.0f })
        g.drawLine (gr.getCentreX() + dx, gr.getY() + 2.5f, gr.getCentreX() + dx, gr.getBottom() - 2.5f, 1.1f);
    if (topHidden())
        ui::text (g, { gr.getRight() + 18, r.getY(), 460, r.getHeight() }, juce::String::fromUTF8 ("EDITOR HIDDEN  ·  DRAG DOWN OR DOUBLE-CLICK TO SHOW"),
              font (10.5f, 600, 1.8f), C ("chassis_text"));
}

void PanelSplitter::mouseMove (const juce::MouseEvent& e)
{
    const bool h = gripArea().contains (e.getPosition());
    setMouseCursor (h ? juce::MouseCursor::UpDownResizeCursor : juce::MouseCursor::NormalCursor);
    if (h != hover) { hover = h; repaint(); }
}

void PanelSplitter::mouseDown (const juce::MouseEvent& e)
{
    dragging = gripArea().contains (e.getPosition());
    dragOffset = e.y - gripArea().getY();
    repaint();
}

void PanelSplitter::mouseDrag (const juce::MouseEvent& e)
{
    if (! dragging)
        return;
    const int avail = juce::jmax (1, getHeight() - grip);
    int t = e.y - dragOffset;
    if (t < topMin / 2)
        t = 0;                                   // drag past half the minimum: hide the editor
    else
        t = juce::jlimit (juce::jmin (topMin, avail - bottomMin), juce::jmax (0, avail - bottomMin), t);
    setFraction (t <= 0 ? 0.0f : (float) t / avail);
    if (onMoved) onMoved (frac);
}

void PanelSplitter::mouseUp (const juce::MouseEvent&)
{
    dragging = false;
    repaint();
}

void PanelSplitter::mouseDoubleClick (const juce::MouseEvent& e)
{
    if (gripArea().contains (e.getPosition()))
        reset();
}

} // namespace xk::ui
