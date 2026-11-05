#include "engine/Render.h"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <fstream>

namespace xk::render
{

static constexpr double kPi = 3.14159265358979323846;

std::pair<double, double> defaultFadesMs (const Chop& chop)
{
    if (chop.kind == "loop")
        return chop.seam ? std::pair { 0.0, 0.0 } : std::pair { 0.4, 2.0 };
    if (chop.kind == "hit" || chop.kind == "roll")
        return { 0.6, chop.cutAtNext ? 3.0 : 8.0 };
    return { 2.0, 12.0 };
}

static int seamLength (const Chop& chop, int sr)
{
    return (int) std::min (0.012 * sr, (double) (std::max (0, chop.end - chop.start) / 8));
}

// 0.5 - 0.5 cos(linspace(0, pi, length))
static std::vector<float> fadeCurve (int length)
{
    std::vector<float> f ((size_t) std::max (1, length));
    const int n = (int) f.size();
    for (int i = 0; i < n; ++i)
    {
        const double x = n > 1 ? kPi * i / (n - 1) : 0.0;
        f[(size_t) i] = (float) (0.5 - 0.5 * std::cos (x));
    }
    return f;
}

std::vector<std::vector<float>> renderChop (const Stem& stem, const Chop& chop)
{
    const int s = std::max (0, chop.start);
    const int e = std::min (stem.frames(), chop.end);
    const int ch = stem.channels();
    std::vector<std::vector<float>> x ((size_t) ch);
    const int n = std::max (0, e - s);
    for (int c = 0; c < ch; ++c)
        x[(size_t) c].assign (stem.audio[(size_t) c].begin() + s, stem.audio[(size_t) c].begin() + s + n);
    if (n == 0)
        return x;
    const int sr = stem.sr;
    // loop seam: blend the end into the audio just before the loop start
    if (chop.kind == "loop" && chop.seam && ! chop.reverse)
    {
        const int k = seamLength (chop, sr);
        if (k > 8 && s - k >= 0 && k <= n)
            for (int c = 0; c < ch; ++c)
                for (int i = 0; i < k; ++i)
                {
                    const double r = (k > 1 ? (kPi / 2) * i / (k - 1) : 0.0);
                    auto& v = x[(size_t) c][(size_t) (n - k + i)];
                    v = (float) (v * std::cos (r) + stem.audio[(size_t) c][(size_t) (s - k + i)] * std::sin (r));
                }
    }
    if (chop.reverse)
        for (auto& v : x)
            std::reverse (v.begin(), v.end());
    auto [din, dout] = defaultFadesMs (chop);
    const double finMs = chop.fadeInMs < 0 ? din : chop.fadeInMs;
    const double foutMs = chop.fadeOutMs < 0 ? dout : chop.fadeOutMs;
    int fin = (int) (finMs / 1000.0 * sr);
    int fout = (int) (foutMs / 1000.0 * sr);
    if (chop.fadeInMs < 0) fin = std::min (fin, n / 4);
    if (chop.fadeOutMs < 0) fout = std::min (fout, n / 3);
    fin = std::min (fin, n);
    fout = std::min (fout, n);
    if (fin > 1)
    {
        const auto f = fadeCurve (fin);
        for (auto& v : x)
            for (int i = 0; i < fin; ++i)
                v[(size_t) i] *= f[(size_t) i];
    }
    if (fout > 1)
    {
        const auto f = fadeCurve (fout);
        for (auto& v : x)
            for (int i = 0; i < fout; ++i)
                v[(size_t) (n - fout + i)] *= f[(size_t) (fout - 1 - i)];
    }
    float peak = 0;
    for (auto& v : x)
        for (float a : v)
            peak = std::max (peak, std::abs (a));
    if (peak > 1e-9f)
    {
        const double gain = std::min (0.0, chop.gainDb);
        const float k = (float) (std::pow (10.0, (PEAK_DB + gain) / 20.0) / peak);
        for (auto& v : x)
            for (auto& a : v)
                a *= k;
    }
    return x;
}

static void put16 (std::vector<char>& b, uint32_t v) { b.push_back ((char) (v & 0xff)); b.push_back ((char) ((v >> 8) & 0xff)); }
static void put32 (std::vector<char>& b, uint32_t v) { put16 (b, v & 0xffff); put16 (b, v >> 16); }

std::vector<char> wav24Bytes (const std::vector<std::vector<float>>& x, int sr)
{
    const int ch = std::max (1, (int) x.size());
    const int n = x.empty() ? 0 : (int) x[0].size();
    const uint32_t block = 3u * (uint32_t) ch;
    const uint32_t dataLen = block * (uint32_t) n;
    const bool pad = dataLen % 2;
    std::vector<char> b;
    b.reserve (44 + dataLen + 1);
    b.insert (b.end(), { 'R', 'I', 'F', 'F' });
    put32 (b, 4 + (8 + 16) + (8 + dataLen + (pad ? 1 : 0)));
    b.insert (b.end(), { 'W', 'A', 'V', 'E', 'f', 'm', 't', ' ' });
    put32 (b, 16);
    put16 (b, 1);
    put16 (b, (uint32_t) ch);
    put32 (b, (uint32_t) sr);
    put32 (b, (uint32_t) sr * block);
    put16 (b, block);
    put16 (b, 24);
    b.insert (b.end(), { 'd', 'a', 't', 'a' });
    put32 (b, dataLen);
    for (int i = 0; i < n; ++i)
        for (int c = 0; c < ch; ++c)
        {
            const double v = x.empty() ? 0.0 : (double) x[(size_t) c][(size_t) i];
            const long q = std::clamp ((long) std::nearbyint (v * 8388607.0), -8388608L, 8388607L);
            const uint32_t u = (uint32_t) (q & 0xffffff);
            b.push_back ((char) (u & 0xff));
            b.push_back ((char) ((u >> 8) & 0xff));
            b.push_back ((char) ((u >> 16) & 0xff));
        }
    if (pad)
        b.push_back (0);
    return b;
}

bool writeWav24 (const std::string& path, const std::vector<std::vector<float>>& x, int sr)
{
    const auto bytes = wav24Bytes (x, sr);
    std::ofstream f (path, std::ios::binary);
    if (! f)
        return false;
    f.write (bytes.data(), (std::streamsize) bytes.size());
    return (bool) f;
}

} // namespace xk::render
