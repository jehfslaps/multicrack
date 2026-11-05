#include "ui/Waveforms.h"

#include <cmath>

namespace xk::ui
{

static const juce::Colour MARK (0xffe8483a);

PeakCache::PeakCache (StemPtr st) : stem (std::move (st)), m (stem->mono())
{
    const int nb = (int) m.size() / BLOCK;
    bmin.resize ((size_t) nb);
    bmax.resize ((size_t) nb);
    for (int i = 0; i < nb; ++i)
    {
        float lo = 1e9f, hi = -1e9f;
        for (int k = 0; k < BLOCK; ++k)
        {
            const float v = m[(size_t) (i * BLOCK + k)];
            lo = juce::jmin (lo, v);
            hi = juce::jmax (hi, v);
        }
        bmin[(size_t) i] = lo;
        bmax[(size_t) i] = hi;
    }
}

void PeakCache::columns (int a, int b, int cols, std::vector<float>& mins, std::vector<float>& maxs) const
{
    a = juce::jmax (0, a);
    b = juce::jmin ((int) m.size(), b);
    cols = juce::jmax (1, cols);
    mins.assign ((size_t) cols, 0.0f);
    maxs.assign ((size_t) cols, 0.0f);
    if (b - a <= 1)
        return;
    const bool coarse = (b - a) / (double) cols > BLOCK * 2 && ! bmin.empty();
    for (int c = 0; c < cols; ++c)
    {
        float lo = 1e9f, hi = -1e9f;
        if (coarse)
        {
            const int ba = a / BLOCK, bb = juce::jmax (ba + 1, juce::jmin ((int) bmin.size(), b / BLOCK));
            const int i0 = ba + (int) ((long long) (bb - ba) * c / cols);
            const int i1 = juce::jmax (i0 + 1, ba + (int) ((long long) (bb - ba) * (c + 1) / cols));
            for (int i = i0; i < juce::jmin (i1, (int) bmin.size()); ++i)
            {
                lo = juce::jmin (lo, bmin[(size_t) i]);
                hi = juce::jmax (hi, bmax[(size_t) i]);
            }
        }
        else
        {
            const int i0 = a + (int) ((long long) (b - a) * c / cols);
            const int i1 = juce::jmax (i0 + 1, a + (int) ((long long) (b - a) * (c + 1) / cols));
            for (int i = i0; i < juce::jmin (i1, b); ++i)
            {
                lo = juce::jmin (lo, m[(size_t) i]);
                hi = juce::jmax (hi, m[(size_t) i]);
            }
        }
        if (lo > hi) lo = hi = 0;
        mins[(size_t) c] = lo;
        maxs[(size_t) c] = hi;
    }
}

float waveGain (const std::vector<float>& mins, const std::vector<float>& maxs)
{
    float pk = 0;
    for (float v : mins) pk = juce::jmax (pk, std::abs (v));
    for (float v : maxs) pk = juce::jmax (pk, std::abs (v));
    return pk > 1e-6f ? 1.0f / pk : 1.0f;
}

void paintWave (juce::Graphics& g, juce::Rectangle<float> r, const std::vector<float>& mins, const std::vector<float>& maxs,
                float gain, juce::Colour fill, juce::Colour edge, bool centre)
{
    const float cy = r.getCentreY();
    if (centre)
    {
        g.setColour (juce::Colour (0xff2c3237));
        g.drawLine (r.getX(), cy, r.getRight(), cy, 1.0f);
    }
    const int n = (int) mins.size();
    if (n == 0)
        return;
    const float w = r.getWidth(), half = r.getHeight() / 2 * 0.92f;
    juce::Path p;
    for (int i = 0; i < n; ++i)
    {
        const float x = r.getX() + (i + 0.5f) * (w / n);
        const float y = juce::jmin (cy - juce::jlimit (-1.0f, 1.0f, maxs[(size_t) i] * gain) * half, cy - 0.6f);
        if (i == 0) p.startNewSubPath (x, y); else p.lineTo (x, y);
    }
    for (int i = n - 1; i >= 0; --i)
    {
        const float x = r.getX() + (i + 0.5f) * (w / n);
        const float y = juce::jmax (cy - juce::jlimit (-1.0f, 1.0f, mins[(size_t) i] * gain) * half, cy + 0.6f);
        p.lineTo (x, y);
    }
    p.closeSubPath();
    g.setColour (fill);
    g.fillPath (p);
    g.setColour (edge);
    g.strokePath (p, juce::PathStrokeType (0.7f));
}

// ------------------------------------------------------------------ mini
void MiniWave::set (std::shared_ptr<PeakCache> c, int a_, int b_, bool rev)
{
    cache = std::move (c);
    a = a_;
    b = b_;
    reverse = rev;
    repaint();
}

void MiniWave::paint (juce::Graphics& g)
{
    if (! cache)
        return;
    auto r = getLocalBounds().toFloat().withTrimmedTop (2).withTrimmedBottom (2);
    std::vector<float> mins, maxs;
    cache->columns (a, b, juce::jmax (8, (int) (r.getWidth() / 1.6f)), mins, maxs);
    if (reverse)
    {
        std::reverse (mins.begin(), mins.end());
        std::reverse (maxs.begin(), maxs.end());
    }
    paintWave (g, r, mins, maxs, waveGain (mins, maxs), C ("wave"), C ("wave_edge"), false);
    if (playhead >= 0)
    {
        g.setColour (juce::Colours::white);
        const float x = r.getWidth() * playhead;
        g.drawLine (x, 0, x, (float) getHeight(), 1.6f);
    }
}

// ------------------------------------------------------------------ chop view
void ChopView::set (std::shared_ptr<PeakCache> c, int n_, int sr_, int s, int e)
{
    cache = std::move (c);
    n = n_;
    sr = sr_;
    start = s;
    end = e;
    const int len = juce::jmax (1, end - start);
    const int pad = juce::jmax ((int) (0.25 * len), (int) (0.12 * sr));
    const int span = juce::jmin (n, juce::jmax ((int) (0.01 * sr), len + 2 * pad));
    viewA = juce::jmax (0, juce::jmin (n - span, start - pad));
    viewB = viewA + span;
    repaint();
}

juce::Rectangle<float> ChopView::area() const
{
    auto r = getLocalBounds().toFloat().reduced (1);
    return { r.getX() + 2, r.getY() + 24, r.getWidth() - 4, r.getHeight() - 48 };
}

float ChopView::xOf (double s) const
{
    const auto a = area();
    return a.getX() + (float) ((s - viewA) / juce::jmax (1, viewB - viewA)) * a.getWidth();
}

void ChopView::mouseUp (const juce::MouseEvent& e)
{
    if (! cache || ! onClickAt)
        return;
    const auto a = area();
    const int s = viewA + (int) ((e.position.x - a.getX()) / juce::jmax (1.0f, a.getWidth()) * (viewB - viewA));
    onClickAt (juce::jlimit (0, n, s));
}

static double timeStep (double span)
{
    for (double s : { 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 15.0, 30.0, 60.0 })
        if (span / s <= 9)
            return s;
    return 60.0;
}

static juce::String fmtT (double t, double step)
{
    const int m = (int) (t / 60);
    const double sec = t - 60 * m;
    if (step < 1)
        return juce::String (m) + ":" + juce::String (sec, 2).paddedLeft ('0', 5);
    return juce::String (m) + ":" + juce::String ((int) std::round (sec)).paddedLeft ('0', 2);
}

void ChopView::paint (juce::Graphics& g)
{
    auto r = getLocalBounds().toFloat().reduced (1);
    paintGlass (g, r, 4);
    if (! cache)
    {
        text (g, r, "SELECT A CHOP TO SEE IT HERE", font (12, 500, 2.0f), juce::Colour (0xff6e6a64), juce::Justification::centred);
        return;
    }
    const auto a = area();
    juce::Graphics::ScopedSaveState ss (g);
    g.reduceClipRegion (r.reduced (2).toNearestInt());
    // grid and ruler
    const double span = (viewB - viewA) / (double) sr;
    if (span > 0)
    {
        const double step = timeStep (span);
        double t = viewA > 0 ? (std::floor (viewA / (double) sr / step) + 1) * step : 0.0;
        juce::Rectangle<float> ruler (r.getX() + 4, a.getBottom() + 2, r.getWidth() - 8, 20);
        for (; t * sr <= viewB; t += step)
        {
            const float x = xOf (t * sr);
            g.setColour (juce::Colour::fromRGBA (255, 255, 255, 14));
            g.drawLine (x, a.getY(), x, a.getBottom(), 1.0f);
            g.setColour (juce::Colour::fromRGBA (255, 255, 255, 60));
            g.drawLine (x, ruler.getY(), x, ruler.getY() + 4, 1.0f);
            text (g, { x + 4, ruler.getY(), 80, ruler.getHeight() }, fmtT (t, step), font (11, 500, 0.6f), juce::Colour (0xffa9a49c));
        }
        for (float fr : { 0.25f, 0.75f })
        {
            g.setColour (juce::Colour::fromRGBA (255, 255, 255, 9));
            g.drawLine (a.getX(), a.getY() + a.getHeight() * fr, a.getRight(), a.getY() + a.getHeight() * fr, 1.0f);
        }
    }
    std::vector<float> mins, maxs, cm, cx;
    cache->columns (viewA, viewB, juce::jmax (8, (int) (a.getWidth() / 1.4f)), mins, maxs);
    cache->columns (start, end, 64, cm, cx);
    const float gain = waveGain (cm, cx);
    paintWave (g, a, mins, maxs, gain, C ("wave_dim"), juce::Colour (0xff8a8f94));
    const float xs = xOf (start), xe = xOf (end);
    {
        juce::Graphics::ScopedSaveState s2 (g);
        g.reduceClipRegion (juce::Rectangle<float> (xs, a.getY() - 2, juce::jmax (0.0f, xe - xs), a.getHeight() + 4).toNearestInt());
        paintWave (g, a, mins, maxs, gain, C ("wave"), C ("wave_edge"), false);
        g.setColour (C ("wave").withAlpha ((juce::uint8) 18));
        g.fillRect (juce::Rectangle<float> (xs, a.getY(), xe - xs, a.getHeight()));
    }
    g.setColour (MARK.withAlpha ((juce::uint8) 70));
    g.fillRect (juce::Rectangle<float> (xs, r.getY() + 8, juce::jmax (0.0f, xe - xs), 5));
    for (float x : { xs, xe })
    {
        g.setColour (MARK);
        g.drawLine (x, r.getY() + 22, x, a.getBottom(), 1.8f);
        juce::Path tri;
        tri.addTriangle (x - 6.5f, r.getY() + 3, x + 6.5f, r.getY() + 3, x, r.getY() + 23);
        g.fillPath (tri);
    }
    if (playhead >= 0)
    {
        const float xp = xOf (playhead);
        g.setColour (juce::Colours::white);
        g.drawLine (xp, r.getY() + 22, xp, a.getBottom(), 1.7f);
        juce::Path tri;
        tri.addTriangle (xp - 5.5f, r.getY() + 4, xp + 5.5f, r.getY() + 4, xp, r.getY() + 22);
        g.fillPath (tri);
    }
}

} // namespace xk::ui
