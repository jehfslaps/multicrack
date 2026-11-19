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
void ChopView::set (std::shared_ptr<PeakCache> c, int n_, int sr_, int s, int e, bool keepView)
{
    const bool same = c == cache && n_ == n;
    cache = std::move (c);
    n = n_;
    sr = sr_;
    if (drag == None)
    {
        start = s;
        end = e;
    }
    if (keepView && same && viewB > viewA)
        repaint();
    else
        showChop (same && viewB > viewA);   // another chop of the same stem: glide over to it
}

void ChopView::setFx (int fi, int fo, bool rev)
{
    if (fi != fadeIn || fo != fadeOut || rev != reverse)
    {
        fadeIn = fi;
        fadeOut = fo;
        reverse = rev;
        repaint();
    }
}

void ChopView::showChop (bool glide)
{
    const int len = juce::jmax (1, end - start);
    const int pad = juce::jmax ((int) (0.25 * len), (int) (0.12 * sr));
    setView (start - pad, end + pad, glide);
}

std::pair<int, int> ChopView::heading() const
{
    if (va.moving() || vb.moving())
        return { (int) va.target(), (int) vb.target() };
    return { viewA, viewB };
}

void ChopView::setView (int a, int b, bool glide)
{
    const int span = juce::jmin (n, juce::jmax ((int) (0.01 * sr), b - a));
    a = juce::jmax (0, juce::jmin (n - span, a));
    if (glide && isShowing() && viewB > viewA)
    {
        if (! va.moving() && ! vb.moving())
        {
            va.jump (viewA);
            vb.jump (viewB);
        }
        va.onChange = vb.onChange = [this] (double) { glided(); };
        va.to (a);
        vb.to (a + span);
        return;
    }
    va.onChange = vb.onChange = nullptr;
    va.jump (a);      // stops any glide
    vb.jump (a + span);
    viewA = a;
    viewB = a + span;
    repaint();
}

void ChopView::glided()
{
    const int a = (int) std::lround (va.get()), b = (int) std::lround (vb.get());
    if (b - a < 2)
        return;
    viewA = juce::jmax (0, juce::jmin (n - (b - a), a));
    viewB = juce::jmin (n, viewA + (b - a));
    repaint();
}

void ChopView::zoom (double factor, int centre)
{
    if (! cache)
        return;
    const auto [a0, b0] = heading();      // quick wheel turns add up
    const int span = b0 - a0;
    if (centre < 0)
        centre = a0 + span / 2;
    const double ns = span * factor;
    const double a = centre - (centre - a0) * ns / juce::jmax (1, span);
    setView ((int) a, (int) (a + ns), true);
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

int ChopView::sOf (float x) const
{
    const auto a = area();
    return viewA + (int) ((x - a.getX()) / juce::jmax (1.0f, a.getWidth()) * (viewB - viewA));
}

juce::Rectangle<float> ChopView::handleRect() const
{
    const auto r = getLocalBounds().toFloat().reduced (1);
    const float cx = (xOf (start) + xOf (end)) / 2;
    return { cx - 22, r.getY() + 2, 44, 15 };
}

int ChopView::near (float x) const
{
    const float ds = std::abs (x - xOf (start)), de = std::abs (x - xOf (end));
    if (juce::jmin (ds, de) < 10)
        return ds <= de ? 1 : 2;
    return 0;
}

void ChopView::mouseMove (const juce::MouseEvent& e)
{
    if (! cache)
        return;
    const float x = e.position.x;
    const bool nearEdge = juce::jmin (std::abs (x - xOf (start)), std::abs (x - xOf (end))) < 5;
    const bool over = handleRect().expanded (3, 2).contains (e.position) && ! nearEdge;
    if (over != hoverHandle)
    {
        hoverHandle = over;
        repaint();
    }
    const int part = near (x);
    setMouseCursor (over ? juce::MouseCursor::DraggingHandCursor
                         : part ? juce::MouseCursor::LeftRightResizeCursor : juce::MouseCursor::PointingHandCursor);
    setTooltip (over ? "Drag to slide the whole chop (same length)"
                     : part ? "Drag to trim"
                            : "Click to play the stem from here. Drag across to pick a new section. Wheel zooms, Shift+wheel scrolls.");
}

void ChopView::mouseExit (const juce::MouseEvent&)
{
    if (hoverHandle)
    {
        hoverHandle = false;
        repaint();
    }
}

void ChopView::mouseDown (const juce::MouseEvent& e)
{
    if (! cache || e.mods.isPopupMenu())
        return;
    const float x = e.position.x;
    const bool nearEdge = juce::jmin (std::abs (x - xOf (start)), std::abs (x - xOf (end))) < 5;
    a0 = start;
    b0 = end;
    if (handleRect().expanded (3, 2).contains (e.position) && ! nearEdge)
    {
        drag = Move;
        xPress = x;
        spp = (viewB - viewA) / (double) juce::jmax (1.0f, area().getWidth());
        repaint();
    }
    else if (const int part = near (x))
        drag = part == 1 ? Start : End;
    else
    {
        drag = New;
        newStarted = false;
        anchor = juce::jlimit (0, n, sOf (x));
    }
}

void ChopView::moveTo (float x)
{
    const int len = b0 - a0;
    int ns = juce::jlimit (0, juce::jmax (0, n - len), a0 + (int) ((x - xPress) * spp));
    if (snapMove)
        ns = juce::jlimit (0, juce::jmax (0, n - len), snapMove (ns));
    start = ns;
    end = ns + len;
    // keep the chop in view while sweeping through the stem
    const int span = viewB - viewA;
    if (span < n)
    {
        if (end > viewB)
            setView (end - span + span / 20, end + span / 20);
        else if (start < viewA)
            setView (start - span / 20, start - span / 20 + span);
    }
}

void ChopView::mouseDrag (const juce::MouseEvent& e)
{
    if (drag == None)
        return;
    const float x = e.position.x;
    const int minLen = juce::jmax (1, (int) (0.005 * sr));
    const int s = juce::jlimit (0, n, sOf (x));
    if (drag == Move)
        moveTo (x);
    else if (drag == Start)
        start = juce::jmin (s, end - minLen);
    else if (drag == End)
        end = juce::jmax (s, start + minLen);
    else if (drag == New)
    {
        if (newStarted || std::abs (s - anchor) > minLen)
        {
            newStarted = true;
            start = juce::jmin (anchor, s);
            end = juce::jmax (juce::jmax (anchor, s), start + minLen);
        }
        else
            return;
    }
    // drag past the edge of the view: scroll along
    const auto a = area();
    if (drag != Move && (x < a.getX() || x > a.getRight()) && viewB - viewA < n)
    {
        const int step = (viewB - viewA) / 30;
        setView (viewA + (x < a.getX() ? -step : step), viewB + (x < a.getX() ? -step : step));
    }
    repaint();
    if (onSelecting)
        onSelecting (start, end);
}

void ChopView::mouseUp (const juce::MouseEvent&)
{
    const auto d = drag;
    drag = None;
    if (d == None || ! cache)
        return;
    const int minLen = juce::jmax (1, (int) (0.005 * sr));
    if (d == New && ! newStarted)
    {
        if (onSeek)
            onSeek (anchor);   // a plain click: play the stem from here
        return;
    }
    if (d == Move)
    {
        if (start == a0 && end == b0)
        {
            repaint();
            return;
        }
        if (snap && ! snapMove)
        {
            const int len = end - start;
            const int ns = juce::jlimit (0, juce::jmax (0, n - len), snap (start));
            start = ns;
            end = ns + len;
        }
    }
    else if ((d == Start || d == New) && snap)
        start = juce::jmin (snap (start), end - minLen);
    repaint();
    if (onTrimmed && (start != a0 || end != b0))
        onTrimmed (start, end);
}

void ChopView::mouseWheelMove (const juce::MouseEvent& e, const juce::MouseWheelDetails& w)
{
    if (! cache)
        return;
    const float dx = w.deltaX, dy = w.deltaY;
    if (e.mods.isShiftDown() || std::abs (dx) > std::abs (dy))
    {
        const float d = dx != 0 ? dx : dy;
        const auto [a0, b0] = heading();
        const int span = b0 - a0;
        const int shift = (int) (-d * span * 0.6f);
        setView (a0 + shift, b0 + shift, ! w.isSmooth);
    }
    else if (dy != 0)
        zoom (dy > 0 ? 0.8 : 1.25, juce::jlimit (0, n, sOf (e.position.x)));
}

void ChopView::mouseMagnify (const juce::MouseEvent& e, float scale)
{
    if (cache && scale > 0)
        zoom (1.0 / scale, juce::jlimit (0, n, sOf (e.position.x)));
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
    float gain;
    if (viewB - viewA > 4 * juce::jmax (1, end - start))
        gain = juce::jmin (waveGain (mins, maxs), 8.0f);
    else
    {
        cache->columns (start, end, 64, cm, cx);
        gain = waveGain (cm, cx);
    }
    paintWave (g, a, mins, maxs, gain, C ("wave_dim"), juce::Colour (0xff8a8f94));
    const float xs = xOf (start), xe = xOf (end);
    {
        juce::Graphics::ScopedSaveState s2 (g);
        g.reduceClipRegion (juce::Rectangle<float> (xs, a.getY() - 2, juce::jmax (0.0f, xe - xs), a.getHeight() + 4).toNearestInt());
        paintWave (g, a, mins, maxs, gain, C ("wave"), C ("wave_edge"), false);
        g.setColour (C ("wave").withAlpha ((juce::uint8) 18));
        g.fillRect (juce::Rectangle<float> (xs, a.getY(), xe - xs, a.getHeight()));
    }
    // fades as heard (a reversed chop fades in from its original end)
    {
        const int fi = reverse ? fadeOut : fadeIn, fo = reverse ? fadeIn : fadeOut;
        const float dashes[] = { 4.0f, 3.0f };
        g.setColour (juce::Colour::fromRGBA (235, 232, 225, 190));
        if (fi > 0)
            g.drawDashedLine ({ xs, a.getBottom(), xOf (start + fi), a.getY() }, dashes, 2, 1.3f);
        if (fo > 0)
            g.drawDashedLine ({ xOf (end - fo), a.getY(), xe, a.getBottom() }, dashes, 2, 1.3f);
    }
    g.setColour (MARK.withAlpha ((juce::uint8) 70));
    g.fillRect (juce::Rectangle<float> (xs, r.getY() + 8, juce::jmax (0.0f, xe - xs), 5));
    {
        // grab bar: drag to slide the whole chop
        const auto hr = handleRect();
        const bool hot = hoverHandle || drag == Move;
        juce::ColourGradient gr (hot ? juce::Colours::white : juce::Colour (0xfff2eee6), hr.getX(), hr.getY(),
                                 juce::Colour (0xffbdb5a7), hr.getX(), hr.getBottom(), false);
        g.setGradientFill (gr);
        g.fillRoundedRectangle (hr, 3);
        g.setColour (juce::Colour::fromRGBA (0, 0, 0, 200));
        g.drawRoundedRectangle (hr, 3, 1);
        g.setColour (juce::Colour::fromRGBA (40, 36, 32, 200));
        for (float dx : { -6.0f, -2.0f, 2.0f, 6.0f })
            g.drawLine (hr.getCentreX() + dx, hr.getY() + 3.5f, hr.getCentreX() + dx, hr.getBottom() - 3.5f, 1.2f);
    }
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
