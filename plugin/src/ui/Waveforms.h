// Edison-style waveforms: peak cache, the small list waveform and the chop view.
#pragma once

#include "engine/Model.h"
#include "ui/Skin.h"

#include <functional>
#include <memory>

namespace xk::ui
{

// Min/max per pixel column, with a coarse block level for zoomed-out views.
class PeakCache
{
public:
    explicit PeakCache (StemPtr stem);   // keeps the stem alive while shown
    void columns (int a, int b, int cols, std::vector<float>& mins, std::vector<float>& maxs) const;
    int length() const { return (int) m.size(); }

private:
    static constexpr int BLOCK = 256;
    StemPtr stem;
    const Vec& m;
    std::vector<float> bmin, bmax;
};

float waveGain (const std::vector<float>& mins, const std::vector<float>& maxs);
void paintWave (juce::Graphics& g, juce::Rectangle<float> r, const std::vector<float>& mins, const std::vector<float>& maxs,
                float gain, juce::Colour fill, juce::Colour edge, bool centre = true);

class MiniWave : public juce::Component
{
public:
    MiniWave() { setInterceptsMouseClicks (false, false); }
    void set (std::shared_ptr<PeakCache> c, int a, int b, bool reverse);
    void setPlayhead (float f) { if (f != playhead) { playhead = f; repaint(); } }
    void paint (juce::Graphics&) override;

private:
    std::shared_ptr<PeakCache> cache;
    int a = 0, b = 0;
    bool reverse = false;
    float playhead = -1;
};

// The selected chop inside its stem. Click anywhere to play the stem from that spot. Drag a red
// flag to trim, drag the grab bar between the flags to slide the whole chop (same length), or
// drag across the waveform to pick a new section. Wheel zooms (all the way out to the whole
// stem); Shift+wheel moves left / right.
class ChopView : public juce::Component, public juce::SettableTooltipClient
{
public:
    void set (std::shared_ptr<PeakCache> c, int n, int sr, int start, int end, bool keepView);
    void setFx (int fadeInSamples, int fadeOutSamples, bool reverse);
    void clear() { cache.reset(); drag = None; repaint(); }
    void setPlayhead (int s) { if (s != playhead) { playhead = s; repaint(); } }
    void paint (juce::Graphics&) override;

    // view
    void setView (int a, int b);
    void zoom (double factor, int centre = -1);
    void showChop();
    void showAll() { setView (0, n); }
    bool isWhole() const { return viewA <= 0 && viewB >= n; }
    int viewStart() const { return viewA; }
    int viewEnd() const { return viewB; }
    bool dragging() const { return drag != None; }
    bool hasStem() const { return cache != nullptr; }

    std::function<void (int start, int end)> onTrimmed;    // mouse released after a trim
    std::function<void (int start, int end)> onSelecting;  // while dragging
    std::function<void (int sample)> onSeek;               // a plain click: play from here
    std::function<int (int)> snap;                         // flags (and a slid chop) on release
    std::function<int (int)> snapMove;                     // while sliding (loops: bar grid)

    void mouseMove (const juce::MouseEvent&) override;
    void mouseExit (const juce::MouseEvent&) override;
    void mouseDown (const juce::MouseEvent&) override;
    void mouseDrag (const juce::MouseEvent&) override;
    void mouseUp (const juce::MouseEvent&) override;
    void mouseWheelMove (const juce::MouseEvent&, const juce::MouseWheelDetails&) override;
    void mouseMagnify (const juce::MouseEvent&, float scale) override;

private:
    enum Drag { None, Start, End, Move, New };
    juce::Rectangle<float> area() const;
    juce::Rectangle<float> handleRect() const;
    float xOf (double s) const;
    int sOf (float x) const;
    int near (float x) const;              // 0 none, 1 start, 2 end
    void moveTo (float x);
    std::shared_ptr<PeakCache> cache;
    int n = 0, sr = 44100, start = 0, end = 0, viewA = 0, viewB = 0, playhead = -1;
    int fadeIn = 0, fadeOut = 0;
    bool reverse = false, hoverHandle = false;
    Drag drag = None;
    bool newStarted = false;
    int anchor = 0, a0 = 0, b0 = 0;
    float xPress = 0;
    double spp = 1;
};

} // namespace xk::ui
