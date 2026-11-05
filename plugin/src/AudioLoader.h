// Reading stems with JUCE, joining split L/R files (mirrors load_stems in core/audio.py).
#pragma once

#include "engine/Model.h"

#include <juce_audio_formats/juce_audio_formats.h>

#include <functional>
#include <vector>

namespace xk
{
bool isAudioFile (const juce::File& f);
// files and folders (recursively) -> audio files sorted by name
juce::Array<juce::File> expandPaths (const juce::StringArray& paths);
// a drop that is one folder with several song folders inside -> those folders (else empty)
juce::Array<juce::File> splitSongs (const juce::StringArray& paths);

using LoadProgress = std::function<void (const juce::String& msg, int i, int n)>;
std::vector<StemPtr> loadStems (const juce::StringArray& paths, juce::AudioFormatManager& formats,
                                LoadProgress progress = {});
}
