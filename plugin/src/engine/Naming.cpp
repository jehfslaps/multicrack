#include "engine/Naming.h"

#include <algorithm>
#include <cctype>
#include <cstdio>
#include <regex>

namespace xk::naming
{

std::string lower (std::string s)
{
    for (auto& c : s)
        c = (char) std::tolower ((unsigned char) c);
    return s;
}

static std::vector<std::string> cleanWords (const std::string& text)
{
    std::vector<std::string> out;
    std::string cur;
    for (unsigned char c : text)
    {
        if (std::isalnum (c) && c < 128)
            cur.push_back ((char) c);
        else if (! cur.empty())
        {
            out.push_back (cur);
            cur.clear();
        }
    }
    if (! cur.empty())
        out.push_back (cur);
    return out;
}

static std::string capFirst (const std::string& w)
{
    if (w.empty())
        return w;
    std::string r = w;
    r[0] = (char) std::toupper ((unsigned char) r[0]);
    return r;
}

std::string makePrefix (const std::string& artist, const std::string& song)
{
    std::string initials;
    for (auto& w : cleanWords (artist))
        initials.push_back ((char) std::toupper ((unsigned char) w[0]));
    std::string songPart;
    for (auto& w : cleanWords (song))
        songPart += capFirst (w);
    if (songPart.size() > 28)
        songPart.resize (28);
    std::vector<std::string> parts;
    if (! initials.empty()) parts.push_back (initials);
    if (! songPart.empty()) parts.push_back (songPart);
    if (parts.empty())
        return "";
    std::string r;
    for (size_t i = 0; i < parts.size(); ++i)
        r += (i ? "_" : "") + parts[i];
    return r + "_";
}

static std::string stripInvalid (const std::string& s)
{
    std::string r;
    for (unsigned char c : s)
        if (! (c < 0x20 || std::string ("<>:\"/\\|?*").find ((char) c) != std::string::npos))
            r.push_back ((char) c);
    return r;
}

static std::string trim (const std::string& s, const char* chars = " \t\r\n")
{
    const auto a = s.find_first_not_of (chars);
    if (a == std::string::npos)
        return "";
    const auto b = s.find_last_not_of (chars);
    return s.substr (a, b - a + 1);
}

std::string folderName (const std::string& artist, const std::string& song)
{
    const std::string a = stripInvalid (trim (artist)), s = stripInvalid (trim (song));
    std::string base;
    if (! a.empty() && ! s.empty()) base = a + " - " + s;
    else base = ! a.empty() ? a : (! s.empty() ? s : "Untitled");
    std::string r = base + " (Chopped)";
    while (! r.empty() && (r.back() == '.' || r.back() == ' '))
        r.pop_back();
    return r;
}

std::string labelToken (const std::string& label)
{
    static const std::map<std::string, std::string> overrides {
        { "Vocal Shout", "VoxShout" }, { "Vocal Chop", "VoxChop" }, { "Vocal FX", "VoxFX" },
        { "Vocal Phrase", "VoxPhrase" }, { "Guitar Chord", "GtrChord" }, { "Guitar Lead", "GtrLead" },
        { "Guitar Stab", "GtrStab" },
    };
    auto it = overrides.find (label);
    if (it != overrides.end())
        return it->second;
    std::string r;
    for (auto& w : cleanWords (label))
        r += capFirst (w);
    return r.empty() ? "Sample" : r;
}

std::string chopKey (const std::string& label, int bars, bool reverse)
{
    std::string tok = labelToken (label);
    if (reverse)
        tok += "Rev";
    if (isLoopedLabel (label) && bars > 0)
        tok += "_" + std::to_string (bars) + "bar";
    return tok;
}

std::map<std::string, int> existingCounts (const std::vector<std::string>& files, const std::string& prefix)
{
    std::map<std::string, int> counts;
    const std::string lp = lower (prefix);
    for (auto& f : files)
    {
        const std::string lf = lower (f);
        if (lf.size() <= lp.size() + 4 || lf.compare (0, lp.size(), lp) != 0)
            continue;
        if (lf.substr (lf.size() - 4) != ".wav")
            continue;
        const std::string mid = f.substr (prefix.size(), f.size() - prefix.size() - 4);
        // (.+)_(\d+)
        const auto us = mid.find_last_of ('_');
        if (us == std::string::npos || us == 0 || us + 1 >= mid.size())
            continue;
        const std::string num = mid.substr (us + 1);
        if (! std::all_of (num.begin(), num.end(), [] (unsigned char c) { return std::isdigit (c); }))
            continue;
        const std::string key = mid.substr (0, us);
        counts[key] = std::max (counts[key], std::stoi (num));
    }
    return counts;
}

std::map<int, std::string> assignNames (const std::vector<Chop>& chops, const std::string& prefix,
                                        std::map<std::string, int> counts)
{
    std::map<int, std::string> names;
    for (auto& c : chops)
    {
        const std::string k = chopKey (c.label, c.bars, c.reverse);
        const int n = ++counts[k];
        char buf[16];
        std::snprintf (buf, sizeof (buf), "%02d", n);
        names[c.id] = prefix + k + "_" + buf + ".wav";
    }
    return names;
}

std::string baseName (const std::string& path)
{
    const auto p = path.find_last_of ("/\\");
    return p == std::string::npos ? path : path.substr (p + 1);
}

std::string stemOf (const std::string& path)
{
    const std::string b = baseName (path);
    const auto d = b.find_last_of ('.');
    return d == std::string::npos || d == 0 ? b : b.substr (0, d);
}

std::vector<std::string> splitTokens (const std::string& name)
{
    const std::string base = stemOf (name);
    static const std::regex sep ("[^0-9A-Za-z#]+");
    static const std::regex tok ("[A-Z]+(?![a-z])|[A-Z]?[a-z#]+|\\d+");
    std::vector<std::string> out;
    std::sregex_token_iterator it (base.begin(), base.end(), sep, -1), end;
    for (; it != end; ++it)
    {
        const std::string r = *it;
        if (r.empty())
            continue;
        for (std::sregex_iterator m (r.begin(), r.end(), tok), me; m != me; ++m)
            if (! m->str().empty())
                out.push_back (m->str());
    }
    return out;
}

std::string cleanStemName (const std::string& name)
{
    const std::string base = stemOf (name);
    static const std::regex sep ("[\\s_\\-.]+");
    static const std::regex keyRe ("^[A-Ga-g](#|b|s)?(m|min|maj|minor|major|M)?$");
    static const std::regex chRe ("^(l|r|left|right|lt|rt)$", std::regex::icase);
    static const std::vector<std::string> noise { "stem", "stems", "st", "bounce", "export", "print",
                                                  "final", "mix", "wav" };
    auto isNoise = [&] (const std::string& p) {
        return std::find (noise.begin(), noise.end(), lower (p)) != noise.end();
    };
    std::vector<std::string> parts;
    for (std::sregex_token_iterator it (base.begin(), base.end(), sep, -1), e; it != e; ++it)
        if (! it->str().empty())
            parts.push_back (*it);
    auto isDigits = [] (const std::string& s) {
        return ! s.empty() && std::all_of (s.begin(), s.end(), [] (unsigned char c) { return std::isdigit (c); });
    };
    while (! parts.empty() && isDigits (parts.front()))
        parts.erase (parts.begin());
    while (! parts.empty() && (std::regex_match (parts.back(), chRe) || std::regex_match (parts.back(), keyRe)
                               || isNoise (parts.back())))
        parts.pop_back();
    std::string r;
    for (auto& p : parts)
        if (! isNoise (p))
            r += (r.empty() ? "" : " ") + p;
    return r.empty() ? base : r;
}

std::pair<std::string, char> channelSide (const std::string& name)
{
    const std::string base = stemOf (name);
    static const std::regex re ("^(.*?)[\\s_\\-.]+(L|R|Left|Right|Lt|Rt)$", std::regex::icase);
    std::smatch m;
    if (! std::regex_match (base, m, re))
        return { "", 0 };
    const char side = (char) std::toupper ((unsigned char) m[2].str()[0]);
    return { lower (m[1].str()), side };
}

std::pair<std::string, std::string> guessNames (const std::string& folder)
{
    std::string name = baseName (folder);
    std::replace (name.begin(), name.end(), '_', ' ');
    static const std::regex junk ("[\\[(][^\\])]*[\\])]|\\b(stems?|multi ?tracks?|multitrack|tracks|bounces?|"
                                  "exports?|session|wavs?|files)\\b",
                                  std::regex::icase);
    name = std::regex_replace (name, junk, " ");
    name = std::regex_replace (name, std::regex ("\\s+"), " ");
    name = trim (name, " -.");
    for (const char* s : { " - ", " -", "- " })
    {
        const auto p = name.find (s);
        if (p != std::string::npos)
            return { trim (name.substr (0, p), " -"), trim (name.substr (p + std::string (s).size()), " -") };
    }
    return { "", name };
}

} // namespace xk::naming
