#include "PluginProcessor.h"

#include "PluginEditor.h"

XenakisProcessor::XenakisProcessor()
    : AudioProcessor (BusesProperties()
                          .withInput ("Input", juce::AudioChannelSet::stereo(), true)
                          .withOutput ("Output", juce::AudioChannelSet::stereo(), true))
{
    addParameter (previewLevel = new juce::AudioParameterFloat (
                      juce::ParameterID { "preview_level", 1 }, "Preview level",
                      juce::NormalisableRange<float> (0.0f, 1.0f), 1.0f,
                      juce::AudioParameterFloatAttributes()
                          .withStringFromValueFunction ([] (float v, int) { return juce::String (juce::roundToInt (v * 100)) + "%"; })
                          .withValueFromStringFunction ([] (const juce::String& t) {
                              return juce::jlimit (0.0f, 1.0f, t.retainCharacters ("0123456789.").getFloatValue() / 100.0f);
                          })));
}

void XenakisProcessor::prepareToPlay (double sampleRate, int)
{
    player.prepare (sampleRate);
}

bool XenakisProcessor::isBusesLayoutSupported (const BusesLayout& layouts) const
{
    const auto out = layouts.getMainOutputChannelSet();
    if (out != juce::AudioChannelSet::mono() && out != juce::AudioChannelSet::stereo())
        return false;
    const auto in = layouts.getMainInputChannelSet();
    return in.isDisabled() || in == out;
}

void XenakisProcessor::processBlock (juce::AudioBuffer<float>& buffer, juce::MidiBuffer&)
{
    juce::ScopedNoDenormals noDenormals;
    const int n = buffer.getNumSamples();
    for (int c = getTotalNumInputChannels(); c < getTotalNumOutputChannels(); ++c)
        buffer.clear (c, 0, n);
    // the standalone build has no track to pass through (and would echo the microphone)
    if (wrapperType == wrapperType_Standalone)
        buffer.clear();
    player.render (buffer, n, previewLevel->get());
}

juce::AudioProcessorEditor* XenakisProcessor::createEditor()
{
    return new XenakisEditor (*this);
}

void XenakisProcessor::getStateInformation (juce::MemoryBlock& destData)
{
    // Stage 1 keeps the song details with the project; the full session comes in stage 3.
    juce::ValueTree st ("Xenakis");
    st.setProperty ("version", 1, nullptr);
    st.setProperty ("preview_level", (double) previewLevel->get(), nullptr);
    st.setProperty ("artist", session.artist, nullptr);
    st.setProperty ("song", session.song, nullptr);
    if (session.prefixEdited)
        st.setProperty ("prefix", session.prefix, nullptr);
    juce::MemoryOutputStream mo (destData, false);
    st.writeToStream (mo);
}

void XenakisProcessor::setStateInformation (const void* data, int sizeInBytes)
{
    auto st = juce::ValueTree::readFromData (data, (size_t) sizeInBytes);
    if (! st.hasType ("Xenakis"))
        return;
    if (st.hasProperty ("preview_level"))
    {
        const float v = juce::jlimit (0.0f, 1.0f, (float) (double) st["preview_level"]);
        if (std::abs (v - previewLevel->get()) > 1e-6f)
        {
            *previewLevel = v;
            // tell the host the parameter values changed (CLAP hosts re-read them)
            updateHostDisplay (ChangeDetails().withProgramChanged (true));
        }
    }
    juce::WeakReference<xk::Session> weak (&session);
    juce::MessageManager::callAsync ([weak, st]() {
        if (auto* s = weak.get())
        {
            s->setSong (st["artist"].toString(), st["song"].toString());
            if (st.hasProperty ("prefix"))
                s->setPrefix (st["prefix"].toString());
        }
    });
}

juce::AudioProcessor* JUCE_CALLTYPE createPluginFilter()
{
    return new XenakisProcessor();
}
