#include "engine/Pipeline.h"

#include "engine/Classify.h"
#include "engine/Engines.h"
#include "engine/Tempo.h"

#include <algorithm>
#include <cmath>
#include <numeric>
#include <set>

namespace xk::pipeline
{

bool isDrumKind (const std::string& kind)
{
    static const std::set<std::string> k { "Kick", "Snare", "Clap", "Hats", "Cymbals", "Toms", "Full drums",
                                           "Drum loops", "Perc / loops", "Fills", "Mixed hits" };
    return k.count (kind) > 0;
}

std::string detectKind (Stem& stem)
{
    auto& an = engines::getAnalysis (stem);
    const double centroid = classify::summarizeSpectrum (an);
    stem.centroid = centroid;
    const auto hints = classify::kindsFromName (stem.name);
    // (the desktop app lets a trained model listen when the name is unclear; the plug-in uses the
    // first hint for now)
    std::string hinted = hints.empty() ? "" : hints[0];
    if (hinted == "Synth" && centroid > 0 && centroid < 300)
        hinted = "Bass";
    if (! hinted.empty())
        return hinted;
    const auto& onsets = engines::getOnsets (stem);
    const size_t step = std::max<size_t> (1, onsets.size() / 150);
    std::vector<std::pair<std::string, int>> counts;
    for (size_t i = 0; i < onsets.size(); i += step)
    {
        const int s = onsets[i];
        const int e = std::min (an.n, s + (int) (0.3 * an.sr));
        const std::string lab = classify::drumLabel (an.features (s, e), "drums");
        auto it = std::find_if (counts.begin(), counts.end(), [&] (auto& kv) { return kv.first == lab; });
        if (it == counts.end()) counts.push_back ({ lab, 1 });
        else ++it->second;
    }
    const auto mask = an.activeMask (1024);
    double active = 0;
    if (! mask.empty())
    {
        int c = 0;
        for (char m : mask) c += m ? 1 : 0;
        active = c / (double) mask.size();
    }
    // loudest moments: env[::64] sorted descending
    std::vector<int> idx;
    for (int i = 0; i < (int) an.env.size(); i += 64) idx.push_back (i / 64);
    std::stable_sort (idx.begin(), idx.end(), [&] (int a, int b) { return an.env[(size_t) a * 64] > an.env[(size_t) b * 64]; });
    if (idx.size() > 8) idx.resize (8);
    std::vector<double> ps;
    for (int q : idx)
    {
        const int p = q * 64 * Analysis::HOP_ENV;
        const int len = std::max (0, std::min (an.n, p + (int) (0.2 * an.sr)) - p);
        ps.push_back (pitchStrength (an.m.data() + p, len, an.sr));
    }
    const double pitch = ps.empty() ? 0.0 : median (ps);
    std::shared_ptr<TempoEst> est = onsets.size() > 16 ? tempo::estimate (an) : nullptr;
    const double conf = est ? est->confidence : 0.0;
    return classify::kindFromAudio (an, onsets, counts, conf, active, pitch, centroid);
}

static std::shared_ptr<TempoEst> tempoEst (Stem& st)
{
    if (! st.haveTempoEst)
    {
        st.tempoEst = tempo::estimate (engines::getAnalysis (st));
        st.haveTempoEst = true;
    }
    return st.tempoEst;
}

std::optional<Song> lockTempo (std::vector<StemPtr>& stems)
{
    Stem* bestStem = nullptr;
    std::shared_ptr<TempoEst> best;
    for (auto& st : stems)
    {
        if (st->mode != "auto" || ! isDrumKind (st->kind) || st->seconds() < 6)
            continue;
        auto est = tempoEst (*st);
        if (est && (! best || est->confidence > best->confidence))
        {
            best = est;
            bestStem = st.get();
        }
    }
    if (! bestStem)
        return std::nullopt;
    Song s;
    s.bpm = best->bpm;
    s.downbeat = best->downbeat;
    s.ref = bestStem->id;
    s.frames = bestStem->frames();
    s.sr = bestStem->sr;
    return s;
}

void applyGrid (Stem& stem, const std::optional<Song>& song)
{
    stem.tempoWarning.clear();
    if (! song)
    {
        stem.haveGrid = false;
        return;
    }
    const bool sameTimeline = stem.sr == song->sr && std::abs (stem.frames() - song->frames) < stem.sr;
    if (sameTimeline)
        stem.grid = { song->bpm, (double) song->downbeat };
    else
    {
        auto est = tempoEst (stem);
        if (! est)
            stem.grid = { song->bpm, 0.0 };
        else
            stem.grid = { tempo::fits (est->bpm, song->bpm) ? song->bpm : est->bpm, (double) est->downbeat };
    }
    stem.haveGrid = true;
    if (stem.engine() == "groove")
    {
        std::shared_ptr<TempoEst> est = stem.haveTempoEst ? stem.tempoEst : nullptr;
        if (! est && isDrumKind (stem.kind))
            est = tempoEst (stem);
        if (est && est->confidence > 2.0 && ! tempo::fits (est->bpm, song->bpm))
        {
            char buf[32];
            std::snprintf (buf, sizeof (buf), "%g", song->bpm);
            stem.tempoWarning = std::string ("Rhythm doesn't fit the song tempo (") + buf + " BPM). Check its loops.";
        }
    }
}

std::vector<Chop> chopStem (Stem& stem, const std::optional<Song>& song)
{
    if (stem.mode != "auto")
        return {};
    if (! findKind (stem.kind))
        stem.kind = "Melodic (other)";
    applyGrid (stem, song);
    const std::string eng = stem.engine();
    std::vector<Chop> chops;
    if (eng == "oneshot") chops = engines::oneshotEngine (stem);
    else if (eng == "groove") chops = engines::grooveEngine (stem);
    else chops = engines::eventsEngine (stem, song ? song->bpm : 0.0);
    if (! stem.tempoWarning.empty())
        for (auto& c : chops)
            if (c.kind == "loop")
                c.flag = c.flag.empty() ? stem.tempoWarning : c.flag + " " + stem.tempoWarning;
    return chops;
}

std::vector<Chop> process (std::vector<StemPtr>& stems, std::optional<Song>& song, Progress progress,
                           const std::function<bool()>& cancelled)
{
    std::vector<Stem*> work;
    for (auto& s : stems)
        if (s->mode == "auto")
            work.push_back (s.get());
    if (progress) progress ("Finding the song tempo", 0, (int) std::max<size_t> (1, work.size()) + 1);
    song = lockTempo (stems);
    std::vector<Chop> out;
    for (size_t i = 0; i < work.size(); ++i)
    {
        if (cancelled && cancelled())
            break;
        auto* st = work[i];
        if (progress) progress ("Chopping " + st->name, (int) i + 1, (int) work.size() + 1);
        try
        {
            auto chops = chopStem (*st, song);
            st->status = chops.empty() ? "Nothing found" : std::to_string (chops.size()) + " chops";
            out.insert (out.end(), chops.begin(), chops.end());
        }
        catch (const std::exception& e)
        {
            st->status = "Couldn't chop this file";
            st->error = e.what();
        }
    }
    return out;
}

} // namespace xk::pipeline
