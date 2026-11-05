#include "PreviewPlayer.h"

namespace xk
{

void PreviewPlayer::prepare (double sr)
{
    if (sr > 0)
        hostRate.store (sr);
}

void PreviewPlayer::play (const std::vector<std::vector<float>>& audio, int srcRate, int id, bool loop)
{
    auto buf = std::make_unique<Buf>();
    const int ch = juce::jlimit (1, 2, (int) audio.size());
    const int n = audio.empty() ? 0 : (int) audio[0].size();
    const double out = hostRate.load();
    const double ratio = srcRate / out;              // source samples per output sample
    const int outLen = juce::jmax (1, (int) std::ceil (n / ratio));
    buf->data.setSize (2, outLen);
    buf->data.clear();
    buf->loop = loop;
    for (int c = 0; c < 2; ++c)
    {
        const auto& src = audio[(size_t) juce::jmin (c, ch - 1)];
        if (std::abs (ratio - 1.0) < 1e-9)
            std::copy (src.begin(), src.end(), buf->data.getWritePointer (c));
        else
        {
            juce::LagrangeInterpolator interp;
            std::vector<float> padded (src.begin(), src.end());
            padded.resize (padded.size() + 8, 0.0f);   // tail room for the interpolator
            interp.process (ratio, padded.data(), buf->data.getWritePointer (c), outLen);
        }
    }
    std::unique_ptr<Buf> old;
    {
        const juce::SpinLock::ScopedLockType sl (lock);
        old = std::move (current);
        current = std::move (buf);
        pos.store (0);
        length.store (outLen);
        ident.store (id);
        looping.store (loop);
        active.store (true);
    }
    // `old` is freed here, on the message thread
}

void PreviewPlayer::stop()
{
    std::unique_ptr<Buf> old;
    {
        const juce::SpinLock::ScopedLockType sl (lock);
        old = std::move (current);
        active.store (false);
        ident.store (-1);
        pos.store (0);
    }
}

void PreviewPlayer::render (juce::AudioBuffer<float>& out, int numSamples, float gain) noexcept
{
    if (! active.load())
        return;
    const juce::SpinLock::ScopedTryLockType sl (lock);
    if (! sl.isLocked() || current == nullptr)
        return;
    auto& d = current->data;
    const long long len = d.getNumSamples();
    long long p = pos.load();
    const int outCh = out.getNumChannels();
    int done = 0;
    while (done < numSamples)
    {
        if (p >= len)
        {
            if (current->loop && len > 0)
                p = 0;
            else
            {
                active.store (false);
                break;
            }
        }
        const int n = (int) juce::jmin<long long> (numSamples - done, len - p);
        for (int c = 0; c < outCh; ++c)
            out.addFrom (c, done, d, juce::jmin (c, 1), (int) p, n, gain);
        p += n;
        done += n;
    }
    pos.store (p);
}

double PreviewPlayer::position() const noexcept
{
    if (! active.load())
        return -1.0;
    const auto len = length.load();
    return len > 0 ? juce::jlimit (0.0, 1.0, pos.load() / (double) len) : -1.0;
}

} // namespace xk
