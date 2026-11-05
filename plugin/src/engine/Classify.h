// Working out what a stem is and what each sound in it is (mirrors core/classify.py).
#pragma once

#include "engine/Dsp.h"

#include <map>
#include <string>
#include <vector>

namespace xk::classify
{
std::vector<std::string> kindsFromName (const std::string& name);
std::string kindFromAudio (const Analysis& an, const std::vector<int>& onsets,
                           const std::vector<std::pair<std::string, int>>& labelCounts, double tempoConf,
                           double activeFrac, double pitch, double centroid);
std::string drumLabel (const HitFeat& f, const std::string& context);
std::string loopLabel (const std::vector<std::string>& hitLabels, const std::string& context, double centroid);
std::string fxLabel (const EventFeat& f);
std::string vocalLabel (const EventFeat& f, bool fxHint);
std::string melodicLabel (const EventFeat& f, const std::string& context);
double summarizeSpectrum (const Analysis& an);
}
