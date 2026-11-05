// Signal analysis: envelopes, onsets, tails and per-sound features (mirrors core/dsp.py).
#pragma once

#include "engine/Model.h"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <utility>
#include <vector>

namespace xk
{

constexpr double EPS = 1e-12;
constexpr double PI = 3.14159265358979323846;

// --- numpy-style helpers
double percentile (std::vector<float> v, double q);       // linear interpolation (numpy default)
double percentileD (std::vector<double> v, double q);
double median (std::vector<double> v);
Vec frameRms (const Vec& m, int hop, int win);
Vec movingMean (const Vec& x, int w);
std::vector<double> boxSame (const float* x, int n, int k); // np.convolve(x, ones(k)/k, "same")
std::vector<float> hanning (int n);
std::vector<int> bandEdges (int sr, int nFft, std::vector<double>& freqs, int nBands = 24,
                            double lo = 30.0, double hi = 16000.0);
std::vector<double> rfftFreqs (int nFft, int sr);
inline double dbOf (double x) { double a = x < 0 ? -x : x; return 20.0 * std::log10 (a > EPS ? a : EPS); }

// Magnitude STFT, frame k centred on sample k*hop (same padding as stft_mag_chunks).
// Calls fn(frameIndex, mags[nFft/2+1]).
template <typename Fn> void stftMag (const float* m, int n, int nFft, int hop, Fn&& fn);

struct HitFeat
{
    double centroid = 0, low = 0, high = 0, mid = 0, flat = 0, decay = 0, attack = 0;
    int bursts = 0;
    double level = 0;
    Vec vec;
};

struct EventFeat
{
    double centroid = 0;
    double centParts[3] { 0, 0, 0 };
    double flat = 0, dur = 0, peakPos = 0, attack = 0, pitch = 0;
    int peaks = 0;
    double level = 0;
    Vec vec;
};

struct Analysis
{
    static constexpr int HOP_ENV = 64;     // fine amplitude envelope
    static constexpr int HOP_ONSET = 256;  // onset-strength frames

    Analysis (Vec mono, int sampleRate);

    Vec m;
    int sr = 44100;
    int n = 0;
    Vec env;
    double peak = 0, floor = 0;
    Vec flux, fluxLow, fluxHigh;
    double fps = 0;

    std::vector<int> onsets (double sensitivity = 1.0, double minGap = 0.035) const;
    int refineStart (int approx) const;
    int peakIndex (int start, int end) const;
    std::pair<int, bool> tailEnd (int start, int limit, double relDb = -50.0, double hold = 0.025,
                                  double maxLen = 0.0) const;
    std::vector<char> activeMask (int hop, double relDb = -45.0) const;
    HitFeat features (int start, int end) const;
    EventFeat eventFeatures (int start, int end) const;

    float envAt (int i) const { return env[(size_t) std::max (0, std::min ((int) env.size() - 1, i))]; }

private:
    void onsetStrength();
};

double pitchStrength (const float* x, int n, int sr);

// Pick up to k items: first the most typical, then the most different ones.
std::vector<int> farthestPick (const std::vector<Vec>& vecs, const std::vector<int>& order, int k,
                               double minDist);
// Greedy grouping of similar sounds (order = importance).
std::vector<std::vector<int>> groupItems (const std::vector<Vec>& vecs, const std::vector<int>& order,
                                          double threshold);

} // namespace xk

#include "engine/Fft.h"
#include <cmath>

namespace xk
{
template <typename Fn> void stftMag (const float* m, int n, int nFft, int hop, Fn&& fn)
{
    static thread_local std::vector<float> win;
    if ((int) win.size() != nFft)
        win = hanning (nFft);
    const int half = nFft / 2;
    const int nFrames = 1 + n / hop;
    std::vector<float> fr ((size_t) nFft), mag ((size_t) nFft / 2 + 1);
    for (int k = 0; k < nFrames; ++k)
    {
        const int s = k * hop - half;     // index into m of the frame's first sample
        for (int i = 0; i < nFft; ++i)
        {
            const int j = s + i;
            fr[(size_t) i] = (j >= 0 && j < n) ? m[j] * win[(size_t) i] : 0.0f;
        }
        fft::rfftMag (fr.data(), nFft, mag.data());
        fn (k, mag.data());
    }
}
} // namespace xk
