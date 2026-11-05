// Small FFT helpers (radix-2) used by the analysis code.
#pragma once

#include <complex>
#include <vector>

namespace xk::fft
{

// In-place complex FFT; n must be a power of two.
void transform (std::vector<std::complex<double>>& a, bool inverse);

int nextPow2 (int n);

// |rfft(x)| for a frame of length n (power of two). out gets n/2 + 1 values.
void rfftMag (const float* x, int n, float* out);

// |rfft(x)|^2 (power), double precision.
void rfftPower (const double* x, int n, double* out);

// Linear autocorrelation ac[0..n-1] of x (same as irfft(|rfft(x, 2n)|^2)[:n]).
std::vector<double> autocorr (const double* x, int n);

} // namespace xk::fft
