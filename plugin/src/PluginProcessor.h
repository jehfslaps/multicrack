// The plug-in: passes the track's audio through untouched and adds the chop being auditioned.
#pragma once

#include "PreviewPlayer.h"
#include "Session.h"

#include <juce_audio_processors/juce_audio_processors.h>

class XenakisProcessor : public juce::AudioProcessor
{
public:
    XenakisProcessor();
    ~XenakisProcessor() override = default;

    void prepareToPlay (double sampleRate, int samplesPerBlock) override;
    void releaseResources() override {}
    bool isBusesLayoutSupported (const BusesLayout& layouts) const override;
    void processBlock (juce::AudioBuffer<float>&, juce::MidiBuffer&) override;
    using AudioProcessor::processBlock;

    juce::AudioProcessorEditor* createEditor() override;
    bool hasEditor() const override { return true; }

    const juce::String getName() const override { return "Xenakis"; }
    bool acceptsMidi() const override { return false; }
    bool producesMidi() const override { return false; }
    bool isMidiEffect() const override { return false; }
    double getTailLengthSeconds() const override { return 0.0; }

    int getNumPrograms() override { return 1; }
    int getCurrentProgram() override { return 0; }
    void setCurrentProgram (int) override {}
    const juce::String getProgramName (int) override { return {}; }
    void changeProgramName (int, const juce::String&) override {}

    void getStateInformation (juce::MemoryBlock& destData) override;
    void setStateInformation (const void* data, int sizeInBytes) override;

    xk::PreviewPlayer player;
    xk::Session session { player };
    juce::AudioParameterFloat* previewLevel = nullptr;   // how loud auditioned chops play

private:
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (XenakisProcessor)
};
