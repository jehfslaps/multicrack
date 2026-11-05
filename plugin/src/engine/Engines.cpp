#include "engine/Engines.h"

#include "engine/Classify.h"
#include "engine/Naming.h"
#include "engine/Tempo.h"

#include <algorithm>
#include <cmath>
#include <map>
#include <numeric>
#include <set>

namespace xk::engines
{

static const int VARIATIONS = 3;
static const int VARIATIONS_PERC = 6;
static const double MIN_DIFF_HIT = 0.05;
static const double MIN_DIFF_EVENT = 0.06;

static double maxHitLen (const std::string& ctx)
{
    static const std::map<std::string, double> m { { "kick", 1.5 }, { "snare", 2.0 }, { "clap", 1.5 },
                                                   { "hats", 1.6 }, { "cymbals", 6.0 }, { "toms", 2.5 },
                                                   { "mixed", 3.0 }, { "drums", 2.0 }, { "perc", 1.5 },
                                                   { "fills", 2.5 } };
    auto it = m.find (ctx);
    return it != m.end() ? it->second : 2.0;
}

Analysis& getAnalysis (Stem& stem)
{
    if (! stem.an)
        stem.an = std::make_shared<Analysis> (stem.mono(), stem.sr);
    return *stem.an;
}

double reattackDb (const Analysis& an, int o)
{
    const int sr = an.sr, H = Analysis::HOP_ENV;
    const int ne = (int) an.env.size();
    const int b0 = std::max (0, (o - (int) (0.03 * sr)) / H), b1 = std::min (ne, std::max (1, o / H));
    const int a0 = o / H, a1 = std::min (ne, std::max (o / H + 1, (o + (int) (0.035 * sr)) / H));
    if (b1 <= b0 || a1 <= a0)
        return 99.0;
    float bmin = 1e30f, amax = 0.0f;
    for (int i = b0; i < b1; ++i) bmin = std::min (bmin, an.env[(size_t) i]);
    for (int i = a0; i < a1; ++i) amax = std::max (amax, an.env[(size_t) i]);
    return 20.0 * std::log10 ((amax + 1e-9) / (bmin + 1e-9));
}

const std::vector<int>& getOnsets (Stem& stem)
{
    if (! stem.haveOnsets)
    {
        auto& an = getAnalysis (stem);
        auto raw = an.onsets();
        if (raw.size() > 2)
        {
            std::vector<double> ra, fl;
            for (int o : raw)
            {
                ra.push_back (reattackDb (an, o));
                const int a = std::max (0, o / Analysis::HOP_ONSET - 1);
                const int b = std::min ((int) an.flux.size(), o / Analysis::HOP_ONSET + 4);
                float mx = 0;
                for (int i = a; i < b; ++i) mx = std::max (mx, an.flux[(size_t) i]);
                fl.push_back (mx);
            }
            const double med = median (fl);
            std::vector<int> kept;
            for (size_t i = 0; i < raw.size(); ++i)
            {
                const double rel = fl[i] / (med + 1e-12);
                if (! (ra[i] < 2.0 && rel < 0.5))
                    kept.push_back (raw[i]);
            }
            raw.swap (kept);
        }
        stem.onsets = raw;
        stem.haveOnsets = true;
    }
    return stem.onsets;
}

// ------------------------------------------------------------------- hits
namespace
{
struct Hit
{
    int start = 0, end = 0;
    bool cut = false;
    HitFeat f;
    double gap = 0, pre = 0, score = 0, rel = 0;
    std::string label;
};

std::vector<Hit> makeHits (const Analysis& an, const std::vector<int>& onsets, const std::string& context,
                           int withinA = -1, int withinB = -1)
{
    const int sr = an.sr;
    const double maxLen = maxHitLen (context);
    const bool within = withinA >= 0;
    std::vector<Hit> hits;
    for (size_t i = 0; i < onsets.size(); ++i)
    {
        const int s = onsets[i];
        if (within && ! (withinA <= s && s < withinB - (int) (0.01 * sr)))
            continue;
        const int nxt = i + 1 < onsets.size() ? onsets[i + 1] : an.n;
        int limit = nxt - (int) (0.003 * sr);
        if (within)
            limit = std::min (limit, withinB);
        auto [end, cut] = an.tailEnd (s, limit, -50.0, 0.025, maxLen);
        if (end - s < (int) (0.012 * sr))
            continue;
        Hit h;
        h.f = an.features (s, end);
        if (h.f.attack > std::max (0.03, 0.3 * (end - s) / (double) sr))
            continue;   // the loud part comes late: the onset landed on something else
        const int H = Analysis::HOP_ENV;
        const int ne = (int) an.env.size();
        const int preA = std::max (0, s - (int) (0.006 * sr)) / H;
        const int preB = std::min (ne, std::max (preA + 1, s / H));
        float pmax = 0;
        for (int q = std::min (preA, ne - 1); q < preB; ++q)
            pmax = std::max (pmax, an.env[(size_t) q]);
        h.pre = pmax / (h.f.level + 1e-9);
        h.gap = (nxt - s) / (double) sr;
        h.start = s;
        h.end = end;
        h.cut = cut;
        h.label = classify::drumLabel (h.f, context);
        hits.push_back (std::move (h));
    }
    if (! hits.empty())
    {
        double loud = 0;
        for (auto& h : hits) loud = std::max (loud, h.f.level);
        loud += 1e-9;
        for (auto& h : hits)
        {
            const double rel = h.f.level / loud;
            h.score = (h.cut ? 0.0 : 1.0) + std::min (h.gap, 1.2) * 0.5 - std::min (h.pre, 1.0) * 1.5 + rel * 0.8;
            h.rel = rel;
        }
    }
    return hits;
}

int drumIndex (const std::string& l)
{
    const auto& d = drumLabels();
    auto it = std::find (d.begin(), d.end(), l);
    return it == d.end() ? 99 : (int) (it - d.begin());
}

std::vector<Chop> pickHits (Stem& stem, const std::vector<Hit>& hits, const std::string& context)
{
    std::vector<std::string> order;                      // labels, insertion order
    std::map<std::string, std::vector<const Hit*>> byLabel;
    for (auto& h : hits)
    {
        if (h.rel < 0.12)
            continue;   // faint ghost notes and bleed
        if (! byLabel.count (h.label))
            order.push_back (h.label);
        byLabel[h.label].push_back (&h);
    }
    std::stable_sort (order.begin(), order.end(),
                      [] (const std::string& a, const std::string& b) { return drumIndex (a) < drumIndex (b); });
    const bool drumCtx = context == "drums" || context == "perc" || context == "fills" || context == "mixed";
    std::vector<Chop> chops;
    for (auto& label : order)
    {
        auto group = byLabel[label];
        std::stable_sort (group.begin(), group.end(), [] (const Hit* a, const Hit* b) { return a->score > b->score; });
        if (drumCtx && group.size() < 2 && hits.size() > 12)
            if (group[0]->cut || group[0]->pre > 0.3)
                continue;   // a lone stray hit of a different type is usually a misread
        const size_t take = std::min (group.size(), (size_t) std::max (8, std::min (120, (int) group.size() / 2)));
        std::vector<const Hit*> top (group.begin(), group.begin() + (long) take);
        std::vector<Vec> vecs;
        for (auto* h : top) vecs.push_back (h->f.vec);
        std::vector<int> idx ((size_t) top.size());
        std::iota (idx.begin(), idx.end(), 0);
        const int k = label == "Perc" ? VARIATIONS_PERC : VARIATIONS;
        auto picked = farthestPick (vecs, idx, k, MIN_DIFF_HIT);
        std::sort (picked.begin(), picked.end(), [&] (int a, int b) { return top[(size_t) a]->start < top[(size_t) b]->start; });
        for (int i : picked)
        {
            const Hit* h = top[(size_t) i];
            Chop c;
            c.stemId = stem.id;
            c.start = h->start;
            c.end = h->end;
            c.label = label;
            c.kind = "hit";
            c.cutAtNext = h->cut;
            c.flag = h->cut ? "Tail cut at the next hit." : "";
            chops.push_back (c);
        }
    }
    return chops;
}
} // namespace

std::vector<Chop> oneshotEngine (Stem& stem)
{
    auto& an = getAnalysis (stem);
    const auto& onsets = getOnsets (stem);
    auto hits = makeHits (an, onsets, stem.context());
    return pickHits (stem, hits, stem.context());
}

// ----------------------------------------------------------------- grooves
static bool barGrid (Stem& stem, Analysis& an, double& bpm, double& bar, double& d0)
{
    if (! stem.haveGrid)
    {
        auto est = tempo::estimate (an);
        if (! est)
            return false;
        stem.grid = { est->bpm, (double) est->downbeat };
        stem.haveGrid = true;
    }
    bpm = stem.options.bpm > 0 ? stem.options.bpm : stem.grid.bpm;
    bar = 240.0 * an.sr / bpm;
    d0 = std::fmod (stem.grid.downbeat, bar);
    if (d0 < 0) d0 += bar;
    return true;
}

static double norm (const std::vector<double>& v)
{
    double s = 0;
    for (double x : v) s += x * x;
    return std::sqrt (s);
}

std::vector<Chop> grooveEngine (Stem& stem)
{
    auto& an = getAnalysis (stem);
    const int sr = an.sr;
    const auto& onsets = getOnsets (stem);
    const std::string ctx = stem.context();
    auto& opts = stem.options;
    const int wantBars = opts.bars;
    const std::string rollMode = opts.rollMode;

    double bpm, bar, d0;
    if (! barGrid (stem, an, bpm, bar, d0))
        return pickHits (stem, makeHits (an, onsets, ctx), ctx);
    const int nb = (int) std::floor ((an.n - d0) / bar);
    const int H = Analysis::HOP_ONSET;
    const auto& flux = an.flux;
    const auto& low = an.fluxLow;
    const auto& high = an.fluxHigh;
    const int nf = (int) flux.size();
    const auto act = an.activeMask (512, -42.0);

    std::vector<std::vector<double>> descs;
    std::vector<char> active;
    for (int b = 0; b < nb; ++b)
    {
        const double s = d0 + b * bar;
        std::vector<double> p (16);
        double pmax = 0;
        for (int j = 0; j < 16; ++j)
        {
            const int a = (int) ((s + j * bar / 16) / H);
            const int e = std::max (a + 1, (int) ((s + (j + 1) * bar / 16) / H));
            double v = 0;
            if (a < nf)
                for (int q = a; q < std::min (e, nf); ++q)
                    v = std::max (v, (double) flux[(size_t) q]);
            p[(size_t) j] = v;
            pmax = std::max (pmax, v);
        }
        const int a0 = (int) (s / H), a1 = std::min (nf, (int) ((s + bar) / H));
        std::vector<double> prof (3, 0.0);
        if (a1 > a0)
        {
            for (int q = a0; q < a1; ++q)
            {
                prof[0] += low[(size_t) q];
                prof[1] += std::max (0.0, (double) flux[(size_t) q] - low[(size_t) q] - high[(size_t) q]);
                prof[2] += high[(size_t) q];
            }
            for (auto& v : prof) v /= (a1 - a0);
        }
        const double pn = norm (p) + 1e-9, prn = norm (prof) + 1e-9;
        std::vector<double> d;
        for (double v : p) d.push_back (v / pn);
        for (double v : prof) d.push_back (v / prn * 0.6);
        descs.push_back (d);
        const int m0 = (int) (s / 512), m1 = std::min ((int) act.size(), (int) ((s + bar) / 512));
        double frac = 0;
        if (m1 > m0)
        {
            int c = 0;
            for (int q = m0; q < m1; ++q) c += act[(size_t) q] ? 1 : 0;
            frac = c / (double) (m1 - m0);
        }
        active.push_back (frac > 0.55 && pmax > 0);
    }
    auto sim = [&] (int i, int j) {
        double dot = 0;
        for (size_t q = 0; q < descs[(size_t) i].size(); ++q) dot += descs[(size_t) i][q] * descs[(size_t) j][q];
        return dot / (norm (descs[(size_t) i]) * norm (descs[(size_t) j]) + 1e-9);
    };
    std::vector<char> repeating ((size_t) nb, 0);
    for (int i = 0; i < nb; ++i)
        if (active[(size_t) i])
            for (int d : { -2, -1, 1, 2 })
            {
                const int j = i + d;
                if (j >= 0 && j < nb && active[(size_t) j] && sim (i, j) > 0.86)
                {
                    repeating[(size_t) i] = 1;
                    break;
                }
            }
    std::vector<std::pair<int, int>> segs;
    for (int i = 0; i < nb;)
    {
        if (repeating[(size_t) i])
        {
            int j = i;
            while (j + 1 < nb && repeating[(size_t) j + 1]) ++j;
            if (j - i + 1 >= 2) segs.push_back ({ i, j + 1 });
            i = j + 1;
        }
        else
            ++i;
    }

    // group sections that play the same groove
    struct Cluster { std::vector<double> center; std::vector<std::pair<int, int>> segs; };
    std::vector<Cluster> clusters;
    auto bySize = segs;
    std::stable_sort (bySize.begin(), bySize.end(), [] (auto& a, auto& b) { return (a.second - a.first) > (b.second - b.first); });
    for (auto& sg : bySize)
    {
        std::vector<double> v (descs.empty() ? 19 : descs[0].size(), 0.0);
        for (int q = sg.first; q < sg.second; ++q)
            for (size_t t = 0; t < v.size(); ++t) v[t] += descs[(size_t) q][t];
        for (auto& x : v) x /= (sg.second - sg.first);
        const double vn = norm (v) + 1e-9;
        for (auto& x : v) x /= vn;
        Cluster* best = nullptr;
        double bs = 0.0;
        for (auto& c : clusters)
        {
            double dot = 0;
            for (size_t t = 0; t < v.size(); ++t) dot += v[t] * c.center[t];
            if (dot > bs)
            {
                bs = dot;
                best = &c;
            }
        }
        if (best && bs > 0.93)
            best->segs.push_back (sg);
        else
            clusters.push_back ({ v, { sg } });
    }
    auto total = [] (const Cluster& c) { int t = 0; for (auto& s : c.segs) t += s.second - s.first; return t; };
    std::stable_sort (clusters.begin(), clusters.end(), [&] (auto& a, auto& b) { return total (a) > total (b); });
    if (clusters.size() > 4) clusters.resize (4);
    auto firstBar = [] (const Cluster& c) { int m = 1 << 30; for (auto& s : c.segs) m = std::min (m, s.first); return m; };
    std::stable_sort (clusters.begin(), clusters.end(), [&] (auto& a, auto& b) { return firstBar (a) < firstBar (b); });

    std::vector<Chop> chops;
    std::vector<Hit> pool;
    std::vector<char> inGroove ((size_t) std::max (0, nb), 0);
    for (auto& sg : segs)
        for (int q = sg.first; q < sg.second; ++q) inGroove[(size_t) q] = 1;

    auto snap = [&] (double x) {
        if (onsets.empty()) return (int) std::nearbyint (x);
        int bestI = 0;
        double bd = 1e300;
        for (size_t q = 0; q < onsets.size(); ++q)
        {
            const double d = std::abs (onsets[q] - x);
            if (d < bd) { bd = d; bestI = (int) q; }
        }
        return bd < 0.025 * sr ? onsets[(size_t) bestI] : (int) std::nearbyint (x);
    };

    for (size_t ci = 0; ci < clusters.size(); ++ci)
    {
        const auto& c = clusters[ci];
        const std::string name = std::string ("Groove ") + (char) ('A' + ci);
        auto& go = opts.grooves[name];
        auto longest = c.segs[0];
        for (auto& s : c.segs)
            if (s.second - s.first > longest.second - longest.first) longest = s;
        const int segLen = longest.second - longest.first;
        int nUse = 1;
        for (int nn : { 16, 8, 4, 2, 1 })
            if (nn <= std::max (1, std::min (wantBars, segLen))) { nUse = nn; break; }
        const int ls = snap (d0 + longest.first * bar);
        const int le = std::min (an.n, ls + (int) std::nearbyint (nUse * bar));
        auto hits = makeHits (an, onsets, ctx, ls, le);
        std::vector<std::string> strong;
        double cent = 0;
        for (auto& h : hits)
        {
            if (h.rel > 0.3) strong.push_back (h.label);
            cent += h.f.centroid;
        }
        cent = hits.empty() ? 0.0 : cent / hits.size();
        const std::string label = classify::loopLabel (strong, ctx, cent);
        if (go.loop)
        {
            Chop ch;
            ch.stemId = stem.id;
            ch.start = ls;
            ch.end = le;
            ch.label = label;
            ch.kind = "loop";
            ch.bars = nUse;
            ch.flag = nUse < wantBars ? "This section only fits " + std::to_string (nUse) + " bars." : "";
            chops.push_back (ch);
        }
        if (go.chop)
            for (auto& h : hits) pool.push_back (h);
    }

    // outside the grooves: rolls and single hits
    auto barOf = [&] (double x) { return (int) std::floor ((x - d0) / bar); };
    std::vector<int> outside;
    for (int o : onsets)
    {
        const int b = barOf (o);
        if (! (b >= 0 && b < nb && inGroove[(size_t) b]))
            outside.push_back (o);
    }
    std::vector<std::vector<int>> rolls;
    std::vector<int> singles;
    for (size_t i = 0; i < outside.size();)
    {
        size_t j = i;
        while (j + 1 < outside.size() && outside[j + 1] - outside[j] < 0.17 * sr && outside[j + 1] - outside[i] < 2.2 * bar)
            ++j;
        std::vector<int> group (outside.begin() + (long) i, outside.begin() + (long) j + 1);
        if (group.size() >= 4 && group.back() - group.front() > 0.25 * sr)
            rolls.push_back (group);
        else
            singles.insert (singles.end(), group.begin(), group.end());
        i = j + 1;
    }
    struct Roll { int start, end; bool cut; EventFeat f; };
    std::vector<Roll> rollItems;
    for (auto& grp : rolls)
    {
        int limit = an.n;
        for (int o : onsets)
            if (o > grp.back()) { limit = o - (int) (0.0015 * sr); break; }
        auto [end, cut] = an.tailEnd (grp.back(), limit, -50.0, 0.025, 2.5);
        rollItems.push_back ({ grp.front(), end, cut, an.eventFeatures (grp.front(), end) });
    }
    if (! rollItems.empty() && rollMode != "Skip")
    {
        std::vector<Vec> vecs;
        for (auto& r : rollItems) vecs.push_back (r.f.vec);
        std::vector<int> order ((size_t) rollItems.size());
        std::iota (order.begin(), order.end(), 0);
        std::stable_sort (order.begin(), order.end(), [&] (int a, int b) { return rollItems[(size_t) a].f.level > rollItems[(size_t) b].f.level; });
        std::vector<int> kept;
        for (auto& g : groupItems (vecs, order, 0.32))
            for (int k : farthestPick (vecs, g, 2, MIN_DIFF_EVENT))
                kept.push_back (k);
        std::stable_sort (kept.begin(), kept.end(), [&] (int a, int b) { return rollItems[(size_t) a].f.level > rollItems[(size_t) b].f.level; });
        if (kept.size() > 6) kept.resize (6);
        std::stable_sort (kept.begin(), kept.end(), [&] (int a, int b) { return rollItems[(size_t) a].start < rollItems[(size_t) b].start; });
        for (int k : kept)
        {
            const auto& r = rollItems[(size_t) k];
            Chop ch;
            ch.stemId = stem.id;
            if (rollMode == "Loop")
            {
                const double bstart = d0 + barOf (r.start) * bar;
                const int nbars = std::max (1, (int) std::ceil ((r.end - bstart) / bar - 0.15));
                const int s_ = snap (bstart);
                ch.start = s_;
                ch.end = std::min (an.n, s_ + (int) std::nearbyint (nbars * bar));
                ch.label = "Fill";
                ch.kind = "loop";
                ch.bars = nbars;
            }
            else
            {
                ch.start = r.start;
                ch.end = r.end;
                ch.label = "Roll";
                ch.kind = "roll";
                ch.cutAtNext = r.cut;
                ch.flag = r.cut ? "Ends where the next sound starts." : "";
            }
            chops.push_back (ch);
        }
    }
    if (opts.includeHits && ! singles.empty())
    {
        std::set<int> sset (singles.begin(), singles.end());
        for (auto& h : makeHits (an, onsets, ctx))
            if (sset.count (h.start)) pool.push_back (h);
    }
    if (! pool.empty())
    {
        double loud = 0;
        for (auto& h : pool) loud = std::max (loud, h.f.level);
        loud += 1e-9;
        for (auto& h : pool) h.rel = h.f.level / loud;
        auto more = pickHits (stem, pool, ctx);
        chops.insert (chops.end(), more.begin(), more.end());
    }
    return chops;
}

// ------------------------------------------------------------------ events
namespace
{
struct EvParams { double gap, minLen, maxLen; int cap; double group; };

std::vector<std::pair<int, int>> regions (const Analysis& an, double gap, double minLen)
{
    const int hop = 256;
    const auto mask = an.activeMask (hop, -45.0);
    const int sr = an.sr;
    std::vector<int> idx;
    for (int i = 0; i < (int) mask.size(); ++i)
        if (mask[(size_t) i]) idx.push_back (i);
    if (idx.empty()) return {};
    std::vector<std::pair<int, int>> regs;
    int start = idx[0], prev = idx[0];
    const int gapF = (int) (gap * sr / hop);
    for (size_t q = 1; q < idx.size(); ++q)
    {
        const int i = idx[q];
        if (i - prev > gapF)
        {
            regs.push_back ({ start, prev + 1 });
            start = i;
        }
        prev = i;
    }
    regs.push_back ({ start, prev + 1 });
    std::vector<std::pair<int, int>> out;
    for (auto& r : regs)
    {
        const int s = r.first * hop, e = std::min (an.n, r.second * hop);
        if ((e - s) / (double) sr >= minLen) out.push_back ({ s, e });
    }
    return out;
}

std::vector<std::pair<int, int>> splitLong (const Analysis& an, int s, int e, double maxLen, double minPiece)
{
    const int sr = an.sr, H = Analysis::HOP_ENV;
    if ((e - s) / (double) sr <= maxLen) return { { s, e } };
    const int ne = (int) an.env.size();
    std::vector<float> env;
    for (int i = s / H; i < std::min (ne, e / H); ++i) env.push_back (an.env[(size_t) i]);
    const int k = std::max (1, (int) (0.03 * sr / H));
    auto sm = boxSame (env.data(), (int) env.size(), k);
    if ((int) env.size() < k) sm.resize (env.size());
    const int lo = (int) (minPiece * sr / H);
    if ((int) sm.size() <= 2 * lo) return { { s, s + (int) (maxLen * sr) } };
    int cut = lo;
    for (int i = lo; i < (int) sm.size() - lo; ++i)
        if (sm[(size_t) i] < sm[(size_t) cut]) cut = i;
    const int c = s + cut * H;
    auto a = splitLong (an, s, c, maxLen, minPiece);
    auto b = splitLong (an, c, e, maxLen, minPiece);
    a.insert (a.end(), b.begin(), b.end());
    return a;
}

struct Unit { int s, e; bool trimmed; };

std::vector<Unit> melodicUnits (Stem& stem, const Analysis& an, int s, int e, double bpm)
{
    const int sr = an.sr;
    const double beat = bpm > 0 ? 60.0 / bpm : 0.48;
    const int minUnit = (int) (beat * sr * 0.95);
    const int maxUnit = (int) (4 * beat * sr);
    std::vector<int> starts { an.refineStart (s) };
    for (int o : getOnsets (stem))
        if (s + (int) (0.05 * sr) <= o && o < e - (int) (0.05 * sr) && reattackDb (an, o) >= 6.0)
            starts.push_back (o);
    std::vector<Unit> out;
    size_t i = 0;
    while (i < starts.size())
    {
        const int st = starts[i];
        size_t j = i + 1;
        while (j < starts.size() && starts[j] - st < minUnit) ++j;
        int natural;
        if (j < starts.size())
            natural = starts[j] - (int) (0.003 * sr);
        else
        {
            natural = an.tailEnd (std::max (st, e - (int) (0.03 * sr)), std::min (an.n, e + (int) (2.0 * sr)), -55.0).first;
            natural = std::max (natural, e);
        }
        const int end = std::min (natural, st + maxUnit);
        if (end - st >= (int) (0.12 * sr)) out.push_back ({ st, end, end < natural });
        i = j;
    }
    return out;
}

std::vector<Chop> phrases (Stem& stem, const Analysis& an, const std::string& ctx, int bars, int cap)
{
    if (! stem.haveGrid) return {};
    const int sr = an.sr;
    const double bar = 240.0 * sr / stem.grid.bpm;
    double d0 = std::fmod (stem.grid.downbeat, bar);
    if (d0 < 0) d0 += bar;
    const auto mask = an.activeMask (512, -40.0);
    std::vector<std::pair<int, int>> cands;
    for (int b = 0; d0 + (b + bars) * bar <= an.n; b += bars)
    {
        const int s = (int) std::nearbyint (d0 + b * bar), e = (int) std::nearbyint (d0 + (b + bars) * bar);
        double frac = 0;
        const int m0 = s / 512, m1 = std::min ((int) mask.size(), e / 512);
        if (e / 512 > s / 512 && m1 > m0)
        {
            int c = 0;
            for (int q = m0; q < m1; ++q) c += mask[(size_t) q] ? 1 : 0;
            frac = c / (double) (m1 - m0);
        }
        if (frac > 0.8) cands.push_back ({ s, e });
    }
    (void) sr;
    if (cands.empty()) return {};
    std::vector<EventFeat> feats;
    std::vector<Vec> vecs;
    for (auto& c : cands)
    {
        feats.push_back (an.eventFeatures (c.first, c.second));
        vecs.push_back (feats.back().vec);
    }
    std::vector<int> order ((size_t) cands.size());
    std::iota (order.begin(), order.end(), 0);
    std::stable_sort (order.begin(), order.end(), [&] (int a, int b) { return feats[(size_t) a].level > feats[(size_t) b].level; });
    auto groups = groupItems (vecs, order, 0.12);
    std::stable_sort (groups.begin(), groups.end(), [] (auto& a, auto& b) { return a.size() > b.size(); });
    static const std::map<std::string, std::string> labels { { "guitar", "Guitar Lead" }, { "keys", "Keys" },
                                                             { "strings", "Strings" }, { "brass", "Brass" },
                                                             { "bass", "Bass" } };
    auto it = labels.find (ctx);
    const std::string label = it != labels.end() ? it->second : "Synth Lead";
    std::vector<Chop> out;
    for (size_t g = 0; g < groups.size() && (int) g < cap; ++g)
    {
        Chop c;
        c.stemId = stem.id;
        c.start = cands[(size_t) groups[g][0]].first;
        c.end = cands[(size_t) groups[g][0]].second;
        c.label = label;
        c.kind = "event";
        c.origin = "ai";
        c.flag = "AI suggestion: " + std::to_string (bars) + "-bar phrase.";
        out.push_back (c);
    }
    return out;
}
} // namespace

std::vector<Chop> eventsEngine (Stem& stem, double bpm)
{
    auto& an = getAnalysis (stem);
    const int sr = an.sr;
    const std::string ctx = stem.context();
    const std::string family = ctx == "fx" ? "fx" : (ctx == "vocal" ? "vocal" : "melodic");
    EvParams P = family == "fx" ? EvParams { 0.25, 0.08, 14.0, 20, 0.30 }
               : family == "vocal" ? EvParams { 0.14, 0.12, 6.0, 16, 0.28 }
                                   : EvParams { 0.15, 0.12, 4.0, 12, 0.14 };
    if (family == "melodic" && bpm > 0)
        P.maxLen = std::min (8.0, 2 * 240.0 / bpm);
    bool fxHint = false;
    for (auto& t : naming::splitTokens (stem.name))
        if (naming::lower (t) == "fx") fxHint = true;

    std::vector<Unit> segs;
    for (auto [s, e] : regions (an, P.gap, P.minLen))
    {
        if (family != "melodic") s = an.refineStart (s);
        if (family == "melodic")
        {
            auto u = melodicUnits (stem, an, s, e, bpm);
            segs.insert (segs.end(), u.begin(), u.end());
        }
        else
            for (auto [a, b] : splitLong (an, s, e, P.maxLen, family == "vocal" ? 0.8 : 1.5))
            {
                const int nxt = b + (int) (0.25 * sr);
                const int end = an.tailEnd (std::max (a, b - (int) (0.03 * sr)), std::min (an.n, nxt), -55.0).first;
                segs.push_back ({ a, std::max (b, end), false });
            }
    }
    if (segs.empty()) return {};
    struct Item { int start, end; EventFeat f; std::string label; bool trimmed; };
    std::vector<Item> items;
    for (auto& sg : segs)
    {
        Item it { sg.s, sg.e, an.eventFeatures (sg.s, sg.e), "", sg.trimmed };
        if (family == "fx") it.label = classify::fxLabel (it.f);
        else if (family == "vocal") it.label = classify::vocalLabel (it.f, fxHint);
        else it.label = classify::melodicLabel (it.f, ctx);
        items.push_back (std::move (it));
    }
    double loud = 0;
    for (auto& it : items) loud = std::max (loud, it.f.level);
    loud += 1e-9;
    items.erase (std::remove_if (items.begin(), items.end(), [&] (const Item& it) { return ! (it.f.level / loud > 0.08); }),
                 items.end());
    if (items.empty()) return {};
    std::vector<Vec> vecs;
    for (auto& it : items) vecs.push_back (it.f.vec);
    std::vector<int> order ((size_t) items.size());
    std::iota (order.begin(), order.end(), 0);
    std::stable_sort (order.begin(), order.end(), [&] (int a, int b) { return items[(size_t) a].f.level > items[(size_t) b].f.level; });
    auto groups = groupItems (vecs, order, P.group);
    std::stable_sort (groups.begin(), groups.end(), [&] (auto& a, auto& b) {
        return std::sqrt ((double) a.size()) * items[(size_t) a[0]].f.level > std::sqrt ((double) b.size()) * items[(size_t) b[0]].f.level;
    });
    std::vector<std::vector<int>> perGroup;
    for (auto& g : groups) perGroup.push_back (farthestPick (vecs, g, VARIATIONS, MIN_DIFF_EVENT));
    std::vector<int> picked;
    for (int rnd = 0; rnd < VARIATIONS; ++rnd)
        for (auto& pg : perGroup)
            if (rnd < (int) pg.size() && (int) picked.size() < P.cap)
                picked.push_back (pg[(size_t) rnd]);
    std::vector<Chop> phraseChops;
    if (family == "melodic")
    {
        if (picked.size() > 6) picked.resize (6);
        phraseChops = phrases (stem, an, ctx, 1, 3);
        auto two = phrases (stem, an, ctx, 2, 3);
        phraseChops.insert (phraseChops.end(), two.begin(), two.end());
    }
    std::stable_sort (picked.begin(), picked.end(), [&] (int a, int b) { return items[(size_t) a].start < items[(size_t) b].start; });
    std::vector<Chop> chops;
    for (int k : picked)
    {
        const auto& it = items[(size_t) k];
        Chop c;
        c.stemId = stem.id;
        c.start = it.start;
        c.end = it.end;
        c.label = it.label;
        c.kind = "event";
        c.origin = family == "melodic" ? "ai" : "auto";
        c.flag = family == "melodic" ? "AI suggestion: check the label." : "";
        if (it.trimmed) c.flag = c.flag.empty() ? "Long part trimmed." : c.flag + " Long part trimmed.";
        chops.push_back (c);
    }
    chops.insert (chops.end(), phraseChops.begin(), phraseChops.end());
    std::stable_sort (chops.begin(), chops.end(), [] (const Chop& a, const Chop& b) { return a.start < b.start; });
    return chops;
}

} // namespace xk::engines
