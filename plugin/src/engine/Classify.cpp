#include "engine/Classify.h"

#include "engine/Naming.h"

#include <algorithm>
#include <set>

namespace xk::classify
{

namespace
{
struct Hint { const char* kind; std::set<std::string> words; };

const std::vector<Hint>& hints()
{
    static const std::vector<Hint> h {
        { "Vocals", { "vox", "vocal", "vocals", "voc", "vo", "adlib", "adlibs", "shout", "shouts", "chant",
                      "chants", "bgv", "bv", "bvs", "harmony", "harmonies", "acapella", "acap" } },
        { "Kick", { "kick", "kicks", "kik", "kck", "bd", "bassdrum" } },
        { "Snare", { "snare", "snares", "snr", "sd", "rim", "rimshot" } },
        { "Clap", { "clap", "claps", "clp" } },
        { "Hats", { "hat", "hats", "hh", "hihat", "hihats", "hhat" } },
        { "Cymbals", { "crash", "ride", "cym", "cymbal", "cymbals", "splash", "china", "oh", "overhead",
                       "overheads" } },
        { "Toms", { "tom", "toms", "floortom" } },
        { "Fills", { "fill", "fills", "roll", "rolls" } },
        { "Perc / loops", { "perc", "percs", "percussion", "conga", "congas", "bongo", "bongos", "shaker",
                            "shakers", "tamb", "tambo", "tambourine", "cowbell", "timbale", "timbales",
                            "clave", "claves", "guiro", "triangle", "block", "cabasa" } },
        { "Drum loops", { "loop", "loops", "groove", "grooves", "break", "breaks", "beat", "beats",
                          "breakbeat" } },
        { "Full drums", { "drum", "drums", "kit", "drm", "drms", "room", "rooms", "dr" } },
        { "FX", { "fx", "sfx", "efx", "riser", "risers", "rise", "sweep", "sweeps", "whoosh", "swoosh",
                  "impact", "impacts", "noise", "uplifter", "downlifter", "downer", "laser", "lasers", "zap",
                  "transition", "transitions", "reverse", "atmos", "atmosphere", "foley" } },
        { "Guitar", { "gtr", "gtrs", "guitar", "guitars", "gt", "acgtr", "elecgtr" } },
        { "Bass", { "bass", "sub", "subs", "808", "bs", "subbass" } },
        { "Keys", { "keys", "piano", "pno", "rhodes", "wurli", "wurlitzer", "epiano", "ep", "organ", "clav",
                    "clavinet" } },
        { "Strings", { "strings", "string", "str", "violin", "violins", "viola", "cello", "cellos", "orch",
                       "orchestra" } },
        { "Brass", { "brass", "horn", "horns", "trumpet", "trumpets", "sax", "trombone", "tpt" } },
        { "Synth", { "synth", "synths", "syn", "juno", "moog", "prophet", "jupiter", "ob", "lead", "leads",
                     "arp", "arps", "pluck", "plucks", "pad", "pads", "saw", "poly", "chord", "chords", "stab",
                     "stabs", "serum", "massive", "sylenth", "nexus" } },
    };
    return h;
}
} // namespace

std::vector<std::string> kindsFromName (const std::string& name)
{
    std::vector<std::string> toks;
    for (auto& t : naming::splitTokens (name))
        toks.push_back (naming::lower (t));
    std::string joined;
    for (auto& t : toks)
        joined += t;
    std::vector<std::string> out;
    auto add = [&] (const char* k) {
        if (std::find (out.begin(), out.end(), k) == out.end())
            out.push_back (k);
    };
    for (auto& h : hints())
        for (auto& t : toks)
            if (h.words.count (t))
            {
                add (h.kind);
                break;
            }
    if (out.empty())
        for (auto& h : hints())
            for (auto& w : h.words)
                if (w.size() >= 4 && joined.find (w) != std::string::npos)
                {
                    add (h.kind);
                    break;
                }
    return out;
}

std::string kindFromAudio (const Analysis& an, const std::vector<int>& onsets,
                           const std::vector<std::pair<std::string, int>>& labelCounts, double tempoConf,
                           double activeFrac, double pitch, double centroid)
{
    int nHits = 0;
    for (auto& kv : labelCounts)
        nHits += kv.second;
    const double dur = an.n / (double) an.sr;
    const double rate = (double) onsets.size() / std::max (dur * std::max (activeFrac, 0.05), 1e-3);
    const bool percussive = nHits > 0 && rate > 0.8 && pitch < 0.55;
    if (percussive)
    {
        std::string top;
        int topN = -1;
        int distinct = 0;
        for (auto& kv : labelCounts)
        {
            if (kv.second > topN)
            {
                topN = kv.second;
                top = kv.first;
            }
            if (kv.second >= 0.08 * nHits)
                ++distinct;
        }
        const double share = topN / (double) std::max (nHits, 1);
        if (share > 0.8)
        {
            static const std::map<std::string, std::string> m {
                { "Kick", "Kick" }, { "Snare", "Snare" }, { "Clap", "Clap" }, { "Closed Hat", "Hats" },
                { "Open Hat", "Hats" }, { "Crash", "Cymbals" }, { "Ride", "Cymbals" }, { "Tom", "Toms" },
                { "Shaker", "Perc / loops" } };
            auto it = m.find (top);
            return it != m.end() ? it->second : "Perc / loops";
        }
        if (tempoConf > 2.2 && activeFrac > 0.3 && distinct >= 2)
        {
            int kicks = 0;
            for (auto& kv : labelCounts)
                if (kv.first == "Kick")
                    kicks = kv.second;
            return kicks > 0.1 * nHits ? "Full drums" : "Perc / loops";
        }
        return "Mixed hits";
    }
    if (pitch > 0.45)
        return centroid < 300 ? "Bass" : "Synth";
    return "FX";
}

std::string drumLabel (const HitFeat& f, const std::string& context)
{
    const double c = f.centroid, lo = f.low, hi = f.high, flat = f.flat, dec = f.decay;
    if (context == "kick") return "Kick";
    if (context == "snare") return (f.bursts >= 3 && dec < 0.25) ? "Clap" : "Snare";
    if (context == "clap") return "Clap";
    if (context == "toms") return "Tom";
    if (context == "hats" || context == "cymbals")
    {
        if (dec > 0.9)
            return (flat > 0.2 || context == "cymbals") ? "Crash" : "Ride";
        if (context == "cymbals")
            return dec < 0.5 ? "Ride" : "Crash";
        return dec > 0.16 ? "Open Hat" : "Closed Hat";
    }
    std::string label;
    if (lo > 0.42 && c < 1500) label = "Kick";
    else if (hi > 0.42 || c > 6500) label = dec > 0.9 ? "Crash" : (dec > 0.16 ? "Open Hat" : "Closed Hat");
    else if (c > 1200 && flat > 0.08) label = (f.bursts >= 3 && dec < 0.25) ? "Clap" : "Snare";
    else if (c < 1200 && lo + f.mid > 0.7 && flat < 0.12 && dec > 0.1) label = "Tom";
    else label = "Perc";
    if (context == "perc")
    {
        static const std::map<std::string, std::string> m {
            { "Closed Hat", "Shaker" }, { "Open Hat", "Shaker" }, { "Kick", "Perc" }, { "Snare", "Perc" },
            { "Clap", "Clap" }, { "Tom", "Perc" }, { "Crash", "Perc" } };
        auto it = m.find (label);
        return it != m.end() ? it->second : label;
    }
    return label;
}

std::string loopLabel (const std::vector<std::string>& hitLabels, const std::string& context, double centroid)
{
    if (context == "perc") return "Perc Loop";
    if (std::find (hitLabels.begin(), hitLabels.end(), "Kick") != hitLabels.end()) return "Drum Loop";
    if (centroid > 3000) return "Top Loop";
    return (context == "perc" || context == "fills") ? "Perc Loop" : "Drum Loop";
}

std::string fxLabel (const EventFeat& f)
{
    const double dur = f.dur, pp = f.peakPos, flat = f.flat, pitch = f.pitch, att = f.attack;
    const double c0 = f.centParts[0], c2 = f.centParts[2];
    if (pp > 0.62 && dur > 0.8) return "Riser";
    if (att < 0.03 && dur > 0.35 && f.centroid < 1800 && pp < 0.2) return "Impact";
    if (pitch > 0.5 && dur < 1.6 && (std::max (c0, c2) > 1.6 * std::min (c0, c2) + 1)) return "Laser";
    if (pp < 0.35 && dur > 0.9 && c0 > 1.4 * c2) return "Downlifter";
    if (flat > 0.12 && 0.2 <= pp && pp <= 0.8 && 0.25 < dur && dur < 3.5) return "Whoosh";
    if (flat > 0.2 && dur > 1.0) return "Noise";
    return "FX";
}

std::string vocalLabel (const EventFeat& f, bool fxHint)
{
    const bool processed = f.pitch < 0.3 || f.flat > 0.25;
    if (fxHint && processed) return "Vocal FX";
    if (f.dur < 0.9) return f.attack < 0.08 ? "Vocal Shout" : "Vocal Chop";
    if (f.dur < 2.6) return "Adlib";
    return "Vocal Phrase";
}

std::string melodicLabel (const EventFeat& f, const std::string& context)
{
    const double dur = f.dur;
    const bool poly = f.peaks >= 7;
    const bool shortHit = dur < 0.7 && f.attack < 0.06;
    if (context == "guitar")
    {
        if (shortHit) return "Guitar Stab";
        return poly ? "Guitar Chord" : "Guitar Lead";
    }
    if (context == "bass") return "Bass";
    if (context == "keys") return "Keys";
    if (context == "strings") return "Strings";
    if (context == "brass") return "Brass";
    if (f.centroid < 260 && ! poly) return "Bass";
    if (shortHit) return "Synth Stab";
    if (dur > 1.6 && (poly || f.attack > 0.12)) return "Pad";
    return "Synth Lead";
}

double summarizeSpectrum (const Analysis& an)
{
    const int nFft = 2048, hop = 4096;
    const auto freqs = rfftFreqs (nFft, an.sr);
    std::vector<double> cents, levels;
    stftMag (an.m.data(), an.n, nFft, hop, [&] (int, const float* mag) {
        double tot = 0, w = 0;
        for (int k = 0; k <= nFft / 2; ++k)
        {
            const double p = (double) mag[k] * mag[k];
            tot += p;
            w += p * freqs[(size_t) k];
        }
        cents.push_back (w / (tot + 1e-12));
        levels.push_back (tot);
    });
    if (levels.empty())
        return 0.0;
    const double mx = *std::max_element (levels.begin(), levels.end());
    if (mx <= 0)
        return 0.0;
    std::vector<double> loud;
    for (size_t i = 0; i < levels.size(); ++i)
        if (levels[i] > mx * 1e-3)
            loud.push_back (cents[i]);
    return loud.empty() ? 0.0 : median (loud);
}

} // namespace xk::classify
