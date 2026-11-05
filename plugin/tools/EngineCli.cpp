// xk_engine_cli <folder-or-files...> [--export DIR] [--json]
// Runs the C++ engine and prints what it finds, one line per chop (same format as
// tools/compare_engine.py prints for the Python engine).
#include "AudioLoader.h"
#include "engine/Naming.h"
#include "engine/Pipeline.h"
#include "engine/Render.h"

#include <juce_audio_formats/juce_audio_formats.h>

#include <chrono>
#include <cmath>
#include <cstdio>
#include <map>

// --selftest: synthetic kick + hats at 120 BPM, written to a temp WAV, loaded, chopped, exported.
static int selftest()
{
    const int sr = 44100, n = sr * 16;
    std::vector<float> kick ((size_t) n, 0.0f), hats ((size_t) n, 0.0f);
    juce::Random rng (7);
    for (int b = 0; b < 32; ++b)                       // a kick on every beat
        for (int i = 0; i < (int) (0.35 * sr); ++i)
        {
            const int k = b * sr / 2 + i;
            if (k >= n) break;
            const double t = i / (double) sr;
            kick[(size_t) k] += (float) (0.9 * std::exp (-t * 9.0) * std::sin (2 * juce::MathConstants<double>::pi * (55 + 120 * std::exp (-t * 30)) * t));
        }
    for (int b = 0; b < 64; ++b)                       // hats on eighth notes, two kinds
        for (int i = 0; i < (int) ((b % 4 == 2 ? 0.25 : 0.05) * sr); ++i)
        {
            const int k = b * sr / 4 + i;
            if (k >= n) break;
            hats[(size_t) k] += (float) ((rng.nextFloat() * 2 - 1) * 0.5 * std::exp (-i / (double) sr * (b % 4 == 2 ? 14 : 70)));
        }
    auto dir = juce::File::getSpecialLocation (juce::File::tempDirectory).getChildFile ("xenakis_selftest");
    dir.deleteRecursively();
    dir.createDirectory();
    xk::render::writeWav24 (dir.getChildFile ("Kick_Stem.wav").getFullPathName().toStdString(), { kick }, sr);
    xk::render::writeWav24 (dir.getChildFile ("Hats_Stem.wav").getFullPathName().toStdString(), { hats }, sr);
    juce::AudioFormatManager fm;
    fm.registerBasicFormats();
    auto stems = xk::loadStems ({ dir.getFullPathName() }, fm);
    if (stems.size() != 2) { std::printf ("SELFTEST FAILED: loaded %zu stems\n", stems.size()); return 1; }
    for (auto& st : stems)
        st->kind = xk::pipeline::detectKind (*st);
    std::optional<xk::Song> song;
    auto chops = xk::pipeline::process (stems, song);
    int kicks = 0, hatsN = 0;
    for (auto& c : chops)
    {
        kicks += c.label == "Kick";
        hatsN += c.label.find ("Hat") != std::string::npos;
    }
    std::printf ("kinds: %s, %s | bpm %.2f | %zu chops (%d kick, %d hat)\n", stems[0]->kind.c_str(),
                 stems[1]->kind.c_str(), song ? song->bpm : 0.0, chops.size(), kicks, hatsN);
    if (chops.empty() || kicks == 0 || hatsN == 0) { std::printf ("SELFTEST FAILED: missing chops\n"); return 1; }
    if (! song || std::abs (song->bpm - 120.0) > 1.0) { std::printf ("SELFTEST FAILED: tempo\n"); return 1; }
    std::map<int, xk::StemPtr> byId;
    for (auto& s : stems) byId[s->id] = s;
    auto bytes = xk::render::wav24Bytes (xk::render::renderChop (*byId[chops[0].stemId], chops[0]), sr);
    const bool header = bytes.size() > 44 && std::string (bytes.data(), 4) == "RIFF" && std::string (bytes.data() + 12, 4) == "fmt "
                        && std::string (bytes.data() + 36, 4) == "data";
    if (! header) { std::printf ("SELFTEST FAILED: wav header\n"); return 1; }
    dir.deleteRecursively();
    std::printf ("engine selftest ok\n");
    return 0;
}

int main (int argc, char** argv)
{
    if (argc >= 2 && juce::String (argv[1]) == "--selftest")
        return selftest();
    juce::StringArray inputs;
    juce::String exportDir;
    for (int i = 1; i < argc; ++i)
    {
        juce::String a (argv[i]);
        if (a == "--export" && i + 1 < argc)
            exportDir = argv[++i];
        else
            inputs.add (a);
    }
    juce::AudioFormatManager fm;
    fm.registerBasicFormats();
    const auto t0 = std::chrono::steady_clock::now();
    auto stems = xk::loadStems (inputs, fm);
    for (auto& st : stems)
        if (st->mode == "auto")
            st->kind = xk::pipeline::detectKind (*st);
    std::optional<xk::Song> song;
    auto chops = xk::pipeline::process (stems, song);
    const auto t1 = std::chrono::steady_clock::now();
    std::printf ("SONG bpm=%.2f downbeat=%d\n", song ? song->bpm : 0.0, song ? song->downbeat : 0);
    for (auto& st : stems)
    {
        int n = 0;
        for (auto& c : chops) n += c.stemId == st->id;
        std::printf ("STEM %s | kind=%s | sr=%d ch=%d frames=%d | %s\n", st->name.c_str(), st->kind.c_str(), st->sr,
                     st->channels(), st->frames(), st->status.c_str());
        for (auto& c : chops)
            if (c.stemId == st->id)
                std::printf ("  %-6s %-12s %9d %9d bars=%d %s\n", c.kind.c_str(), c.label.c_str(), c.start, c.end,
                             c.bars, c.flag.c_str());
    }
    std::printf ("TOTAL %zu chops in %.1f s\n", chops.size(),
                 std::chrono::duration<double> (t1 - t0).count());
    if (exportDir.isNotEmpty())
    {
        juce::File dir (exportDir);
        dir.createDirectory();
        std::map<int, xk::StemPtr> byId;
        for (auto& s : stems) byId[s->id] = s;
        auto names = xk::naming::assignNames (chops, "TS_Style_", {});
        for (auto& c : chops)
        {
            auto& st = *byId[c.stemId];
            auto x = xk::render::renderChop (st, c);
            xk::render::writeWav24 (dir.getChildFile (names[c.id]).getFullPathName().toStdString(), x, st.sr);
        }
        std::printf ("EXPORTED %zu files to %s\n", chops.size(), exportDir.toRawUTF8());
    }
    return 0;
}
