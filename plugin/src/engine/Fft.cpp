#include "engine/Fft.h"

#include <cmath>
#include <map>
#include <memory>

namespace
{
constexpr double kPi = 3.14159265358979323846;

// Precomputed tables for one FFT size (bit-reversal order and twiddles).
struct Plan
{
    int n = 0;
    std::vector<int> rev;
    std::vector<std::complex<double>> tw;      // exp(-2 pi i k / n), k < n/2
    std::vector<std::complex<double>> realTw;  // exp(-2 pi i k / (2n)), k <= n  (for real FFT of size 2n)

    explicit Plan (int size) : n (size)
    {
        rev.resize ((size_t) n);
        int bits = 0;
        while ((1 << bits) < n) ++bits;
        for (int i = 0; i < n; ++i)
        {
            int r = 0;
            for (int b = 0; b < bits; ++b)
                if (i & (1 << b)) r |= 1 << (bits - 1 - b);
            rev[(size_t) i] = r;
        }
        tw.resize ((size_t) std::max (1, n / 2));
        for (int k = 0; k < n / 2; ++k)
            tw[(size_t) k] = std::polar (1.0, -2.0 * kPi * k / n);
        realTw.resize ((size_t) n + 1);
        for (int k = 0; k <= n; ++k)
            realTw[(size_t) k] = std::polar (1.0, -2.0 * kPi * k / (2.0 * n));
    }
};

const Plan& plan (int n)
{
    thread_local std::map<int, std::unique_ptr<Plan>> cache;
    auto& p = cache[n];
    if (! p)
        p = std::make_unique<Plan> (n);
    return *p;
}

void run (std::complex<double>* a, const Plan& P, bool inverse)
{
    const int n = P.n;
    for (int i = 0; i < n; ++i)
    {
        const int j = P.rev[(size_t) i];
        if (i < j)
            std::swap (a[i], a[j]);
    }
    for (int len = 2; len <= n; len <<= 1)
    {
        const int half = len >> 1;
        const int step = n / len;
        for (int i = 0; i < n; i += len)
            for (int k = 0; k < half; ++k)
            {
                auto w = P.tw[(size_t) (k * step)];
                if (inverse) w = std::conj (w);
                const auto u = a[i + k];
                const auto v = a[i + k + half] * w;
                a[i + k] = u + v;
                a[i + k + half] = u - v;
            }
    }
    if (inverse)
        for (int i = 0; i < n; ++i)
            a[i] /= (double) n;
}

// Real FFT of length n via one complex FFT of length n/2. out gets n/2 + 1 bins.
template <typename T> void realForward (const T* x, int n, std::complex<double>* out)
{
    const int h = n / 2;
    thread_local std::vector<std::complex<double>> z;
    z.resize ((size_t) h);
    for (int i = 0; i < h; ++i)
        z[(size_t) i] = { (double) x[2 * i], (double) x[2 * i + 1] };
    const Plan& P = plan (h);
    run (z.data(), P, false);
    for (int k = 0; k <= h; ++k)
    {
        const auto zk = z[(size_t) (k % h)];
        const auto zc = std::conj (z[(size_t) ((h - k) % h)]);
        const auto even = (zk + zc) * 0.5;
        const auto odd = (zk - zc) * std::complex<double> (0, -0.5);
        out[k] = even + P.realTw[(size_t) k] * odd;
    }
}
} // namespace

namespace xk::fft
{

int nextPow2 (int n)
{
    int p = 1;
    while (p < n)
        p <<= 1;
    return p;
}

void transform (std::vector<std::complex<double>>& a, bool inverse)
{
    run (a.data(), plan ((int) a.size()), inverse);
}

void rfftMag (const float* x, int n, float* out)
{
    thread_local std::vector<std::complex<double>> s;
    s.resize ((size_t) n / 2 + 1);
    realForward (x, n, s.data());
    for (int k = 0; k <= n / 2; ++k)
        out[k] = (float) std::abs (s[(size_t) k]);
}

void rfftPower (const double* x, int n, double* out)
{
    thread_local std::vector<std::complex<double>> s;
    s.resize ((size_t) n / 2 + 1);
    realForward (x, n, s.data());
    for (int k = 0; k <= n / 2; ++k)
        out[k] = std::norm (s[(size_t) k]);
}

std::vector<double> autocorr (const double* x, int n)
{
    const int m = nextPow2 (2 * n);
    std::vector<std::complex<double>> a ((size_t) m);
    for (int i = 0; i < n; ++i)
        a[(size_t) i] = x[i];
    transform (a, false);
    for (auto& v : a)
        v = std::norm (v);
    transform (a, true);
    std::vector<double> ac ((size_t) n);
    for (int i = 0; i < n; ++i)
        ac[(size_t) i] = a[(size_t) i].real();
    return ac;
}

} // namespace xk::fft
