#include "engine/Tempo.h"

#include <algorithm>
#include <cmath>

namespace xk::tempo
{

static std::vector<double> autocorrNorm (const std::vector<double>& x)
{
    double mean = 0;
    for (double v : x) mean += v;
    mean /= (double) std::max<size_t> (1, x.size());
    std::vector<double> d (x.size());
    for (size_t i = 0; i < x.size(); ++i)
        d[i] = x[i] - mean;
    auto ac = fft::autocorr (d.data(), (int) d.size());
    const double a0 = ac.empty() ? 1.0 : ac[0] + EPS;
    for (auto& v : ac)
        v /= a0;
    return ac;
}

static double foldSharpness (const std::vector<double>& pos, const std::vector<double>& w, double period,
                             std::vector<double>* histOut = nullptr, int bins = 96)
{
    std::vector<double> h ((size_t) bins, 0.0);
    for (size_t i = 0; i < pos.size(); ++i)
    {
        double ph = std::fmod (pos[i], period);
        if (ph < 0) ph += period;
        ph /= period;
        int b = ((int) (ph * bins)) % bins;
        h[(size_t) b] += w[i];
    }
    std::vector<double> s ((size_t) bins);
    for (int i = 0; i < bins; ++i)
        s[(size_t) i] = (h[(size_t) i] + h[(size_t) ((i - 1 + bins) % bins)] + h[(size_t) ((i + 1) % bins)]) / 3.0;
    double mx = -1e300, mean = 0;
    for (double v : s)
    {
        mx = std::max (mx, v);
        mean += v;
    }
    mean /= bins;
    if (histOut)
        *histOut = s;
    return mx / (mean + EPS);
}

static double roundHalfEven (double x)
{
    return std::nearbyint (x);   // default rounding mode = round half to even
}

static double downbeat (const Analysis& an, double bpm, double beatPhase)
{
    const double period = 60.0 * an.sr / bpm;
    const int H = Analysis::HOP_ONSET;
    const auto& low = an.fluxLow;
    const auto& full = an.flux;
    const int nf = (int) low.size();
    std::vector<double> mid ((size_t) nf);
    for (int i = 0; i < nf; ++i)
        mid[(size_t) i] = std::max (0.0f, full[(size_t) i] - low[(size_t) i]);
    const int nb = (int) std::floor ((an.n - beatPhase) / period);
    if (nb < 8)
        return beatPhase;
    std::vector<int> idx ((size_t) nb);
    for (int b = 0; b < nb; ++b)
        idx[(size_t) b] = std::clamp ((int) roundHalfEven ((beatPhase + b * period) / H), 0, nf - 1);
    auto around = [&] (auto&& get) {
        std::vector<double> out ((size_t) nb, 0.0);
        for (int b = 0; b < nb; ++b)
            for (int d = -1; d <= 1; ++d)
                out[(size_t) b] = std::max (out[(size_t) b], (double) get (std::clamp (idx[(size_t) b] + d, 0, nf - 1)));
        return out;
    };
    auto lb = around ([&] (int i) { return low[(size_t) i]; });
    auto mb = around ([&] (int i) { return mid[(size_t) i]; });
    auto normalize = [] (std::vector<double>& v) {
        double m = 0;
        for (double x : v) m += x;
        m /= (double) std::max<size_t> (1, v.size());
        for (auto& x : v) x /= (m + EPS);
    };
    normalize (lb);
    normalize (mb);
    double firstOn = -1;
    {
        std::vector<float> fv (full.begin(), full.end());
        const double p97 = percentile (fv, 97.0);
        for (int i = 0; i < nf; ++i)
            if (full[(size_t) i] > p97)
            {
                firstOn = (double) i * H;
                break;
            }
    }
    auto meanOf = [&] (const std::vector<double>& v, int startIdx) {
        double s = 0;
        int c = 0;
        for (int i = startIdx; i < nb; i += 4)
        {
            s += v[(size_t) i];
            ++c;
        }
        return c ? s / c : 0.0;
    };
    std::vector<double> scores;
    for (int b = 0; b < 4; ++b)
    {
        double s = meanOf (lb, b) + 0.5 * (meanOf (mb, (b + 1) % 4) + meanOf (mb, (b + 3) % 4)) / 2.0
                   - 0.25 * meanOf (mb, b);
        if (firstOn >= 0)
        {
            const double d0 = beatPhase + b * period;
            double dist = std::fmod (firstOn - d0, 4 * period);
            if (dist < 0) dist += 4 * period;
            dist = std::min (dist, 4 * period - dist);
            if (dist < 0.06 * an.sr)
                s += 0.35;
        }
        scores.push_back (s);
    }
    const int b = (int) (std::max_element (scores.begin(), scores.end()) - scores.begin());
    double d = beatPhase + b * period;
    const double bar = 4 * period;
    d = std::fmod (d, bar);
    if (d < 0) d += bar;
    return d;
}

std::shared_ptr<TempoEst> estimate (const Analysis& an)
{
    const int nf = (int) an.flux.size();
    std::vector<double> o ((size_t) nf);
    double omax = 0;
    for (int i = 0; i < nf; ++i)
    {
        o[(size_t) i] = (double) an.flux[(size_t) i] + (double) an.fluxLow[(size_t) i];
        omax = std::max (omax, o[(size_t) i]);
    }
    const double fps = an.fps;
    if (nf < fps * 4 || omax <= 0)
        return nullptr;
    const auto ac = autocorrNorm (o);
    auto score = [&] (double b) {
        const double lag = 60.0 * fps / b;
        double s = 0;
        const double mults[3] = { 1, 2, 4 }, wts[3] = { 1.0, 0.5, 0.25 };
        for (int q = 0; q < 3; ++q)
        {
            const double L = lag * mults[q];
            const int i = (int) L;
            if (i + 1 >= (int) ac.size())
                continue;
            const double fr = L - i;
            s += wts[q] * (ac[(size_t) i] * (1 - fr) + ac[(size_t) i + 1] * fr);
        }
        return s;
    };
    double best = 60.0, bestv = -1e300;
    for (int k = 0; k < 560; ++k)
    {
        const double b = 60.0 + 0.25 * k;
        const double prior = std::exp (-0.5 * std::pow (std::log2 (b / 120.0) / 0.7, 2.0));
        const double v = score (b) * prior;
        if (v > bestv)
        {
            bestv = v;
            best = b;
        }
    }
    const double sBest = score (best);
    if (best < 88 && score (best * 2) > 0.55 * sBest)
        best *= 2;
    else if (best > 170 && score (best / 2) > 0.55 * sBest)
        best /= 2;

    // fine search by folding onset strength over the whole file
    const double p80 = percentileD (o, 80.0);
    std::vector<double> pos, w;
    for (int i = 0; i < nf; ++i)
        if (o[(size_t) i] > p80)
        {
            pos.push_back ((double) i * Analysis::HOP_ONSET);
            w.push_back (o[(size_t) i]);
        }
    const double c0 = best - 1.5;
    const int nc = (int) std::ceil (((best + 1.5) - c0) / 0.01);
    double bpm = c0, top = -1e300;
    for (int k = 0; k < nc; ++k)
    {
        const double b = c0 + k * 0.01;
        const double s = foldSharpness (pos, w, 60.0 * an.sr / b);
        if (s > top)
        {
            top = s;
            bpm = b;
        }
    }
    const double r = roundHalfEven (bpm);
    if (std::abs (bpm - r) < 0.08 && foldSharpness (pos, w, 60.0 * an.sr / r) >= 0.95 * top)
        bpm = r;
    const double period = 60.0 * an.sr / bpm;
    std::vector<double> hist;
    const double conf = foldSharpness (pos, w, period, &hist);
    const int hb = (int) (std::max_element (hist.begin(), hist.end()) - hist.begin());
    const double beatPhase = (hb + 0.5) / (double) hist.size() * period;
    const double db = downbeat (an, bpm, beatPhase);
    auto est = std::make_shared<TempoEst>();
    est->bpm = std::round (bpm * 100.0) / 100.0;
    est->confidence = conf;
    est->downbeat = (int) db;
    return est;
}

bool fits (double a, double b)
{
    if (a <= 0 || b <= 0)
        return true;
    for (double ratio : { 1.0, 2.0, 0.5, 1.5, 2.0 / 3.0 })
        if (std::abs (a * ratio - b) / b < 0.035)
            return true;
    return false;
}

} // namespace xk::tempo
