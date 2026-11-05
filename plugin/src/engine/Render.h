// Rendering chops and writing clean WAVs (mirrors render_chop / write_wav24 in core/audio.py).
#pragma once

#include "engine/Model.h"

#include <string>
#include <utility>
#include <vector>

namespace xk::render
{
constexpr double PEAK_DB = -0.1;

std::pair<double, double> defaultFadesMs (const Chop& chop);
// Slice, (reverse), de-click / fade, smooth loop seam, peak-normalize and apply gain.
// Returns [channel][frame]. Preview and export use exactly this.
std::vector<std::vector<float>> renderChop (const Stem& stem, const Chop& chop);
// Plain 24-bit PCM WAV: only the 'fmt ' and 'data' chunks, no tempo or other tags.
bool writeWav24 (const std::string& path, const std::vector<std::vector<float>>& x, int sr);
std::vector<char> wav24Bytes (const std::vector<std::vector<float>>& x, int sr);
}
