// High-level steps: detect stem types, lock the song tempo, chop (mirrors core/pipeline.py).
#pragma once

#include "engine/Model.h"

#include <functional>
#include <optional>
#include <vector>

namespace xk::pipeline
{
bool isDrumKind (const std::string& kind);
std::string detectKind (Stem& stem);
std::optional<Song> lockTempo (std::vector<StemPtr>& stems);
void applyGrid (Stem& stem, const std::optional<Song>& song);
std::vector<Chop> chopStem (Stem& stem, const std::optional<Song>& song);

using Progress = std::function<void (const std::string& msg, int i, int n)>;
// chops every stem in auto mode; returns the chops and the song grid
std::vector<Chop> process (std::vector<StemPtr>& stems, std::optional<Song>& song, Progress progress = {},
                           const std::function<bool()>& cancelled = {});
}
