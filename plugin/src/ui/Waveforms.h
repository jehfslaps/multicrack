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

// The selected chop shown inside its stem (start / end flags, time ruler, playhead).
class ChopView : public juce::Component
{
public:
    void set (std::shared_ptr<PeakCache> c, int n, int sr, int start, int end);
    void clear() { cache.reset(); repaint(); }
    void setPlayhead (int s) { if (s != playhead) { playhead = s; repaint(); } }
    void paint (juce::Graphics&) override;
    std::function<void (int sample)> onClickAt;
    void mouseUp (const juce::MouseEvent&) override;

private:
    juce::Rectangle<float> area() const;
    float xOf (double s) const;
    std::shared_ptr<PeakCache> cache;
    int n = 0, sr = 44100, start = 0, end = 0, viewA = 0, viewB = 0, playhead = -1;
};

} // namespace xk::ui
