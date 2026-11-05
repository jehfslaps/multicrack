// The three chopping engines: one-shots, grooves (loops + hits + rolls) and events.
#pragma once

#include "engine/Dsp.h"

#include <vector>

namespace xk::engines
{
Analysis& getAnalysis (Stem& stem);
const std::vector<int>& getOnsets (Stem& stem);
double reattackDb (const Analysis& an, int o);

std::vector<Chop> oneshotEngine (Stem& stem);
std::vector<Chop> grooveEngine (Stem& stem);
std::vector<Chop> eventsEngine (Stem& stem, double bpm);
}
