// Data model shared by the engine and the interface (mirrors multicrack/core/model.py).
#pragma once

#include <map>
#include <memory>
#include <string>
#include <utility>
#include <vector>

namespace xk
{

using Vec = std::vector<float>;

// ------------------------------------------------------------ sample types
inline const std::vector<std::string>& drumLabels()
{
    static const std::vector<std::string> v { "Kick", "Snare", "Clap", "Rim", "Closed Hat", "Open Hat",
                                              "Ride", "Crash", "Tom", "Shaker", "Tambourine", "Perc" };
    return v;
}

struct LabelGroup { std::string name; std::vector<std::string> labels; };

inline const std::vector<LabelGroup>& labelGroups()
{
    static const std::vector<LabelGroup> g {
        { "Drums", drumLabels() },
        { "Loops", { "Drum Loop", "Perc Loop", "Top Loop", "Fill", "Roll" } },
        { "FX", { "Whoosh", "Riser", "Downlifter", "Impact", "Laser", "Air Horn", "Siren", "Noise", "FX" } },
        { "Melodic", { "Guitar Chord", "Guitar Lead", "Guitar Stab", "Synth Lead", "Synth Stab", "Pad",
                       "Keys", "Bass", "Strings", "Brass" } },
        { "Vocals", { "Vocal Shout", "Vocal Chop", "Vocal FX", "Adlib", "Vocal Phrase" } },
    };
    return g;
}

inline bool isLoopedLabel (const std::string& l)
{
    return l == "Drum Loop" || l == "Perc Loop" || l == "Top Loop";
}

// ------------------------------------------------------------------ stem kinds
struct KindInfo { std::string name, engine, context; };

inline const std::vector<KindInfo>& stemKinds()
{
    static const std::vector<KindInfo> k {
        { "Kick", "oneshot", "kick" },       { "Snare", "oneshot", "snare" },
        { "Clap", "oneshot", "clap" },       { "Hats", "oneshot", "hats" },
        { "Cymbals", "oneshot", "cymbals" }, { "Toms", "oneshot", "toms" },
        { "Mixed hits", "oneshot", "mixed" },
        { "Full drums", "groove", "drums" }, { "Drum loops", "groove", "drums" },
        { "Perc / loops", "groove", "perc" }, { "Fills", "groove", "fills" },
        { "FX", "events", "fx" },            { "Vocals", "events", "vocal" },
        { "Guitar", "events", "guitar" },    { "Synth", "events", "synth" },
        { "Bass", "events", "bass" },        { "Keys", "events", "keys" },
        { "Strings", "events", "strings" },  { "Brass", "events", "brass" },
        { "Melodic (other)", "events", "melodic" },
    };
    return k;
}

inline const KindInfo* findKind (const std::string& name)
{
    for (auto& k : stemKinds())
        if (k.name == name)
            return &k;
    return nullptr;
}

int nextId();

// ------------------------------------------------------------------- chops
struct Chop
{
    int stemId = 0;
    int start = 0;               // sample index in the stem (inclusive)
    int end = 0;                 // sample index in the stem (exclusive)
    std::string label;
    std::string kind = "hit";    // hit | loop | roll | event | region
    int bars = 0;                // loop length in bars (0 = none)
    std::string origin = "auto"; // auto | ai | manual
    std::string flag;            // note shown on the review list
    bool cutAtNext = false;      // tail was cut where the next sound starts
    bool approved = false;
    double fadeInMs = -1.0;      // < 0 = automatic de-click
    double fadeOutMs = -1.0;
    bool reverse = false;
    double gainDb = 0.0;         // 0 = full level (normalized); negative turns it down
    bool seam = true;            // loops: crossfade the loop point
    int id = nextId();

    int length() const { return end > start ? end - start : 0; }
    Chop clone() const { Chop c = *this; c.id = nextId(); c.approved = false; return c; }
};

// ------------------------------------------------------------------- stems
struct Analysis;

struct Grid { double bpm = 0; double downbeat = 0; };
struct TempoEst { double bpm = 0; double confidence = 0; int downbeat = 0; };

struct GrooveOpt { bool loop = true; bool chop = true; };

struct StemOptions
{
    int bars = 4;
    std::string rollMode = "One-shot";   // One-shot | Loop | Skip
    bool includeHits = true;
    double bpm = 0;                      // 0 = use the detected tempo
    std::map<std::string, GrooveOpt> grooves;
};

struct Stem
{
    int id = nextId();
    std::string path;
    std::string name;          // file name shown in the interface
    std::string cleanName;     // name with track numbers, key and L/R removed
    std::vector<std::vector<float>> audio;   // [channel][frame]
    int sr = 44100;
    std::string kind = "Melodic (other)";
    std::string mode = "auto"; // auto | manual | skip
    std::string status = "Ready";
    std::vector<std::string> sources;
    StemOptions options;
    std::string error;

    // cached analysis
    std::shared_ptr<Analysis> an;
    bool haveOnsets = false;
    std::vector<int> onsets;
    bool haveGrid = false;
    Grid grid;
    bool haveTempoEst = false;
    std::shared_ptr<TempoEst> tempoEst;      // null when there is no steady pulse
    std::string tempoWarning;
    double centroid = 0;

    int frames() const { return audio.empty() ? 0 : (int) audio[0].size(); }
    int channels() const { return (int) audio.size(); }
    double seconds() const { return frames() / (double) sr; }
    const KindInfo& info() const
    {
        static const KindInfo other { "Melodic (other)", "events", "melodic" };
        auto* k = findKind (kind);
        return k ? *k : other;
    }
    std::string engine() const { return info().engine; }
    std::string context() const { return info().context; }
    const Vec& mono();

private:
    Vec mono_;
    bool haveMono_ = false;
};

using StemPtr = std::shared_ptr<Stem>;

struct Song
{
    double bpm = 0;
    int downbeat = 0;
    int ref = 0;
    int frames = 0;
    int sr = 0;
};

} // namespace xk
