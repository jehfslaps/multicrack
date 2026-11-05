// File, folder and stem naming (mirrors core/naming.py and core/songs.py).
#pragma once

#include "engine/Model.h"

#include <map>
#include <string>
#include <utility>
#include <vector>

namespace xk::naming
{
std::string makePrefix (const std::string& artist, const std::string& song);
std::string folderName (const std::string& artist, const std::string& song);
std::string labelToken (const std::string& label);
std::string chopKey (const std::string& label, int bars, bool reverse);
// highest number already used per key in a folder (list of file names in it)
std::map<std::string, int> existingCounts (const std::vector<std::string>& filesInFolder, const std::string& prefix);
// chop id -> file name; numbering continues after `existing`
std::map<int, std::string> assignNames (const std::vector<Chop>& chops, const std::string& prefix,
                                        std::map<std::string, int> existing);

std::string baseName (const std::string& path);   // file name without folders
std::string stemOf (const std::string& path);     // file name without extension
std::vector<std::string> splitTokens (const std::string& name);
std::string cleanStemName (const std::string& name);
// ("base", 'L' | 'R') for split-mono files; second == 0 when not a split file
std::pair<std::string, char> channelSide (const std::string& name);
// 'Taylor Swift - Style (Stems)' -> ('Taylor Swift', 'Style')
std::pair<std::string, std::string> guessNames (const std::string& folderName);
std::string lower (std::string s);
}
