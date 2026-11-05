// Tempo and bar-grid detection (mirrors core/tempo.py).
#pragma once

#include "engine/Dsp.h"

#include <memory>

namespace xk::tempo
{
// nullptr when there is no steady pulse
std::shared_ptr<TempoEst> estimate (const Analysis& an);
bool fits (double bpmA, double bpmB);
}
