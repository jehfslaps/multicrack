#include "ui/Skin.h"

#include "XenakisAssets.h"

#include <cmath>
#include <map>
#include <random>

namespace xk::ui
{

// ================================================================== palette
namespace
{
bool gDark = false;

const std::map<std::string, juce::uint32>& common()
{
    static const std::map<std::string, juce::uint32> m {
        { "module", 0xff222326 }, { "module_hi", 0xff33353a }, { "module_lo", 0xff0e0f10 },
        { "module_edge", 0xff3b3d42 }, { "outline", 0xff9c3f2e }, { "wire", 0xffb4473a },
        { "wire_node", 0xffc8553f }, { "on_dark", 0xffe9e5dd }, { "on_dark_muted", 0xff9d9890 },
        { "on_dark_dim", 0xff68645e }, { "field", 0xff161719 }, { "field_edge", 0xff3c3e43 },
        { "field_focus", 0xffc2513d }, { "glass", 0xff121416 }, { "glass_grid", 0xff22262a },
        { "glass_text", 0xffe9e5dd }, { "led_red", 0xffff3b2f }, { "led_green", 0xff4be07a },
        { "led_amber", 0xffffb23d }, { "red", 0xffb8382a }, { "red_hi", 0xffd44a36 }, { "red_lo", 0xff7f2117 },
        { "key", 0xffe7e2d8 }, { "key_hi", 0xfff6f2ea }, { "key_lo", 0xffbdb5a7 }, { "key_text", 0xff26262a },
        { "ok", 0xff7bd88f }, { "warn", 0xffe8644e }, { "info", 0xffe9e5dd }, { "wave", 0xff46d18a },
        { "wave_edge", 0xff9bf0c2 }, { "wave_dim", 0xff6e7378 }, { "wave_neutral", 0xffb9bdc1 },
        { "row_sel", 0xff2c2424 }, { "row_hover", 0xff26272a }, { "row_line", 0xff2d2f33 },
        { "header_text", 0xffa9a49c },
    };
    return m;
}

const std::map<std::string, juce::uint32>& light()
{
    static const std::map<std::string, juce::uint32> m {
        { "chassis", 0xffd8d3c9 }, { "chassis_hi", 0xffece8e0 }, { "chassis_lo", 0xffa9a194 },
        { "chassis_text", 0xff2b2a27 }, { "chassis_muted", 0xff625d55 }, { "plate", 0xffe4dfd6 },
        { "plate_text", 0xff26252a }, { "grime", 0xff463a2c },
    };
    return m;
}

const std::map<std::string, juce::uint32>& dark()
{
    static const std::map<std::string, juce::uint32> m {
        { "chassis", 0xff2b2c2f }, { "chassis_hi", 0xff3d3f43 }, { "chassis_lo", 0xff141516 },
        { "chassis_text", 0xffe2ded6 }, { "chassis_muted", 0xff9b968e }, { "plate", 0xff33353a },
        { "plate_text", 0xffe9e5dd }, { "grime", 0xff000000 }, { "module", 0xff1d1e21 }, { "module_hi", 0xff2e3034 },
    };
    return m;
}
} // namespace

void setDark (bool d) { gDark = d; }
bool isDark() { return gDark; }

juce::Colour C (const char* key, int alpha)
{
    const auto& mode = gDark ? dark() : light();
    auto it = mode.find (key);
    juce::uint32 v = 0xffff00ff;
    if (it != mode.end())
        v = it->second;
    else
    {
        auto jt = common().find (key);
        if (jt != common().end())
            v = jt->second;
    }
    juce::Colour c (v);
    return alpha >= 0 ? c.withAlpha ((juce::uint8) juce::jlimit (0, 255, alpha)) : c;
}

// ==================================================================== fonts
namespace
{
// Fonts and textures live here; JUCE deletes it during shutdown, before its own statics go,
// so nothing is torn down in the wrong order when a host unloads the plug-in.
struct SkinCache : public juce::DeletedAtShutdown
{
    juce::Typeface::Ptr faces[4];
    std::map<int, juce::Image> textures;
    SkinCache()
    {
        faces[0] = juce::Typeface::createSystemTypefaceFor (XenakisAssets::IBMPlexMonoRegular_ttf, XenakisAssets::IBMPlexMonoRegular_ttfSize);
        faces[1] = juce::Typeface::createSystemTypefaceFor (XenakisAssets::IBMPlexMonoMedium_ttf, XenakisAssets::IBMPlexMonoMedium_ttfSize);
        faces[2] = juce::Typeface::createSystemTypefaceFor (XenakisAssets::IBMPlexMonoSemiBold_ttf, XenakisAssets::IBMPlexMonoSemiBold_ttfSize);
        faces[3] = juce::Typeface::createSystemTypefaceFor (XenakisAssets::IBMPlexMonoBold_ttf, XenakisAssets::IBMPlexMonoBold_ttfSize);
    }
    ~SkinCache() override { clearSingletonInstance(); }
    JUCE_DECLARE_SINGLETON_INLINE (SkinCache, false)
};

juce::Typeface::Ptr typeface (int weight)
{
    const int i = weight >= 700 ? 3 : weight >= 600 ? 2 : weight >= 500 ? 1 : 0;
    return SkinCache::getInstance()->faces[i];
}
} // namespace

juce::Font font (float px, int weight, float spacing)
{
    px = juce::jmax (6.0f, px);
    juce::FontOptions o = juce::FontOptions (typeface (weight)).withPointHeight (px);
    juce::Font f (o);
    if (spacing != 0.0f)
        f = juce::Font (o.withKerningFactor (spacing / juce::jmax (1.0f, f.getHeight())));
    return f;
}

float textWidth (const juce::String& s, const juce::Font& f)
{
    juce::GlyphArrangement ga;
    ga.addLineOfText (f, s, 0, 0);
    return ga.getBoundingBox (0, -1, true).getWidth();
}

void text (juce::Graphics& g, juce::Rectangle<float> r, const juce::String& s, const juce::Font& f, juce::Colour c,
           juce::Justification j, bool elide)
{
    g.setFont (f);
    g.setColour (c);
    g.drawText (s, r, j, elide);
}

// ================================================================= textures
namespace
{
// tileable smooth noise in [-1, 1]: wrap-around value noise, cosine-interpolated
std::vector<float> periodicNoise (int n, float cell, std::mt19937& rng)
{
    const int grid = juce::jmax (2, (int) std::round (n / juce::jmax (1.0f, cell)));
    std::normal_distribution<float> nd;
    std::vector<float> g ((size_t) (grid * grid));
    for (auto& v : g) v = nd (rng);
    std::vector<float> out ((size_t) (n * n));
    float mx = 1e-6f;
    double mean = 0;
    for (int y = 0; y < n; ++y)
    {
        const float fy = (float) y * grid / n;
        const int y0 = (int) fy % grid, y1 = (y0 + 1) % grid;
        const float ty = 0.5f - 0.5f * std::cos ((fy - std::floor (fy)) * juce::MathConstants<float>::pi);
        for (int x = 0; x < n; ++x)
        {
            const float fx = (float) x * grid / n;
            const int x0 = (int) fx % grid, x1 = (x0 + 1) % grid;
            const float tx = 0.5f - 0.5f * std::cos ((fx - std::floor (fx)) * juce::MathConstants<float>::pi);
            const float a = g[(size_t) (y0 * grid + x0)], b = g[(size_t) (y0 * grid + x1)];
            const float c = g[(size_t) (y1 * grid + x0)], d = g[(size_t) (y1 * grid + x1)];
            const float v = (a + (b - a) * tx) + ((c + (d - c) * tx) - (a + (b - a) * tx)) * ty;
            out[(size_t) (y * n + x)] = v;
            mean += v;
        }
    }
    mean /= (double) out.size();
    for (auto& v : out)
    {
        v -= (float) mean;
        mx = juce::jmax (mx, std::abs (v));
    }
    for (auto& v : out) v /= mx;
    return out;
}

void scratches (std::vector<float>& rgb, int n, std::mt19937& rng, int count, juce::Colour col, float alpha)
{
    std::uniform_real_distribution<float> u (0.0f, 1.0f);
    for (int s = 0; s < count; ++s)
    {
        const float x0 = u (rng) * n, y0 = u (rng) * n;
        const float ang = u (rng) * juce::MathConstants<float>::pi;
        const float len = n * (0.03f + u (rng) * 0.13f);
        const float bend = -0.06f + u (rng) * 0.12f;
        const float strength = alpha * (0.4f + 0.6f * u (rng));
        const int steps = (int) (len * 2);
        for (int i = 0; i < steps; ++i)
        {
            const float t = (float) i / juce::jmax (1, steps - 1);
            float xs = x0 + std::cos (ang) * len * t + std::sin (ang) * bend * len * t * t;
            float ys = y0 + std::sin (ang) * len * t - std::cos (ang) * bend * len * t * t;
            xs = std::fmod (std::fmod (xs, (float) n) + n, (float) n);
            ys = std::fmod (std::fmod (ys, (float) n) + n, (float) n);
            const float fade = std::sin (juce::MathConstants<float>::pi * t) * strength;
            const size_t k = ((size_t) ys * (size_t) n + (size_t) xs) * 3;
            rgb[k] = rgb[k] * (1 - fade) + col.getRed() * fade;
            rgb[k + 1] = rgb[k + 1] * (1 - fade) + col.getGreen() * fade;
            rgb[k + 2] = rgb[k + 2] * (1 - fade) + col.getBlue() * fade;
        }
    }
}

juce::Image makeTexture (Tex kind, bool darkMode)
{
    const int n = 384;
    std::mt19937 rng (kind == Tex::bone ? 11u : kind == Tex::graphite ? 23u : (darkMode ? 41u : 37u));
    std::normal_distribution<float> nd;
    std::vector<float> rgb ((size_t) n * n * 3);
    juce::Colour base;
    if (kind == Tex::bone) base = juce::Colour (0xffd8d3c9);
    else if (kind == Tex::graphite) base = juce::Colour (0xff2b2c2f);
    else base = juce::Colour (darkMode ? 0xff1d1e21 : 0xff222326);
    std::vector<float> lum ((size_t) n * n, 0.0f);
    float tint[3] { 1, 1, 1 };
    if (kind == Tex::bone)
    {
        auto a = periodicNoise (n, 384 / 3.5f / 2.0f, rng), b = periodicNoise (n, 384 / 14.0f / 2.0f, rng),
             gr = periodicNoise (n, 384 / 5.0f / 2.0f, rng);
        for (size_t i = 0; i < lum.size(); ++i)
            lum[i] = a[i] * 7 + b[i] * 3.5f + nd (rng) * 4.2f - juce::jmax (0.0f, gr[i] - 0.35f) * 26;
        tint[1] = 0.97f;
        tint[2] = 0.9f;
    }
    else if (kind == Tex::graphite)
    {
        auto a = periodicNoise (n, 384 / 3.5f / 2.0f, rng), b = periodicNoise (n, 384 / 16.0f / 2.0f, rng);
        std::vector<float> brush ((size_t) n);
        for (auto& v : brush) v = nd (rng) * 1.6f;
        for (int y = 0; y < n; ++y)
            for (int x = 0; x < n; ++x)
            {
                const size_t i = (size_t) (y * n + x);
                lum[i] = a[i] * 4.5f + b[i] * 2.5f + nd (rng) * 3.2f + brush[(size_t) y];
            }
        tint[2] = 1.04f;
    }
    else
    {
        auto a = periodicNoise (n, 384 / 4.0f / 2.0f, rng);
        for (size_t i = 0; i < lum.size(); ++i)
            lum[i] = a[i] * 3.2f + nd (rng) * 2.6f;
    }
    for (size_t i = 0; i < lum.size(); ++i)
    {
        rgb[i * 3] = base.getRed() + lum[i] * tint[0];
        rgb[i * 3 + 1] = base.getGreen() + lum[i] * tint[1];
        rgb[i * 3 + 2] = base.getBlue() + lum[i] * tint[2];
    }
    if (kind == Tex::bone)
    {
        std::uniform_real_distribution<float> u (0.0f, 1.0f);
        for (size_t i = 0; i < lum.size(); ++i)
            if (u (rng) < 0.0018f)
            {
                const float d = 18 + u (rng) * 27;
                rgb[i * 3] -= d;
                rgb[i * 3 + 1] -= d;
                rgb[i * 3 + 2] -= d;
            }
        scratches (rgb, n, rng, 26, juce::Colour (150, 142, 130), 0.35f);
        scratches (rgb, n, rng, 14, juce::Colour (246, 243, 236), 0.30f);
    }
    else if (kind == Tex::graphite)
        scratches (rgb, n, rng, 18, juce::Colour (80, 82, 88), 0.35f);
    else
        scratches (rgb, n, rng, 10, juce::Colour (64, 66, 72), 0.25f);
    juce::Image img (juce::Image::RGB, n, n, false);
    juce::Image::BitmapData bd (img, juce::Image::BitmapData::writeOnly);
    for (int y = 0; y < n; ++y)
        for (int x = 0; x < n; ++x)
        {
            const size_t k = (size_t) (y * n + x) * 3;
            bd.setPixelColour (x, y, juce::Colour ((juce::uint8) juce::jlimit (0.0f, 255.0f, rgb[k]),
                                                   (juce::uint8) juce::jlimit (0.0f, 255.0f, rgb[k + 1]),
                                                   (juce::uint8) juce::jlimit (0.0f, 255.0f, rgb[k + 2])));
        }
    return img;
}
} // namespace

const juce::Image& texture (Tex kind)
{
    auto& cache = SkinCache::getInstance()->textures;
    const int key = (int) kind * 2 + (kind == Tex::module && gDark ? 1 : 0);
    auto it = cache.find (key);
    if (it == cache.end())
        it = cache.emplace (key, makeTexture (kind, gDark)).first;
    return it->second;
}

const juce::Image& chassisTexture()
{
    return texture (gDark ? Tex::graphite : Tex::bone);
}

void fillTextured (juce::Graphics& g, const juce::Path& p, const juce::Image& img, juce::Colour tint)
{
    juce::Graphics::ScopedSaveState ss (g);
    g.setTiledImageFill (img, 0, 0, 1.0f);
    g.fillPath (p);
    if (! tint.isTransparent())
    {
        g.setColour (tint);
        g.fillPath (p);
    }
}

// ================================================================= draw kit
juce::Path rrect (juce::Rectangle<float> r, float rad)
{
    juce::Path p;
    p.addRoundedRectangle (r, rad);
    return p;
}

void softShadow (juce::Graphics& g, juce::Rectangle<float> r, float rad, float depth, int alpha, float dy)
{
    const int steps = (int) juce::jmax (2.0f, depth);
    for (int i = steps; i > 0; --i)
    {
        const float k = 1.0f - (float) i / (steps + 1);
        const int a = (int) (alpha * k * k / steps * 2.2f);
        g.setColour (juce::Colour::fromRGBA (0, 0, 0, (juce::uint8) juce::jlimit (0, 255, a)));
        const float gr = i * 0.9f;
        g.fillRoundedRectangle (r.expanded (gr).translated (0, dy), rad + gr);
    }
}

void bevelEdges (juce::Graphics& g, juce::Rectangle<float> r, float rad, juce::Colour hi, juce::Colour lo, float w)
{
    juce::ColourGradient cg (hi, r.getTopLeft(), lo, r.getBottomRight(), false);
    cg.addColour (0.45, hi.withAlpha ((juce::uint8) 0));
    cg.addColour (0.55, lo.withAlpha ((juce::uint8) 0));
    g.setGradientFill (cg);
    g.drawRoundedRectangle (r.reduced (w / 2), rad, w);
}

void innerShadow (juce::Graphics& g, juce::Rectangle<float> r, float rad, int strength, float size)
{
    juce::Graphics::ScopedSaveState ss (g);
    g.reduceClipRegion (rrect (r, rad));
    const auto black = juce::Colour::fromRGBA (0, 0, 0, (juce::uint8) strength);
    g.setGradientFill (juce::ColourGradient (black, r.getX(), r.getY(), black.withAlpha ((juce::uint8) 0), r.getX(), r.getY() + size, false));
    g.fillRect (r.withHeight (size));
    const auto b2 = juce::Colour::fromRGBA (0, 0, 0, (juce::uint8) (strength / 2));
    g.setGradientFill (juce::ColourGradient (b2, r.getX(), r.getY(), b2.withAlpha ((juce::uint8) 0), r.getX() + size * 0.7f, r.getY(), false));
    g.fillRect (r.withWidth (size * 0.7f));
}

void screw (juce::Graphics& g, juce::Point<float> c, float r)
{
    g.setColour (juce::Colour::fromRGBA (0, 0, 0, 90));
    g.fillEllipse (juce::Rectangle<float> (2 * (r + 1.3f), 2 * (r + 1.3f)).withCentre (c.translated (0.4f, 0.9f)));
    juce::ColourGradient body (juce::Colour (0xfff2f1ee), c.x - r * 0.35f, c.y - r * 0.45f,
                               juce::Colour (0xff5f5d59), c.x - r * 0.35f + r * 1.6f, c.y - r * 0.45f, true);
    body.addColour (0.45, juce::Colour (0xffb7b4ae));
    g.setGradientFill (body);
    const auto e = juce::Rectangle<float> (2 * r, 2 * r).withCentre (c);
    g.fillEllipse (e);
    g.setColour (juce::Colour::fromRGBA (30, 30, 30, 160));
    g.drawEllipse (e, 0.8f);
    const float ang = (float) std::fmod (std::abs (std::sin (c.x * 12.9898 + c.y * 78.233) * 43758.5453), 180.0);
    juce::Graphics::ScopedSaveState ss (g);
    g.addTransform (juce::AffineTransform::rotation (juce::degreesToRadians (ang)).translated (c));
    const float k = r * 0.58f;
    g.setColour (juce::Colour::fromRGBA (40, 38, 36, 230));
    const float lw = juce::jmax (1.0f, r * 0.28f);
    g.drawLine (-k, 0, k, 0, lw);
    g.drawLine (0, -k, 0, k, lw);
    g.setColour (juce::Colour::fromRGBA (255, 255, 255, 70));
    g.drawLine (-k + 0.6f, 0.9f, k - 0.6f, 0.9f, 0.7f);
}

void cornerScrews (juce::Graphics& g, juce::Rectangle<float> r, float inset, float rad)
{
    screw (g, { r.getX() + inset, r.getY() + inset }, rad);
    screw (g, { r.getRight() - inset, r.getY() + inset }, rad);
    screw (g, { r.getX() + inset, r.getBottom() - inset }, rad);
    screw (g, { r.getRight() - inset, r.getBottom() - inset }, rad);
}

void led (juce::Graphics& g, juce::Point<float> c, float r, juce::Colour col, bool on, bool glow, float glowScale)
{
    juce::ColourGradient bz (juce::Colour (0xff4a4c50), c.x, c.y - r * 0.4f, juce::Colour (0xff0b0b0c), c.x, c.y - r * 0.4f + r * 2.0f, true);
    g.setGradientFill (bz);
    g.fillEllipse (juce::Rectangle<float> (2.9f * r, 2.9f * r).withCentre (c));
    if (on && glow)
    {
        juce::ColourGradient gl (col.withAlpha ((juce::uint8) 120), c.x, c.y, col.withAlpha ((juce::uint8) 0), c.x + r * glowScale, c.y, true);
        g.setGradientFill (gl);
        g.fillEllipse (juce::Rectangle<float> (2 * r * glowScale, 2 * r * glowScale).withCentre (c));
    }
    const float lx = c.x - r * 0.3f, ly = c.y - r * 0.35f;
    if (on)
    {
        juce::ColourGradient lens (juce::Colours::white, lx, ly, col.darker (0.7f), lx + r * 1.3f, ly, true);
        lens.addColour (0.25, col.brighter (0.3f));
        lens.addColour (0.8, col);
        g.setGradientFill (lens);
    }
    else
    {
        const auto dim = col.darker (4.2f);
        juce::ColourGradient lens (dim.brighter (1.4f), lx, ly, juce::Colour (8, 8, 8), lx + r * 1.3f, ly, true);
        lens.addColour (0.5, dim);
        g.setGradientFill (lens);
    }
    g.fillEllipse (juce::Rectangle<float> (2 * r, 2 * r).withCentre (c));
    g.setColour (juce::Colour::fromRGBA (255, 255, 255, on ? 150 : 60));
    g.fillEllipse (juce::Rectangle<float> (r * 0.56f, r * 0.4f).withCentre ({ c.x - r * 0.32f, c.y - r * 0.38f }));
}

void hairlineFrame (juce::Graphics& g, juce::Rectangle<float> r, float rad, juce::Colour c, float w)
{
    g.setColour (c);
    g.drawRoundedRectangle (r.reduced (w / 2), rad, w);
}

void node (juce::Graphics& g, juce::Point<float> c, float r, juce::Colour col, bool filled)
{
    const auto e = juce::Rectangle<float> (2 * r, 2 * r).withCentre (c);
    g.setColour (filled ? col : C ("chassis"));
    g.fillEllipse (e);
    g.setColour (col);
    g.drawEllipse (e, 1.2f);
}

void paintGlass (juce::Graphics& g, juce::Rectangle<float> r, float radius)
{
    g.setGradientFill (juce::ColourGradient (juce::Colour (0xff0e1012), r.getX(), r.getY(), juce::Colour (0xff15181b), r.getX(), r.getBottom(), false));
    g.fillPath (rrect (r, radius));
    innerShadow (g, r, radius, 190, 10);
    g.setColour (juce::Colours::black);
    g.drawRoundedRectangle (r.reduced (0.5f), radius, 1.2f);
    g.setColour (juce::Colour::fromRGBA (255, 255, 255, 22));
    g.drawLine (r.getX() + radius, r.getBottom() + 0.5f, r.getRight() - radius, r.getBottom() + 0.5f, 1.0f);
}

// ==================================================================== icons
juce::Path iconPath (const juce::String& name, float s)
{
    juce::Path P;
    const float k = s / 24.0f;
    auto pt = [k] (float x, float y) { return juce::Point<float> (x * k, y * k); };
    auto mv = [&] (float x, float y) { P.startNewSubPath (pt (x, y)); };
    auto ln = [&] (float x, float y) { P.lineTo (pt (x, y)); };
    auto cu = [&] (float a, float b, float c, float d, float e, float f) { P.cubicTo (pt (a, b), pt (c, d), pt (e, f)); };
    if (name == "play") { mv (8, 5.5f); ln (19, 12); ln (8, 18.5f); P.closeSubPath(); }
    else if (name == "stop") P.addRoundedRectangle (6.5f * k, 6.5f * k, 11 * k, 11 * k, 1.5f * k);
    else if (name == "check") { mv (4.5f, 12.5f); ln (9.5f, 17.5f); ln (19.5f, 6.5f); }
    else if (name == "export") { mv (12, 15); ln (12, 3.5f); mv (7.5f, 8); ln (12, 3.5f); ln (16.5f, 8); mv (4.5f, 13); ln (4.5f, 20); ln (19.5f, 20); ln (19.5f, 13); }
    else if (name == "file") { mv (6, 3); ln (14, 3); ln (19, 8); ln (19, 21); ln (6, 21); P.closeSubPath(); mv (14, 3); ln (14, 8); ln (19, 8); }
    else if (name == "folder") { mv (3, 6); ln (9, 6); ln (11, 8.5f); ln (21, 8.5f); ln (21, 19); ln (3, 19); P.closeSubPath(); }
    else if (name == "upload") { P.addRoundedRectangle (3 * k, 6 * k, 18 * k, 14 * k, 1.5f * k); mv (12, 17); ln (12, 9.5f); mv (8.8f, 12.5f); ln (12, 9.3f); ln (15.2f, 12.5f); }
    else if (name == "pencil") { mv (5, 19); ln (6, 15); ln (16, 5); ln (19, 8); ln (9, 18); P.closeSubPath(); }
    else if (name == "x") { mv (6.5f, 6.5f); ln (17.5f, 17.5f); mv (17.5f, 6.5f); ln (6.5f, 17.5f); }
    else if (name == "trash") { mv (4, 6.5f); ln (20, 6.5f); mv (9.5f, 6.5f); ln (10, 3.8f); ln (14, 3.8f); ln (14.5f, 6.5f); mv (6, 6.5f); ln (7, 20.5f); ln (17, 20.5f); ln (18, 6.5f); mv (10, 10); ln (10.3f, 17); mv (14, 10); ln (13.7f, 17); }
    else if (name == "loop") { mv (7, 7.5f); ln (17, 7.5f); cu (21, 7.5f, 21, 16.5f, 17, 16.5f); mv (14, 4.5f); ln (17, 7.5f); ln (14, 10.5f); mv (17, 16.5f); ln (7, 16.5f); cu (3, 16.5f, 3, 7.5f, 7, 7.5f); }
    else if (name == "warning") { mv (12, 3.5f); ln (21.5f, 20); ln (2.5f, 20); P.closeSubPath(); mv (12, 9.5f); ln (12, 14); mv (12, 16.8f); ln (12, 17.2f); }
    else if (name == "bulb") { mv (9, 17); ln (15, 17); mv (9.8f, 20); ln (14.2f, 20); mv (9, 17); cu (9, 14, 5.5f, 12.5f, 5.5f, 9); cu (5.5f, 5.4f, 8.5f, 3, 12, 3); cu (15.5f, 3, 18.5f, 5.4f, 18.5f, 9); cu (18.5f, 12.5f, 15, 14, 15, 17); }
    else if (name == "menu") { for (float y : { 6.5f, 12.0f, 17.5f }) { mv (4, y); ln (20, y); } }
    else if (name == "minus") { mv (6, 12); ln (18, 12); }
    else if (name == "plus") { mv (6, 12); ln (18, 12); mv (12, 6); ln (12, 18); }
    else if (name == "expand") { mv (3.5f, 9); ln (3.5f, 4); ln (8.5f, 4); mv (15.5f, 4); ln (20.5f, 4); ln (20.5f, 9); mv (20.5f, 15); ln (20.5f, 20); ln (15.5f, 20); mv (8.5f, 20); ln (3.5f, 20); ln (3.5f, 15); }
    else if (name == "drag") { mv (12, 3.5f); ln (12, 15.5f); mv (7.5f, 11); ln (12, 15.5f); ln (16.5f, 11); mv (4.5f, 19.5f); ln (19.5f, 19.5f); }
    else if (name == "grip") { for (float x : { 9.0f, 15.0f }) for (float y : { 6.0f, 12.0f, 18.0f }) P.addEllipse ((x - 1.3f) * k, (y - 1.3f) * k, 2.6f * k, 2.6f * k); }
    return P;
}

void drawIcon (juce::Graphics& g, const juce::String& name, juce::Rectangle<float> r, juce::Colour c, float width, bool filled)
{
    const float s = juce::jmin (r.getWidth(), r.getHeight());
    auto p = iconPath (name, s);
    p.applyTransform (juce::AffineTransform::translation (r.getCentreX() - s / 2, r.getCentreY() - s / 2));
    g.setColour (c);
    if (filled || name == "play" || name == "stop" || name == "grip")
        g.fillPath (p);
    else
        g.strokePath (p, juce::PathStrokeType (width, juce::PathStrokeType::curved, juce::PathStrokeType::rounded));
}

// ===================================================================== logo
void paintLogoMark (juce::Graphics& g, juce::Point<float> c, float size, juce::Colour col)
{
    const int n = size < 28 ? 7 : size < 60 ? 12 : size < 160 ? 16 : 22;
    const float w = juce::jmax (0.9f, size * (size < 28 ? 0.06f : size < 60 ? 0.024f : size < 160 ? 0.016f : 0.0075f));
    const float phi = juce::degreesToRadians (136.0f);
    const float a = size * 0.47f, R = size * 0.13f;
    g.setColour (col);
    for (int dir = 0; dir < 2; ++dir)
    {
        const float dx = 1.0f / std::sqrt (2.0f), dy = (dir == 0 ? 1.0f : -1.0f) / std::sqrt (2.0f);
        const float qx = -dy, qy = dx;
        for (int k = 0; k < n; ++k)
        {
            const float th = juce::MathConstants<float>::twoPi * k / n;
            const float r0 = R * std::cos (th), r1 = R * std::cos (th + phi);
            juce::Path l;
            l.startNewSubPath (c.x - a * dx + r0 * qx, c.y - a * dy + r0 * qy);
            l.lineTo (c.x + a * dx + r1 * qx, c.y + a * dy + r1 * qy);
            g.strokePath (l, juce::PathStrokeType (w, juce::PathStrokeType::curved, juce::PathStrokeType::rounded));
        }
    }
}

void paintLogo (juce::Graphics& g, juce::Rectangle<float> r, bool plate)
{
    const float s = juce::jmin (r.getWidth(), r.getHeight());
    auto box = juce::Rectangle<float> (s, s).withCentre (r.getCentre());
    juce::Rectangle<float> win = box;
    if (plate)
    {
        auto body = box.withTrimmedLeft (s * 0.02f).withTrimmedRight (s * 0.02f).withTrimmedTop (s * 0.02f).withTrimmedBottom (s * 0.04f);
        g.setColour (juce::Colour::fromRGBA (0, 0, 0, 70));
        g.fillRoundedRectangle (body.translated (0, s * 0.02f), s * 0.2f);
        juce::ColourGradient cg (juce::Colour (0xffefebe3), body.getTopLeft(), juce::Colour (0xffafa799), body.getBottomRight(), false);
        cg.addColour (0.55, juce::Colour (0xffd8d3c9));
        g.setGradientFill (cg);
        g.fillRoundedRectangle (body, s * 0.2f);
        win = body.reduced (s * 0.13f);
    }
    const float wr = s * 0.09f;
    g.setGradientFill (juce::ColourGradient (juce::Colour (0xff0d0f11), win.getX(), win.getY(), juce::Colour (0xff181b1e), win.getX(), win.getBottom(), false));
    g.fillRoundedRectangle (win, wr);
    g.setColour (juce::Colours::black);
    g.drawRoundedRectangle (win, wr, juce::jmax (0.8f, s * 0.01f));
    if (s >= 40)
    {
        juce::Graphics::ScopedSaveState ss (g);
        g.reduceClipRegion (rrect (win, wr));
        g.setColour (juce::Colour::fromRGBA (255, 255, 255, 14));
        for (int k = 1; k < 4; ++k)
        {
            const float x = win.getX() + win.getWidth() * k / 4, y = win.getY() + win.getHeight() * k / 4;
            g.drawLine (x, win.getY(), x, win.getBottom(), juce::jmax (0.6f, s * 0.004f));
            g.drawLine (win.getX(), y, win.getRight(), y, juce::jmax (0.6f, s * 0.004f));
        }
    }
    juce::ColourGradient glow (juce::Colour::fromRGBA (232, 72, 58, 55), win.getCentreX(), win.getCentreY(),
                               juce::Colour::fromRGBA (232, 72, 58, 0), win.getCentreX() + win.getWidth() * 0.55f, win.getCentreY(), true);
    g.setGradientFill (glow);
    g.fillEllipse (win.withSizeKeepingCentre (win.getWidth() * 1.1f, win.getHeight() * 1.1f));
    paintLogoMark (g, win.getCentre(), win.getWidth() * 0.86f, juce::Colour (0xffe8483a));
}

// ============================================================= look & feel
LookAndFeel::LookAndFeel()
{
    refreshColours();
}

void LookAndFeel::refreshColours()
{
    setColour (juce::ComboBox::textColourId, C ("on_dark"));
    setColour (juce::ComboBox::arrowColourId, C ("on_dark"));
    setColour (juce::PopupMenu::backgroundColourId, juce::Colour (0xff1d1e21));
    setColour (juce::PopupMenu::textColourId, C ("on_dark"));
    setColour (juce::PopupMenu::highlightedBackgroundColourId, juce::Colour (0xff3a2a28));
    setColour (juce::PopupMenu::highlightedTextColourId, juce::Colours::white);
    setColour (juce::PopupMenu::headerTextColourId, C ("on_dark_muted"));
    setColour (juce::TextEditor::textColourId, C ("on_dark"));
    setColour (juce::TextEditor::highlightColourId, C ("red").withAlpha (0.55f));
    setColour (juce::TextEditor::highlightedTextColourId, juce::Colours::white);
    setColour (juce::CaretComponent::caretColourId, C ("on_dark"));
    setColour (juce::TextEditor::backgroundColourId, C ("field"));
    setColour (juce::TextEditor::outlineColourId, C ("field_edge"));
    setColour (juce::TextEditor::focusedOutlineColourId, C ("field_focus"));
    setColour (juce::Label::textColourId, C ("on_dark"));
    setColour (juce::ScrollBar::thumbColourId, juce::Colour (0xff55585e));
    setColour (juce::TooltipWindow::backgroundColourId, juce::Colour (0xff1d1e21));
    setColour (juce::TooltipWindow::textColourId, C ("on_dark"));
}

juce::Font LookAndFeel::getComboBoxFont (juce::ComboBox&) { return font (13.0f, 400, 0.2f); }
juce::Font LookAndFeel::getPopupMenuFont() { return font (13.0f, 400, 0.2f); }
juce::Font LookAndFeel::getLabelFont (juce::Label& l) { return l.getFont(); }

void LookAndFeel::drawComboBox (juce::Graphics& g, int w, int h, bool, int, int, int, int, juce::ComboBox& box)
{
    auto r = juce::Rectangle<float> (0, 0, (float) w, (float) h).reduced (0.5f);
    g.setColour (C ("field"));
    g.fillRoundedRectangle (r, 3.0f);
    g.setColour (box.hasKeyboardFocus (true) ? C ("field_focus") : C ("field_edge"));
    g.drawRoundedRectangle (r, 3.0f, 1.0f);
    juce::Path tri;
    const float cx = (float) w - 15, cy = (float) h / 2;
    tri.addTriangle (cx - 4.5f, cy - 2.2f, cx + 4.5f, cy - 2.2f, cx, cy + 3.0f);
    g.setColour (box.isEnabled() ? C ("on_dark") : C ("on_dark_dim"));
    g.fillPath (tri);
}

void LookAndFeel::positionComboBoxText (juce::ComboBox& box, juce::Label& label)
{
    label.setBounds (8, 1, box.getWidth() - 30, box.getHeight() - 2);
    label.setFont (getComboBoxFont (box));
}

void LookAndFeel::drawPopupMenuBackground (juce::Graphics& g, int w, int h)
{
    g.fillAll (juce::Colour (0xff1d1e21));
    g.setColour (juce::Colour (0xff45484d));
    g.drawRect (0, 0, w, h, 1);
}

void LookAndFeel::drawPopupMenuItem (juce::Graphics& g, const juce::Rectangle<int>& area, bool isSeparator, bool isActive,
                                     bool isHighlighted, bool isTicked, bool hasSubMenu, const juce::String& txt,
                                     const juce::String& shortcut, const juce::Drawable* icon, const juce::Colour* colour)
{
    if (isSeparator)
    {
        g.setColour (juce::Colour (0xff3a3d42));
        g.fillRect (area.reduced (8, 0).withHeight (1).withY (area.getCentreY()));
        return;
    }
    if (isHighlighted && isActive)
    {
        g.setColour (juce::Colour (0xff3a2a28));
        g.fillRect (area);
        g.setColour (C ("red_hi"));
        g.fillRect (area.withWidth (3));
    }
    auto r = area.toFloat().withTrimmedLeft (26).withTrimmedRight (12);
    if (isTicked)
        led (g, { (float) area.getX() + 13, (float) area.getCentreY() }, 3.6f, C ("led_red"), true, false);
    text (g, r, txt, font (13.0f, isTicked ? 600 : 400, 0.2f), isActive ? C ("on_dark") : C ("on_dark_dim"));
    if (shortcut.isNotEmpty())
        text (g, r, shortcut, font (11.5f, 400, 0.4f), C ("on_dark_muted"), juce::Justification::centredRight);
    if (hasSubMenu)
    {
        juce::Path tri;
        const float x = (float) area.getRight() - 12, y = (float) area.getCentreY();
        tri.addTriangle (x - 3, y - 4, x - 3, y + 4, x + 2, y);
        g.setColour (C ("on_dark"));
        g.fillPath (tri);
    }
    juce::ignoreUnused (icon, colour);
}

void LookAndFeel::drawPopupMenuSectionHeader (juce::Graphics& g, const juce::Rectangle<int>& area, const juce::String& name)
{
    text (g, area.toFloat().withTrimmedLeft (12), name.toUpperCase(), font (11.0f, 600, 1.4f), C ("on_dark_muted"));
}

void LookAndFeel::fillTextEditorBackground (juce::Graphics& g, int w, int h, juce::TextEditor&)
{
    g.setColour (C ("field"));
    g.fillRoundedRectangle (0, 0, (float) w, (float) h, 3.0f);
}

void LookAndFeel::drawTextEditorOutline (juce::Graphics& g, int w, int h, juce::TextEditor& te)
{
    g.setColour (te.hasKeyboardFocus (true) && ! te.isReadOnly() ? C ("field_focus") : C ("field_edge"));
    g.drawRoundedRectangle (0.5f, 0.5f, (float) w - 1, (float) h - 1, 3.0f, 1.0f);
}

void LookAndFeel::drawScrollbar (juce::Graphics& g, juce::ScrollBar&, int x, int y, int w, int h, bool vertical,
                                 int thumbStart, int thumbSize, bool over, bool down)
{
    auto track = juce::Rectangle<float> ((float) x, (float) y, (float) w, (float) h).reduced (2.0f);
    g.setColour (juce::Colour (0xff131416));
    g.fillRoundedRectangle (track, 3.0f);
    auto thumb = vertical ? juce::Rectangle<float> (track.getX(), (float) thumbStart + 2, track.getWidth(), (float) thumbSize - 4)
                          : juce::Rectangle<float> ((float) thumbStart + 2, track.getY(), (float) thumbSize - 4, track.getHeight());
    g.setColour (down ? juce::Colour (0xff8a867f) : over ? juce::Colour (0xff6d6a65) : juce::Colour (0xff55585e));
    g.fillRoundedRectangle (thumb, 3.0f);
}

void LookAndFeel::drawTooltip (juce::Graphics& g, const juce::String& txt, int w, int h)
{
    g.fillAll (juce::Colour (0xff1d1e21));
    g.setColour (juce::Colour (0xff45484d));
    g.drawRect (0, 0, w, h, 1);
    juce::AttributedString as;
    as.append (txt, font (12.5f, 400, 0.2f), C ("on_dark"));
    as.setWordWrap (juce::AttributedString::byWord);
    as.draw (g, juce::Rectangle<float> (10, 6, (float) w - 20, (float) h - 12));
}

juce::Rectangle<int> LookAndFeel::getTooltipBounds (const juce::String& tip, juce::Point<int> pos, juce::Rectangle<int> parent)
{
    juce::AttributedString as;
    as.append (tip, font (12.5f, 400, 0.2f), C ("on_dark"));
    as.setWordWrap (juce::AttributedString::byWord);
    juce::TextLayout tl;
    tl.createLayout (as, 320.0f);
    const int w = (int) tl.getWidth() + 22, h = (int) tl.getHeight() + 14;
    return juce::Rectangle<int> (pos.x + 12, pos.y + 18, w, h).constrainedWithin (parent);
}

} // namespace xk::ui
