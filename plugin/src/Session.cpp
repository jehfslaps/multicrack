#include "Session.h"

#include "AudioLoader.h"
#include "PreviewPlayer.h"
#include "engine/Naming.h"
#include "engine/Pipeline.h"
#include "engine/Render.h"

#include <set>

namespace xk
{

// ---------------------------------------------------------------- settings
Settings::Settings()
{
    juce::PropertiesFile::Options o;
    o.applicationName = "Xenakis";
    o.filenameSuffix = ".settings";
    o.folderName = "Xenakis";
    o.osxLibrarySubFolder = "Application Support";
    o.commonToAllUsers = false;
    o.ignoreCaseOfKeyNames = true;
    o.millisecondsBeforeSaving = 500;
    o.processLock = nullptr;
    props = std::make_unique<juce::PropertiesFile> (o);
}

static juce::File desktop()
{
    auto d = juce::File::getSpecialLocation (juce::File::userDesktopDirectory);
    return d.isDirectory() ? d : juce::File::getSpecialLocation (juce::File::userHomeDirectory);
}

// ----------------------------------------------------------------- session
Session::Session (PreviewPlayer& p) : player (p)
{
    formats.registerBasicFormats();
    const juce::File saved (settings().get ("base_dir"));
    baseDir = saved.isDirectory() ? saved : desktop();
}

Session::~Session()
{
    cancel_.store (true);
    pool.removeAllJobs (true, 20000);
}

void Session::setProgress (const juce::String& msg, float frac)
{
    const juce::ScopedLock sl (progressLock);
    busyMessage = msg;
    progress = frac;
}

std::pair<juce::String, float> Session::getProgress() const
{
    const juce::ScopedLock sl (progressLock);
    return { busyMessage, progress };
}

void Session::changed()
{
    sendChangeMessage();
}

void Session::run (const juce::String& message,
                   std::function<std::function<void()> (std::function<bool()> cancelled)> job)
{
    if (busy_)
        return;
    busy_ = true;
    setProgress (message, 0.0f);
    error.clear();
    cancel_.store (false);
    changed();
    juce::WeakReference<Session> weak (this);
    pool.addJob ([this, weak, job]() {
        std::function<void()> done;
        juce::String err;
        try
        {
            done = job ([this] { return cancel_.load(); });
        }
        catch (const std::exception& e)
        {
            err = e.what();
        }
        catch (...)
        {
            err = "Something went wrong.";
        }
        juce::MessageManager::callAsync ([weak, done, err]() {
            if (auto* s = weak.get())
            {
                s->busy_ = false;
                s->setProgress ({}, 0.0f);
                if (err.isNotEmpty())
                    s->error = err;
                if (done)
                    done();
                s->changed();
            }
        });
    });
}

// ------------------------------------------------------------ song details
void Session::setSong (const juce::String& a, const juce::String& s)
{
    artist = a;
    song = s;
    if (! prefixEdited)
        prefix = naming::makePrefix (a.toStdString(), s.toStdString());
    changed();
}

void Session::setPrefix (const juce::String& p)
{
    prefix = p;
    prefixEdited = p.trim().isNotEmpty();
    if (! prefixEdited)
        prefix = naming::makePrefix (artist.toStdString(), song.toStdString());
    changed();
}

juce::String Session::effectivePrefix() const
{
    return prefix;
}

juce::File Session::outputFolder() const
{
    return baseDir.getChildFile (naming::folderName (artist.toStdString(), song.toStdString()));
}

void Session::setBaseDir (const juce::File& dir)
{
    if (! dir.isDirectory())
        return;
    baseDir = dir;
    settings().set ("base_dir", dir.getFullPathName());
    changed();
}

// ------------------------------------------------------------------- stems
Stem* Session::stemById (int id) const
{
    for (auto& s : stems)
        if (s->id == id)
            return s.get();
    return nullptr;
}

void Session::addFiles (const juce::StringArray& paths)
{
    if (busy_ || paths.isEmpty())
        return;
    // artist and song from a dropped folder named like "Taylor Swift - Style (Stems)"
    if (artist.isEmpty() && song.isEmpty() && paths.size() == 1 && juce::File (paths[0]).isDirectory())
    {
        auto [a, s] = naming::guessNames (juce::File (paths[0]).getFileName().toStdString());
        if (! a.empty() && ! s.empty())
            setSong (juce::String (a), juce::String (s));
    }
    run ("Loading files", [this, paths] (std::function<bool()> cancelled) -> std::function<void()> {
        auto loaded = loadStems (paths, formats, [this] (const juce::String& m, int i, int n) {
            setProgress (m, n > 0 ? (float) i / (float) n : 0.0f);
        });
        for (size_t i = 0; i < loaded.size(); ++i)
        {
            if (cancelled())
                break;
            auto& st = loaded[i];
            if (st->mode == "skip")
                continue;
            setProgress ("Listening to " + juce::String (st->name), (float) i / (float) juce::jmax<size_t> (1, loaded.size()));
            try
            {
                st->kind = pipeline::detectKind (*st);
            }
            catch (...)
            {
                st->kind = "Melodic (other)";
            }
            st->status = "Ready";
        }
        return [this, loaded]() {
            std::set<std::string> have;
            for (auto& s : stems)
                for (auto& src : s->sources)
                    have.insert (src);
            int added = 0;
            for (auto& s : loaded)
                if (! have.count (s->path))
                {
                    stems.push_back (s);
                    ++added;
                }
            statusMessage = juce::String (stems.size()) + " file" + (stems.size() == 1 ? "" : "s")
                            + " loaded. Check the AI detection, then process.";
            if (added == 0 && ! loaded.empty())
                statusMessage = "Those files are already in the list.";
            if (loaded.empty())
                statusMessage = "No audio files found there.";
        };
    });
}

void Session::removeStem (int stemId)
{
    if (busy_)
        return;
    player.stop();
    stems.erase (std::remove_if (stems.begin(), stems.end(), [&] (auto& s) { return s->id == stemId; }), stems.end());
    chops.erase (std::remove_if (chops.begin(), chops.end(), [&] (auto& c) { return c.stemId == stemId; }), chops.end());
    changed();
}

void Session::setStemKind (int stemId, const juce::String& kind)
{
    if (auto* st = stemById (stemId))
    {
        st->kind = kind.toStdString();
        // a new kind means a new engine: forget the old grid / sections
        st->haveGrid = false;
        changed();
    }
}

// ------------------------------------------------------------------- chops
void Session::processAll()
{
    if (busy_ || stems.empty())
        return;
    player.stop();
    auto work = stems;   // shared pointers; the UI doesn't edit stems while busy
    run ("Finding the song tempo", [this, work] (std::function<bool()> cancelled) mutable -> std::function<void()> {
        std::optional<Song> grid;
        auto result = pipeline::process (work, grid, [this] (const std::string& m, int i, int n) {
            setProgress (juce::String (m), n > 0 ? (float) i / (float) n : 0.0f);
        }, cancelled);
        return [this, result, grid]() {
            chops = result;
            songGrid = grid;
            processed = true;
            statusMessage = juce::String (chops.size()) + " chops ready to review.";
        };
    });
}

Chop* Session::chopById (int id)
{
    for (auto& c : chops)
        if (c.id == id)
            return &c;
    return nullptr;
}

void Session::setApproved (int chopId, bool on)
{
    if (auto* c = chopById (chopId))
    {
        c->approved = on;
        changed();
    }
}

void Session::approveAll()
{
    for (auto& c : chops)
        c.approved = true;
    changed();
}

void Session::approveStem (int stemId)
{
    for (auto& c : chops)
        if (c.stemId == stemId)
            c.approved = true;
    changed();
}

void Session::removeStemChops (int stemId)
{
    player.stop();
    chops.erase (std::remove_if (chops.begin(), chops.end(), [&] (auto& c) { return c.stemId == stemId; }), chops.end());
    if (auto* st = stemById (stemId))
        st->status = "Nothing kept";
    changed();
}

void Session::deleteChop (int chopId)
{
    if (player.playingId() == chopId)
        player.stop();
    int stemId = -1;
    for (auto& c : chops)
        if (c.id == chopId)
            stemId = c.stemId;
    chops.erase (std::remove_if (chops.begin(), chops.end(), [&] (auto& c) { return c.id == chopId; }), chops.end());
    if (auto* st = stemById (stemId))
    {
        int n = 0;
        for (auto& c : chops)
            n += c.stemId == stemId;
        st->status = n ? std::to_string (n) + " chops" : "Nothing kept";
    }
    changed();
}

void Session::setLabel (int chopId, const juce::String& label)
{
    if (auto* c = chopById (chopId))
    {
        c->label = label.toStdString();
        changed();
    }
}

int Session::approvedCount() const
{
    int n = 0;
    for (auto& c : chops)
        n += c.approved ? 1 : 0;
    return n;
}

std::map<int, std::string> Session::names() const
{
    std::vector<std::string> files;
    const auto folder = outputFolder();
    if (folder.isDirectory())
        for (auto& f : folder.findChildFiles (juce::File::findFiles, false, "*.wav"))
            files.push_back (f.getFileName().toStdString());
    const auto pfx = effectivePrefix().toStdString();
    return naming::assignNames (chops, pfx, naming::existingCounts (files, pfx));
}

juce::String Session::nameOf (int chopId) const
{
    auto n = names();
    auto it = n.find (chopId);
    return it == n.end() ? juce::String() : juce::String (it->second);
}

// ------------------------------------------------------------------ export
void Session::exportAll()
{
    if (busy_ || chops.empty())
        return;
    player.stop();
    const auto folder = outputFolder();
    const auto nm = names();
    auto list = chops;
    std::map<int, StemPtr> byId;
    for (auto& s : stems)
        byId[s->id] = s;
    run ("Writing files", [this, folder, nm, list, byId] (std::function<bool()> cancelled) -> std::function<void()> {
        if (! folder.createDirectory())
            throw std::runtime_error ("Couldn't create the folder " + folder.getFullPathName().toStdString());
        juce::StringArray written;
        for (size_t i = 0; i < list.size(); ++i)
        {
            if (cancelled())
                break;
            const auto& c = list[i];
            auto it = byId.find (c.stemId);
            if (it == byId.end())
                continue;
            const auto name = juce::String (nm.at (c.id));
            setProgress ("Writing " + name, (float) i / (float) list.size());
            const auto bytes = render::wav24Bytes (render::renderChop (*it->second, c), it->second->sr);
            auto f = folder.getChildFile (name);
            if (! f.replaceWithData (bytes.data(), bytes.size()))
                throw std::runtime_error ("Couldn't write " + name.toStdString());
            written.add (f.getFullPathName());
        }
        return [this, written, folder]() {
            lastExportFiles = written;
            lastExportFolder = folder;
            statusMessage = "Exported " + juce::String (written.size()) + " files.";
        };
    });
}

void Session::startOver()
{
    if (busy_)
        return;
    player.stop();
    stems.clear();
    chops.clear();
    songGrid.reset();
    processed = false;
    lastExportFiles.clear();
    lastExportFolder = juce::File();
    artist.clear();
    song.clear();
    prefix.clear();
    prefixEdited = false;
    statusMessage.clear();
    changed();
}

juce::File Session::renderForDrag (int chopId)
{
    auto* c = chopById (chopId);
    if (c == nullptr)
        return {};
    auto* st = stemById (c->stemId);
    if (st == nullptr)
        return {};
    auto dir = juce::File::getSpecialLocation (juce::File::tempDirectory).getChildFile ("Xenakis").getChildFile ("drag");
    dir.createDirectory();
    auto name = nameOf (chopId);
    if (name.isEmpty())
        name = "Xenakis_sample.wav";
    auto f = dir.getChildFile (name);
    const auto bytes = render::wav24Bytes (render::renderChop (*st, *c), st->sr);
    return f.replaceWithData (bytes.data(), bytes.size()) ? f : juce::File();
}

// ----------------------------------------------------------------- preview
void Session::preview (int chopId, bool loop)
{
    auto* c = chopById (chopId);
    if (c == nullptr)
        return;
    auto* st = stemById (c->stemId);
    if (st == nullptr)
        return;
    player.play (render::renderChop (*st, *c), st->sr, chopId, loop || c->kind == "loop");
}

void Session::stopPreview()
{
    player.stop();
}

} // namespace xk
