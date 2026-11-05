#include "engine/Dsp.h"

#include <algorithm>
#include <atomic>
#include <cmath>
#include <numeric>

namespace xk
{

static std::atomic<int> gIds { 1 };
int nextId() { return gIds.fetch_add (1); }

const Vec& Stem::mono()
{
    if (! haveMono_)
    {
        const int nf = frames();
        mono_.assign ((size_t) nf, 0.0f);
        const int ch = channels();
        if (ch > 0)
        {
            for (int c = 0; c < ch; ++c)
                for (int i = 0; i < nf; ++i)
                    mono_[(size_t) i] += audio[(size_t) c][(size_t) i];
            const float k = 1.0f / (float) ch;
            for (auto& v : mono_)
                v *= k;
        }
        haveMono_ = true;
    }
    return mono_;
}

// ---------------------------------------------------------------- helpers
double percentile (std::vector<float> v, double q)
{
    if (v.empty())
        return 0.0;
    std::sort (v.begin(), v.end());
    const double idx = q / 100.0 * (double) (v.size() - 1);
    const size_t lo = (size_t) std::floor (idx);
    const size_t hi = std::min (lo + 1, v.size() - 1);
    const double fr = idx - (double) lo;
    return (double) v[lo] + ((double) v[hi] - (double) v[lo]) * fr;
}

double percentileD (std::vector<double> v, double q)
{
    if (v.empty())
        return 0.0;
    std::sort (v.begin(), v.end());
    const double idx = q / 100.0 * (double) (v.size() - 1);
    const size_t lo = (size_t) std::floor (idx);
    const size_t hi = std::min (lo + 1, v.size() - 1);
    const double fr = idx - (double) lo;
    return v[lo] + (v[hi] - v[lo]) * fr;
}

double median (std::vector<double> v)
{
    if (v.empty())
        return 0.0;
    std::sort (v.begin(), v.end());
    const size_t n = v.size();
    return n % 2 ? v[n / 2] : 0.5 * (v[n / 2 - 1] + v[n / 2]);
}

Vec frameRms (const Vec& m, int hop, int win)
{
    const int n = (int) m.size();
    std::vector<double> c ((size_t) n + 1, 0.0);
    for (int i = 0; i < n; ++i)
        c[(size_t) i + 1] = c[(size_t) i] + (double) m[(size_t) i] * (double) m[(size_t) i];
    Vec out;
    out.reserve ((size_t) (n / hop + 1));
    for (int ctr = 0; ctr < n; ctr += hop)
    {
        const int a = std::clamp (ctr - win / 2, 0, n);
        const int b = std::clamp (ctr + win / 2, 0, n);
        const double s = std::max (c[(size_t) b] - c[(size_t) a], 0.0) / (double) std::max (b - a, 1);
        out.push_back ((float) std::sqrt (s));
    }
    return out;
}

Vec movingMean (const Vec& x, int w)
{
    w = std::max (1, w);
    const int n = (int) x.size();
    std::vector<double> c ((size_t) n + 1, 0.0);
    for (int i = 0; i < n; ++i)
        c[(size_t) i + 1] = c[(size_t) i] + x[(size_t) i];
    Vec out ((size_t) n);
    for (int i = 0; i < n; ++i)
    {
        const int a = std::clamp (i - w / 2, 0, n);
        const int b = std::clamp (i + w / 2 + 1, 0, n);
        out[(size_t) i] = (float) ((c[(size_t) b] - c[(size_t) a]) / (double) std::max (b - a, 1));
    }
    return out;
}

std::vector<double> boxSame (const float* x, int n, int k)
{
    // np.convolve(x, ones(k)/k, "same"): out[i] = sum_{t<k} x[i + (k-1)//2 - t] / k
    std::vector<double> out ((size_t) std::max (n, k));
    if (n < k)
    {
        // numpy returns max(n, k) values centred on the full convolution
        const int full = n + k - 1;
        const int off = (full - k) / 2;
        for (int i = 0; i < k; ++i)
        {
            double s = 0;
            const int j = i + off;
            for (int t = 0; t < k; ++t)
            {
                const int q = j - t;
                if (q >= 0 && q < n)
                    s += x[q];
            }
            out[(size_t) i] = s / k;
        }
        return out;
    }
    std::vector<double> c ((size_t) n + 1, 0.0);
    for (int i = 0; i < n; ++i)
        c[(size_t) i + 1] = c[(size_t) i] + x[i];
    const int off = (k - 1) / 2;
    for (int i = 0; i < n; ++i)
    {
        const int hi = std::min (n - 1, i + off);
        const int lo = std::max (0, i + off - (k - 1));
        out[(size_t) i] = (hi >= lo ? c[(size_t) hi + 1] - c[(size_t) lo] : 0.0) / k;
    }
    return out;
}

std::vector<float> hanning (int n)
{
    std::vector<float> w ((size_t) n);
    if (n == 1)
    {
        w[0] = 1.0f;
        return w;
    }
    for (int i = 0; i < n; ++i)
        w[(size_t) i] = (float) (0.5 - 0.5 * std::cos (2.0 * PI * i / (n - 1)));
    return w;
}

std::vector<double> rfftFreqs (int nFft, int sr)
{
    std::vector<double> f ((size_t) nFft / 2 + 1);
    for (size_t k = 0; k < f.size(); ++k)
        f[k] = (double) k * (double) sr / (double) nFft;
    return f;
}

std::vector<int> bandEdges (int sr, int nFft, std::vector<double>& freqs, int nBands, double lo, double hi)
{
    hi = std::min (hi, sr / 2.0 * 0.98);
    freqs = rfftFreqs (nFft, sr);
    std::vector<int> edges ((size_t) nBands + 1);
    for (int i = 0; i <= nBands; ++i)
    {
        // np.geomspace
        double hz = lo * std::pow (hi / lo, (double) i / nBands);
        if (i == 0) hz = lo;
        if (i == nBands) hz = hi;
        edges[(size_t) i] = (int) (std::lower_bound (freqs.begin(), freqs.end(), hz) - freqs.begin());
    }
    return edges;
}

// ----------------------------------------------------------------- analysis
Analysis::Analysis (Vec mono, int sampleRate) : m (std::move (mono)), sr (sampleRate)
{
    n = (int) m.size();
    env = frameRms (m, HOP_ENV, HOP_ENV * 4);
    peak = 0;
    for (float v : m)
        peak = std::max (peak, (double) std::abs (v));
    std::vector<float> nz;
    nz.reserve (env.size());
    for (float v : env)
        if (v > 1e-7f)
            nz.push_back (v);
    double fl = nz.empty() ? 1e-7 : percentile (nz, 2.0);
    fl = std::min (fl, peak * std::pow (10.0, -60.0 / 20.0));
    floor = std::max ({ fl, peak * std::pow (10.0, -90.0 / 20.0), 1e-8 });
    onsetStrength();
}

void Analysis::onsetStrength()
{
    const int nFft = 1024, hop = HOP_ONSET;
    auto freqs = rfftFreqs (nFft, sr);
    std::vector<int> lowBins, highBins;
    for (int k = 0; k < (int) freqs.size(); ++k)
    {
        if (freqs[(size_t) k] < 160) lowBins.push_back (k);
        if (freqs[(size_t) k] > 5000) highBins.push_back (k);
    }
    const double ref = std::max (peak, 1e-6);
    const int nb = nFft / 2 + 1;
    std::vector<float> prev ((size_t) nb), cur ((size_t) nb);
    bool first = true;
    const int nFrames = 1 + n / hop;
    flux.assign ((size_t) nFrames, 0);
    fluxLow.assign ((size_t) nFrames, 0);
    fluxHigh.assign ((size_t) nFrames, 0);
    stftMag (m.data(), n, nFft, hop, [&] (int k, const float* mag) {
        for (int b = 0; b < nb; ++b)
            cur[(size_t) b] = std::log1p (mag[b] * (float) (100.0 / ref));
        if (first)
        {
            prev = cur;
            first = false;
        }
        double sAll = 0, sLow = 0, sHigh = 0;
        for (int b = 0; b < nb; ++b)
        {
            const double d = std::max (0.0f, cur[(size_t) b] - prev[(size_t) b]);
            sAll += d;
        }
        for (int b : lowBins) sLow += std::max (0.0f, cur[(size_t) b] - prev[(size_t) b]);
        for (int b : highBins) sHigh += std::max (0.0f, cur[(size_t) b] - prev[(size_t) b]);
        flux[(size_t) k] = (float) (sAll / nb);
        fluxLow[(size_t) k] = lowBins.empty() ? 0.0f : (float) (sLow / (double) lowBins.size());
        fluxHigh[(size_t) k] = highBins.empty() ? 0.0f : (float) (sHigh / (double) highBins.size());
        std::swap (prev, cur);
    });
    fps = sr / (double) hop;
}

std::vector<int> Analysis::onsets (double sensitivity, double minGap) const
{
    const auto& f = flux;
    const int nf = (int) f.size();
    if (nf < 5)
        return {};
    const Vec base = movingMean (f, (int) (0.3 * fps));
    const double p99 = percentile (f, 99.5);
    const double delta = 0.06 * p99 / std::max (sensitivity, 0.1);
    const double gate = std::max (floor * 4, peak * std::pow (10.0, -48.0 / 20.0));
    const int minFrames = std::max (1, (int) (minGap * fps));
    const int look = (int) (0.03 * fps) + 1;
    std::vector<int> out;
    int last = -1000000000;
    for (int i = 0; i < nf; ++i)
    {
        const double thr = base[(size_t) i] * 1.4 + delta;
        const float fi = f[(size_t) i];
        const float fp = f[(size_t) ((i - 1 + nf) % nf)];
        const float fn = f[(size_t) ((i + 1) % nf)];
        if (! (fi > thr && fi >= fp && fi >= fn))
            continue;
        const int lo = std::max (0, i - 2), hi = std::min (nf, i + 3);
        float mx = f[(size_t) lo];
        for (int j = lo; j < hi; ++j) mx = std::max (mx, f[(size_t) j]);
        if (fi < mx)
            continue;
        float lm = -1.0f;
        for (int j = i; j < std::min (nf, i + look); ++j)
            lm = std::max (lm, envAt ((int) (((long long) j * HOP_ONSET) / HOP_ENV)));
        if (lm < 0 || lm < gate)
            continue;
        if (i - last < minFrames)
        {
            if (! out.empty() && fi > f[(size_t) out.back()])
            {
                out.back() = i;
                last = i;
            }
            continue;
        }
        out.push_back (i);
        last = i;
    }
    std::vector<int> starts;
    for (int i : out)
        starts.push_back (refineStart (i * HOP_ONSET));
    std::sort (starts.begin(), starts.end());
    starts.erase (std::unique (starts.begin(), starts.end()), starts.end());
    if (starts.size() > 1)
    {
        const int gap = (int) (0.02 * sr);
        std::vector<int> kept { starts[0] };
        for (size_t i = 1; i < starts.size(); ++i)
            if (starts[i] - starts[i - 1] > gap)
                kept.push_back (starts[i]);
        starts.swap (kept);
    }
    return starts;
}

int Analysis::refineStart (int approx) const
{
    const int a = std::max (0, approx - (int) (0.025 * sr));
    const int b = std::min (n, approx + (int) (0.03 * sr));
    if (b - a < 8)
        return std::max (0, approx);
    std::vector<float> seg ((size_t) (b - a));
    for (int i = a; i < b; ++i)
        seg[(size_t) (i - a)] = std::abs (m[(size_t) i]);
    const int k = std::max (1, (int) (0.0005 * sr));
    auto sm = boxSame (seg.data(), (int) seg.size(), k);
    int p = (int) (std::max_element (sm.begin(), sm.end()) - sm.begin());
    const double pk = sm[(size_t) p];
    if (pk <= 0)
        return std::max (0, approx);
    int st = 0;
    for (int i = p; i >= 0; --i)
        if (sm[(size_t) i] < 0.05 * pk)
        {
            st = i;
            break;
        }
    st = a + st - (int) (0.0008 * sr);
    return std::max (0, st);
}

int Analysis::peakIndex (int start, int end) const
{
    const int ne = (int) env.size();
    const int a = std::min (start / HOP_ENV, ne - 1);
    const int b = std::max (a + 1, std::min (ne, end / HOP_ENV));
    int best = a;
    for (int i = a; i < std::min (b, ne); ++i)
        if (env[(size_t) i] > env[(size_t) best])
            best = i;
    return best;
}

std::pair<int, bool> Analysis::tailEnd (int start, int limit, double relDb, double hold, double maxLen) const
{
    const int H = HOP_ENV;
    if (maxLen > 0)
        limit = std::min (limit, start + (int) (maxLen * sr));
    limit = std::min (limit, n);
    if (limit - start < (int) (0.004 * sr))
        return { limit, true };
    const int pk = peakIndex (start, std::min (limit, start + (int) (0.08 * sr)));
    const double thr = std::max (env[(size_t) pk] * std::pow (10.0, relDb / 20.0), floor * 1.6);
    const int segEnd = std::min ((int) env.size(), std::max (pk + 1, limit / H));
    const int len = segEnd - pk;
    const int hf = std::max (1, (int) (hold * sr / H));
    if (len >= hf)
    {
        int run = 0;
        for (int i = 0; i < len; ++i)
        {
            run += env[(size_t) (pk + i)] < thr ? 1 : 0;
            if (i >= hf)
                run -= env[(size_t) (pk + i - hf)] < thr ? 1 : 0;
            if (i >= hf - 1 && run == hf)
            {
                const int idx = i - hf + 1;
                const int end = (pk + idx) * H + (int) (0.004 * sr);
                if (end < limit)
                    return { end, false };
                break;
            }
        }
    }
    return { limit, true };
}

std::vector<char> Analysis::activeMask (int hop, double relDb) const
{
    const Vec e = frameRms (m, hop, hop * 2);
    const double thr = std::max (peak * std::pow (10.0, relDb / 20.0), floor * 4);
    std::vector<char> mask (e.size());
    for (size_t i = 0; i < e.size(); ++i)
        mask[i] = e[i] > thr;
    return mask;
}

static double flatness (const std::vector<double>& spec, const std::vector<double>& freqs, double lo, double hi)
{
    double sumLog = 0, sum = 0;
    int cnt = 0;
    for (size_t k = 0; k < spec.size(); ++k)
        if (freqs[k] > lo && freqs[k] < hi)
        {
            const double v = spec[k] + EPS;
            sumLog += std::log (v);
            sum += v;
            ++cnt;
        }
    if (cnt == 0)
        return 0.0;
    return std::exp (sumLog / cnt) / (sum / cnt);
}

static std::vector<double> interpPoints (const std::vector<double>& y, int count)
{
    std::vector<double> out ((size_t) count);
    const int len = (int) y.size();
    for (int i = 0; i < count; ++i)
    {
        const double x = count > 1 ? (double) (len - 1) * i / (count - 1) : 0.0;
        const int i0 = (int) std::floor (x);
        const int i1 = std::min (len - 1, i0 + 1);
        const double fr = x - i0;
        out[(size_t) i] = len ? y[(size_t) i0] + (y[(size_t) i1] - y[(size_t) i0]) * fr : 0.0;
    }
    return out;
}

HitFeat Analysis::features (int start, int end) const
{
    HitFeat F;
    const int nFft = 2048;
    const int segEnd = std::min ({ end, start + (int) (0.4 * sr), n });
    std::vector<float> seg;
    for (int i = start; i < segEnd; ++i)
        seg.push_back (m[(size_t) i]);
    if ((int) seg.size() < nFft)
        seg.resize ((size_t) nFft, 0.0f);
    static thread_local std::vector<float> win;
    if ((int) win.size() != nFft)
        win = hanning (nFft);
    std::vector<double> spec ((size_t) nFft / 2 + 1, 0.0), pw ((size_t) nFft / 2 + 1);
    std::vector<double> fr ((size_t) nFft);
    for (int h : { 0, nFft / 4, nFft / 2 })
    {
        for (int i = 0; i < nFft; ++i)
        {
            const int j = h + i;
            fr[(size_t) i] = j < (int) seg.size() ? (double) (seg[(size_t) j] * win[(size_t) i]) : 0.0;
        }
        fft::rfftPower (fr.data(), nFft, pw.data());
        for (size_t k = 0; k < spec.size(); ++k)
            spec[k] += pw[k];
    }
    for (auto& v : spec)
        v /= 3.0;
    std::vector<double> freqs;
    auto edges = bandEdges (sr, nFft, freqs);
    std::vector<double> bands (24);
    for (int i = 0; i < 24; ++i)
    {
        const int a = edges[(size_t) i], b = std::max (edges[(size_t) i] + 1, edges[(size_t) i + 1]);
        double s = 0;
        for (int k = a; k < std::min (b, (int) spec.size()); ++k)
            s += spec[(size_t) k];
        bands[(size_t) i] = s;
    }
    double total = EPS, all = 0, wsum = 0, lo = 0, hi = 0, mid = 0;
    for (size_t k = 0; k < spec.size(); ++k)
    {
        const double f = freqs[k], s = spec[k];
        if (f > 20) total += s;
        all += s;
        wsum += f * s;
        if (f > 20 && f < 150) lo += s;
        if (f > 6000) hi += s;
        if (f >= 150 && f <= 6000) mid += s;
    }
    F.centroid = wsum / (all + EPS);
    F.low = lo / total;
    F.high = hi / total;
    F.mid = mid / total;
    F.flat = flatness (spec, freqs, 100.0, std::min (16000.0, sr / 2.0));

    const int H = HOP_ENV;
    const int ne = (int) env.size();
    const int a = start / H;
    const int b = std::max (a + 2, std::min (ne, end / H));
    std::vector<double> e;
    for (int i = a; i < std::min (b, ne); ++i)
        e.push_back (env[(size_t) i]);
    if (e.empty())
        e.push_back (0.0);
    const int p = (int) (std::max_element (e.begin(), e.end()) - e.begin());
    const double pk = e[(size_t) p] + EPS;
    int d20 = (int) e.size() - p;
    for (int i = p; i < (int) e.size(); ++i)
        if (e[(size_t) i] < pk * 0.1)
        {
            d20 = i - p;
            break;
        }
    F.decay = d20 * (double) H / sr;
    F.attack = p * (double) H / sr;

    // clap check: several bursts in the first 45 ms
    const int fineEnd = std::min (n, start + (int) (0.045 * sr));
    const int fl = std::max (0, fineEnd - start);
    if (fl > 20)
    {
        std::vector<float> fine ((size_t) fl);
        for (int i = 0; i < fl; ++i)
            fine[(size_t) i] = std::abs (m[(size_t) (start + i)]);
        const int k = std::max (1, (int) (0.001 * sr));
        auto sm = boxSame (fine.data(), fl, k);
        double mx = *std::max_element (sm.begin(), sm.end()) + EPS;
        const int sep = (int) (0.004 * sr);
        int last = -sep;
        for (int q = 0; q + 2 < (int) sm.size(); ++q)
        {
            const double c = sm[(size_t) q + 1];
            if (c > sm[(size_t) q] && c >= sm[(size_t) q + 2] && c > 0.45 * mx && q - last >= sep)
            {
                ++F.bursts;
                last = q;
            }
        }
    }
    // feature vector
    std::vector<double> logb (24);
    double mean = 0;
    for (int i = 0; i < 24; ++i)
    {
        logb[(size_t) i] = std::log10 (bands[(size_t) i] + EPS);
        mean += logb[(size_t) i];
    }
    mean /= 24.0;
    double nrm = 0;
    for (auto& v : logb)
    {
        v -= mean;
        nrm += v * v;
    }
    nrm = std::sqrt (nrm) + EPS;
    std::vector<double> edb (e.size());
    for (size_t i = 0; i < e.size(); ++i)
        edb[i] = dbOf (e[i] / pk) / 60.0;
    auto envPts = interpPoints (edb, 12);
    F.vec.reserve (37);
    for (double v : logb) F.vec.push_back ((float) (v / nrm * 3.0));
    for (double v : envPts) F.vec.push_back ((float) (v * 1.2));
    F.vec.push_back ((float) std::log10 (F.decay + 0.01));
    F.level = pk;
    return F;
}

EventFeat Analysis::eventFeatures (int start, int end) const
{
    EventFeat F;
    start = std::max (0, start);
    end = std::min (end, n);
    const int nFft = 2048, hop = 1024;
    std::vector<float> seg;
    for (int i = start; i < end; ++i)
        seg.push_back (m[(size_t) i]);
    if ((int) seg.size() < nFft)
        seg.resize ((size_t) nFft, 0.0f);
    std::vector<double> freqs;
    auto edges = bandEdges (sr, nFft, freqs);
    const int nb = nFft / 2 + 1;
    std::vector<std::vector<double>> lb;           // [frame][24]
    std::vector<double> centT, energy, spec ((size_t) nb, 0.0);
    int nFrames = 0;
    stftMag (seg.data(), (int) seg.size(), nFft, hop, [&] (int, const float* mag) {
        std::vector<double> bandsF (24);
        double tot = 0, w = 0;
        for (int k = 0; k < nb; ++k)
        {
            const double p = (double) mag[k] * (double) mag[k];
            tot += p;
            w += p * freqs[(size_t) k];
            spec[(size_t) k] += p;
        }
        for (int i = 0; i < 24; ++i)
        {
            const int a = edges[(size_t) i], b = std::max (edges[(size_t) i] + 1, edges[(size_t) i + 1]);
            double s = 0;
            for (int k = a; k < std::min (b, nb); ++k)
                s += (double) mag[k] * (double) mag[k];
            bandsF[(size_t) i] = std::log10 (s + 1e-10);
        }
        lb.push_back (bandsF);
        tot += EPS;
        centT.push_back (w / tot);
        energy.push_back (std::sqrt (tot));
        ++nFrames;
    });
    for (auto& v : spec)
        v /= std::max (1, nFrames);
    std::vector<double> meanShape (24, 0.0), sd (24, 0.0);
    for (auto& fr : lb)
        for (int i = 0; i < 24; ++i)
            meanShape[(size_t) i] += fr[(size_t) i];
    for (auto& v : meanShape)
        v /= std::max (1, nFrames);
    for (auto& fr : lb)
        for (int i = 0; i < 24; ++i)
        {
            const double d = fr[(size_t) i] - meanShape[(size_t) i];
            sd[(size_t) i] += d * d;
        }
    for (auto& v : sd)
        v = std::sqrt (v / std::max (1, nFrames));
    double ms = 0;
    for (double v : meanShape) ms += v;
    ms /= 24.0;
    double msn = 0;
    for (auto& v : meanShape)
    {
        v -= ms;
        msn += v * v;
    }
    msn = std::sqrt (msn) + EPS;
    const double emax = energy.empty() ? 0.0 : *std::max_element (energy.begin(), energy.end());
    std::vector<double> edb (energy.size());
    for (size_t i = 0; i < energy.size(); ++i)
        edb[i] = dbOf (energy[i] / (emax + EPS));
    auto envPts = interpPoints (edb, 16);
    F.flat = flatness (spec, freqs, 100.0, std::min (12000.0, sr / 2.0));
    double esum = 0;
    for (double v : energy) esum += v;
    std::vector<double> weight (energy.size());
    for (size_t i = 0; i < energy.size(); ++i)
        weight[i] = energy[i] / (esum + EPS);
    double cent = 0;
    for (size_t i = 0; i < centT.size(); ++i)
        cent += centT[i] * weight[i];
    F.centroid = cent;
    // np.array_split(arange(n), 3)
    {
        const int base = nFrames / 3, extra = nFrames % 3;
        int pos = 0;
        for (int t = 0; t < 3; ++t)
        {
            const int sz = base + (t < extra ? 1 : 0);
            double num = 0, den = 0;
            for (int i = pos; i < pos + sz; ++i)
            {
                num += centT[(size_t) i] * weight[(size_t) i];
                den += weight[(size_t) i];
            }
            F.centParts[t] = num / (den + EPS);
            pos += sz;
        }
    }
    F.dur = (end - start) / (double) sr;
    int ip = 0;
    for (int i = 1; i < (int) energy.size(); ++i)
        if (energy[(size_t) i] > energy[(size_t) ip])
            ip = i;
    F.peakPos = ip / (double) std::max (1, (int) energy.size() - 1);
    const int H = HOP_ENV;
    const int ne = (int) env.size();
    const int a = start / H;
    const int b = std::max (a + 2, end / H);
    int ia = a;
    for (int i = a; i < std::min (b, ne); ++i)
        if (env[(size_t) i] > env[(size_t) ia])
            ia = i;
    F.attack = (ia - a) * (double) H / sr;
    F.pitch = end > start ? pitchStrength (m.data() + start, end - start, sr) : 0.0;
    // polyphony estimate: prominent spectral peaks between 80 Hz and 2 kHz
    std::vector<double> s;
    for (int k = 0; k < nb; ++k)
        if (freqs[(size_t) k] > 80 && freqs[(size_t) k] < 2000)
            s.push_back (spec[(size_t) k]);
    if (s.size() > 5)
    {
        std::vector<double> sdb (s.size());
        double mx = -1e300;
        for (size_t i = 0; i < s.size(); ++i)
        {
            sdb[i] = 10.0 * std::log10 (s[i] + EPS);
            mx = std::max (mx, sdb[i]);
        }
        for (size_t i = 1; i + 1 < s.size(); ++i)
            if (sdb[i] > sdb[i - 1] && sdb[i] > sdb[i + 1] && sdb[i] > mx - 24)
                ++F.peaks;
    }
    F.vec.reserve (65);
    for (double v : meanShape) F.vec.push_back ((float) (v / msn * 3.0));
    for (double v : sd) F.vec.push_back ((float) (v * 0.6));
    for (double v : envPts) F.vec.push_back ((float) (v / 60.0));
    F.vec.push_back ((float) (std::log2 (F.dur + 0.05) * 0.8));
    double lv = 0;
    for (int i = start; i < end; ++i)
        lv = std::max (lv, (double) std::abs (m[(size_t) i]));
    F.level = lv;
    return F;
}

double pitchStrength (const float* x, int len, int sr)
{
    if (len < (int) (0.05 * sr))
        return 0.0;
    const int n = (int) (0.04 * sr);
    const int num = std::min (8, std::max (1, len / n));
    int lo = (int) (sr / 900.0), hi = (int) (sr / 70.0);
    std::vector<double> vals;
    std::vector<double> fr ((size_t) n);
    for (int q = 0; q < num; ++q)
    {
        const double pos = num > 1 ? (double) (len - n) * q / (num - 1) : 0.0;
        const int s = (int) pos;
        double mean = 0;
        for (int i = 0; i < n; ++i)
        {
            fr[(size_t) i] = x[s + i];
            mean += fr[(size_t) i];
        }
        mean /= n;
        double e = 0;
        for (auto& v : fr)
        {
            v -= mean;
            e += v * v;
        }
        if (e < 1e-9)
            continue;
        auto ac = fft::autocorr (fr.data(), n);
        const double a0 = ac[0] + EPS;
        if (hi >= (int) ac.size())
            hi = (int) ac.size() - 1;
        double best = 0;
        if (hi > lo)
        {
            best = -1e300;
            for (int i = lo; i < hi; ++i)
                best = std::max (best, ac[(size_t) i] / a0);
        }
        vals.push_back (best);
    }
    return vals.empty() ? 0.0 : median (vals);
}

static double rmsDist (const Vec& a, const Vec& b)
{
    double s = 0;
    const size_t n = std::min (a.size(), b.size());
    for (size_t i = 0; i < n; ++i)
    {
        const double d = (double) a[i] - (double) b[i];
        s += d * d;
    }
    return std::sqrt (s / (double) std::max<size_t> (1, n));
}

std::vector<int> farthestPick (const std::vector<Vec>& vecs, const std::vector<int>& order, int k, double minDist)
{
    if (order.empty())
        return {};
    const int c = (int) order.size();
    if (c == 1)
        return { order[0] };
    std::vector<double> D ((size_t) c * c, 0.0);
    double dsum = 0;
    for (int i = 0; i < c; ++i)
        for (int j = 0; j < c; ++j)
        {
            const double d = i == j ? 0.0 : rmsDist (vecs[(size_t) order[(size_t) i]], vecs[(size_t) order[(size_t) j]]);
            D[(size_t) (i * c + j)] = d;
            dsum += d;
        }
    const double dmean = dsum / ((double) c * c);
    int first = 0;
    double bestv = 1e300;
    for (int i = 0; i < c; ++i)
    {
        double rm = 0;
        for (int j = 0; j < c; ++j)
            rm += D[(size_t) (i * c + j)];
        rm /= c;
        const double bonus = (c > 1 ? 0.15 * i / (c - 1) : 0.0) * (dmean + EPS);
        if (rm + bonus < bestv)
        {
            bestv = rm + bonus;
            first = i;
        }
    }
    std::vector<int> chosen { first };
    while ((int) chosen.size() < k)
    {
        int j = -1;
        double bestd = -2;
        for (int i = 0; i < c; ++i)
        {
            double md = 1e300;
            bool isChosen = false;
            for (int q : chosen)
            {
                md = std::min (md, D[(size_t) (i * c + q)]);
                if (q == i) isChosen = true;
            }
            if (isChosen) md = -1;
            if (md > bestd)
            {
                bestd = md;
                j = i;
            }
        }
        if (j < 0 || bestd < minDist)
            break;
        chosen.push_back (j);
    }
    std::vector<int> out;
    for (int i : chosen)
        out.push_back (order[(size_t) i]);
    return out;
}

std::vector<std::vector<int>> groupItems (const std::vector<Vec>& vecs, const std::vector<int>& order, double threshold)
{
    std::vector<std::vector<int>> groups;
    std::vector<int> centers;
    for (int i : order)
    {
        int best = -1;
        double bd = 1e9;
        for (size_t g = 0; g < centers.size(); ++g)
        {
            const double d = rmsDist (vecs[(size_t) i], vecs[(size_t) centers[g]]);
            if (d < bd)
            {
                bd = d;
                best = (int) g;
            }
        }
        if (best >= 0 && bd < threshold)
            groups[(size_t) best].push_back (i);
        else
        {
            groups.push_back ({ i });
            centers.push_back (i);
        }
    }
    return groups;
}

} // namespace xk
