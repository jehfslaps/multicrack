// Plays the chop being auditioned through the plug-in's own output (mixed on top of whatever
// the track is playing). Buffers are prepared on the message thread; the audio thread only
// copies samples and never allocates or blocks.
#pragma once

#include <juce_audio_basics/juce_audio_basics.h>

#include <atomic>
#include <memory>
#include <vector>

namespace xk
{

class PreviewPlayer
{
public:
    void prepare (double hostSampleRate);
    // message thread: audio is [channel][frame] at srcRate
    void play (const std::vector<std::vector<float>>& audio, int srcRate, int ident, bool loop);
    void stop();
    // audio thread: adds the preview into out
    void render (juce::AudioBuffer<float>& out, int numSamples, float gain = 1.0f) noexcept;

    int playingId() const noexcept { return active.load() ? ident.load() : -1; }
    // 0..1 through the chop, or -1 when idle
    double position() const noexcept;
    bool isLooping() const noexcept { return looping.load(); }

private:
    struct Buf
    {
        juce::AudioBuffer<float> data;
        bool loop = false;
    };
    juce::SpinLock lock;
    std::unique_ptr<Buf> current;          // read by the audio thread under `lock`
    std::atomic<long long> pos { 0 };
    std::atomic<long long> length { 0 };
    std::atomic<int> ident { -1 };
    std::atomic<bool> active { false }, looping { false };
    std::atomic<double> hostRate { 44100.0 };
};

} // namespace xk
