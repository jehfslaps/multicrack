#include "AudioLoader.h"

#include "engine/Naming.h"

#include <map>
#include <set>

namespace xk
{

bool isAudioFile (const juce::File& f)
{
    static const juce::StringArray exts { ".wav", ".wave", ".aif", ".aiff", ".aifc", ".flac", ".mp3", ".ogg",
                                          ".oga", ".caf", ".w64", ".rf64", ".au", ".snd", ".m4a", ".wma" };
    return exts.contains (f.getFileExtension().toLowerCase()) && ! f.getFileName().startsWith ("._");
}

juce::Array<juce::File> expandPaths (const juce::StringArray& paths)
{
    juce::Array<juce::File> out;
    for (auto& p : paths)
    {
        juce::File f (p);
        if (f.isDirectory())
        {
            for (const auto& e : juce::RangedDirectoryIterator (f, true, "*", juce::File::findFiles))
                if (isAudioFile (e.getFile()))
                    out.add (e.getFile());
        }
        else if (f.existsAsFile() && isAudioFile (f))
            out.add (f);
    }
    // same order as Python's sorted(key=basename.lower())
    std::stable_sort (out.begin(), out.end(), [] (const juce::File& a, const juce::File& b) {
        return a.getFileName().toLowerCase().toStdString() < b.getFileName().toLowerCase().toStdString();
    });
    juce::Array<juce::File> uniq;
    std::set<juce::String> seen;
    for (auto& f : out)
    {
        auto k = f.getFullPathName().toLowerCase();
        if (seen.insert (k).second)
            uniq.add (f);
    }
    return uniq;
}

static bool hasAudio (const juce::File& folder, bool recursive)
{
    for (const auto& e : juce::RangedDirectoryIterator (folder, recursive, "*", juce::File::findFiles))
        if (isAudioFile (e.getFile()))
            return true;
    return false;
}

juce::Array<juce::File> splitSongs (const juce::StringArray& paths)
{
    juce::Array<juce::File> folders;
    for (auto& p : paths)
    {
        juce::File f (p);
        if (f.existsAsFile())
            return {};
        if (f.isDirectory())
            folders.add (f);
    }
    auto byName = [] (const juce::File& a, const juce::File& b) { return a.getFileName().compareIgnoreCase (b.getFileName()) < 0; };
    if (folders.size() >= 2)
    {
        for (auto& f : folders)
            if (! hasAudio (f, true))
                return {};
        std::stable_sort (folders.begin(), folders.end(), byName);
        return folders;
    }
    if (folders.size() == 1 && ! hasAudio (folders[0], false))
    {
        juce::Array<juce::File> songs;
        for (auto& d : folders[0].findChildFiles (juce::File::findDirectories, false))
            if (hasAudio (d, true))
                songs.add (d);
        std::stable_sort (songs.begin(), songs.end(), byName);
        if (songs.size() >= 2)
            return songs;
    }
    return {};
}

static bool readAudio (const juce::File& f, juce::AudioFormatManager& fm, std::vector<std::vector<float>>& out,
                       int& sr, juce::String& error)
{
    std::unique_ptr<juce::AudioFormatReader> r (fm.createReaderFor (f));
    if (! r)
    {
        error = "Can't read this file";
        return false;
    }
    const int ch = (int) juce::jmin<unsigned int> (2, r->numChannels);
    const auto len = r->lengthInSamples;
    if (len <= 0 || len > std::numeric_limits<int>::max() / 2 || ch <= 0)
    {
        error = "Empty or too long";
        return false;
    }
    juce::AudioBuffer<float> buf (ch, (int) len);
    if (! r->read (&buf, 0, (int) len, 0, true, ch > 1))
    {
        error = "Read failed";
        return false;
    }
    out.assign ((size_t) ch, {});
    for (int c = 0; c < ch; ++c)
    {
        out[(size_t) c].assign (buf.getReadPointer (c), buf.getReadPointer (c) + len);
        for (auto& v : out[(size_t) c])
            if (! std::isfinite (v))
                v = 0.0f;
    }
    sr = (int) std::lround (r->sampleRate);
    return true;
}

static StemPtr makeStem (const juce::File& f, std::vector<std::vector<float>> audio, int sr)
{
    auto s = std::make_shared<Stem>();
    s->path = f.getFullPathName().toStdString();
    s->name = f.getFileName().toStdString();
    s->cleanName = naming::cleanStemName (s->name);
    s->audio = std::move (audio);
    s->sr = sr;
    s->sources = { s->path };
    return s;
}

static StemPtr errorStem (const juce::File& f, const juce::String& msg)
{
    auto s = makeStem (f, { std::vector<float> (1, 0.0f) }, 44100);
    s->status = "Can't read this file";
    s->mode = "skip";
    s->error = msg.toStdString();
    return s;
}

std::vector<StemPtr> loadStems (const juce::StringArray& paths, juce::AudioFormatManager& fm, LoadProgress progress)
{
    const auto files = expandPaths (paths);
    std::map<std::pair<std::string, std::string>, std::map<char, juce::File>> sides;
    for (auto& f : files)
    {
        auto [base, side] = naming::channelSide (f.getFileName().toStdString());
        if (side)
            sides[{ f.getParentDirectory().getFullPathName().toLowerCase().toStdString(), base }][side] = f;
    }
    std::map<juce::String, juce::File> pairs;   // L path -> R file
    std::set<juce::String> skip;
    for (auto& kv : sides)
        if (kv.second.count ('L') && kv.second.count ('R'))
        {
            pairs[kv.second.at ('L').getFullPathName()] = kv.second.at ('R');
            skip.insert (kv.second.at ('R').getFullPathName());
        }
    std::vector<StemPtr> stems;
    std::set<juce::String> loaded;
    for (int i = 0; i < files.size(); ++i)
    {
        const auto& f = files.getReference (i);
        if (skip.count (f.getFullPathName()))
            continue;
        if (progress)
            progress ("Loading " + f.getFileName(), i, files.size());
        std::vector<std::vector<float>> audio;
        int sr = 44100;
        juce::String err;
        if (! readAudio (f, fm, audio, sr, err))
        {
            stems.push_back (errorStem (f, err));
            loaded.insert (f.getFullPathName());
            continue;
        }
        auto stem = makeStem (f, std::move (audio), sr);
        loaded.insert (f.getFullPathName());
        auto it = pairs.find (f.getFullPathName());
        if (it != pairs.end())
        {
            std::vector<std::vector<float>> r;
            int rsr = 0;
            juce::String rerr;
            if (readAudio (it->second, fm, r, rsr, rerr) && rsr == sr && stem->channels() == 1 && r.size() == 1
                && r[0].size() == stem->audio[0].size())
            {
                stem->audio.push_back (std::move (r[0]));
                stem->sources.push_back (it->second.getFullPathName().toStdString());
                stem->name = stem->name + " + " + it->second.getFileName().toStdString();
                loaded.insert (it->second.getFullPathName());
            }
        }
        stems.push_back (stem);
    }
    // a lone half of a pair that failed to join is loaded on its own
    for (auto& f : files)
        if (skip.count (f.getFullPathName()) && ! loaded.count (f.getFullPathName()))
        {
            std::vector<std::vector<float>> audio;
            int sr = 44100;
            juce::String err;
            if (readAudio (f, fm, audio, sr, err))
                stems.push_back (makeStem (f, std::move (audio), sr));
            else
                stems.push_back (errorStem (f, err));
        }
    return stems;
}

} // namespace xk
