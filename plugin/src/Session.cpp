#include "Session.h"

#include "AudioLoader.h"
#include "PreviewPlayer.h"
#include "engine/Engines.h"
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
            for (auto& c : chops)
            {
                c.origStart = c.start;
                c.origEnd = c.end;
            }
            undoStack.clear();
            redoStack.clear();
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
    checkpoint();
    if (auto* c = chopById (chopId))
    {
        c->approved = on;
        if (! on)
            c->exported.clear();   // approve it again to save a new copy
        changed();
    }
}

void Session::approveAll()
{
    checkpoint();
    for (auto& c : chops)
        c.approved = true;
    changed();
}

void Session::approveStem (int stemId)
{
    checkpoint();
    for (auto& c : chops)
        if (c.stemId == stemId)
            c.approved = true;
    changed();
}

void Session::removeStemChops (int stemId)
{
    checkpoint();
    player.stop();
    chops.erase (std::remove_if (chops.begin(), chops.end(), [&] (auto& c) { return c.stemId == stemId; }), chops.end());
    if (auto* st = stemById (stemId))
        st->status = "Nothing kept";
    changed();
}

void Session::deleteChop (int chopId)
{
    checkpoint();
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
    checkpoint();
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

// ------------------------------------------------------------------ editing
void Session::checkpoint()
{
    undoStack.push_back (chops);
    if (undoStack.size() > 200)
        undoStack.erase (undoStack.begin());
    redoStack.clear();
}

void Session::edited()
{
    for (auto& st : stems)
    {
        int n = 0;
        for (auto& c : chops)
            n += c.stemId == st->id;
        if (processed && st->mode != "skip")
            st->status = n ? std::to_string (n) + " chops" : "Nothing kept";
    }
    changed();
}

// what's already in the folder stays saved (undo never makes Export write it twice)
void Session::keepSaved (std::vector<Chop>& restored) const
{
    std::map<int, std::string> saved;
    for (auto& c : chops)
        if (! c.exported.empty())
            saved[c.id] = c.exported;
    for (auto& c : restored)
        if (auto it = saved.find (c.id); it != saved.end())
            c.exported = it->second;
}

bool Session::undo()
{
    if (undoStack.empty() || busy_)
        return false;
    player.stop();
    redoStack.push_back (chops);
    keepSaved (undoStack.back());
    chops = undoStack.back();
    undoStack.pop_back();
    edited();
    return true;
}

bool Session::redo()
{
    if (redoStack.empty() || busy_)
        return false;
    player.stop();
    undoStack.push_back (chops);
    keepSaved (redoStack.back());
    chops = redoStack.back();
    redoStack.pop_back();
    edited();
    return true;
}

void Session::setTrim (int chopId, int start, int end, bool remember)
{
    auto* c = chopById (chopId);
    auto* st = c ? stemById (c->stemId) : nullptr;
    if (c == nullptr || st == nullptr)
        return;
    const int n = st->frames(), minLen = juce::jmax (1, (int) (0.005 * st->sr));
    start = juce::jlimit (0, juce::jmax (0, n - minLen), start);
    end = juce::jlimit (start + minLen, n, end);
    if (start == c->start && end == c->end)
        return;
    if (remember)
        checkpoint();
    c->start = start;
    c->end = end;
    c->cutAtNext = false;
    changed();
}

void Session::resetTrim (int chopId)
{
    if (auto* c = chopById (chopId))
        if (c->origStart >= 0 && (c->start != c->origStart || c->end != c->origEnd))
            setTrim (chopId, c->origStart, c->origEnd);
}

int Session::cloneChop (int chopId)
{
    for (size_t i = 0; i < chops.size(); ++i)
        if (chops[i].id == chopId)
        {
            checkpoint();
            auto twin = chops[i].clone();
            chops.insert (chops.begin() + (long) i + 1, twin);
            edited();
            return twin.id;
        }
    return -1;
}

int Session::magnet (int stemId, int s)
{
    auto* st = stemById (stemId);
    if (st == nullptr)
        return s;
    const auto& on = engines::getOnsets (*st);
    if (on.empty())
        return s;
    auto it = std::lower_bound (on.begin(), on.end(), s);
    int best = -1;
    for (auto j : { it, it == on.begin() ? it : it - 1 })
        if (j != on.end() && (best < 0 || std::abs (*j - s) < std::abs (best - s)))
            best = *j;
    return best >= 0 && std::abs (best - s) <= (int) (0.012 * st->sr) ? best : s;
}

int Session::snapToBar (int stemId, int s) const
{
    auto* st = stemById (stemId);
    if (st == nullptr)
        return s;
    double bpm = st->options.bpm > 0 ? st->options.bpm : (st->haveGrid ? st->grid.bpm : 0.0);
    double down = st->haveGrid ? st->grid.downbeat : 0.0;
    if (bpm <= 0 && songGrid && songGrid->bpm > 0)
    {
        bpm = songGrid->bpm;
        down = songGrid->downbeat;
    }
    if (bpm <= 0)
        return s;
    const double bar = 240.0 * st->sr / bpm;
    const double d0 = std::fmod (down, bar);
    return (int) std::lround (d0 + std::round ((s - d0) / bar) * bar);
}

int Session::newChopAt (int stemId, int at, int afterChopId)
{
    auto* st = stemById (stemId);
    if (st == nullptr || st->frames() < 64)
        return -1;
    const int n = st->frames(), sr = st->sr;
    at = juce::jlimit (0, n - 1, at);
    const auto& on = engines::getOnsets (*st);
    // the sound you just heard: the latest onset up to 250 ms before the spot (or just after it)
    int start = at;
    {
        int best = -1;
        for (int o : on)
        {
            if (o > at + (int) (0.03 * sr))
                break;
            if (o >= at - (int) (0.25 * sr))
                best = o;
        }
        if (best >= 0)
            start = best;
    }
    int end = juce::jmin (n, start + (int) (0.5 * sr));
    for (int o : on)
        if (o > start + (int) (0.06 * sr))
        {
            end = juce::jmin (n, juce::jmin (o, start + (int) (2.0 * sr)));
            break;
        }
    end = juce::jmax (end, juce::jmin (n, start + (int) (0.06 * sr)));
    Chop c;
    c.stemId = stemId;
    c.start = start;
    c.end = end;
    c.origStart = start;
    c.origEnd = end;
    c.kind = "region";
    c.origin = "manual";
    std::string label;
    for (auto& x : chops)
        if (x.stemId == stemId)
        {
            label = x.label;
            if (x.id == afterChopId)
                break;
        }
    if (label.empty())
    {
        // a stem with no chops yet: name it after the stem's type ("Kick", "Vocals" ...)
        label = st->kind.substr (0, st->kind.find (" ("));
        for (auto& grp : labelGroups())
            for (auto& l : grp.labels)
                if (naming::lower (l) == naming::lower (label))
                    label = l;
    }
    c.label = label;
    checkpoint();
    auto pos = chops.end();
    for (auto it = chops.begin(); it != chops.end(); ++it)
        if (it->id == afterChopId)
            pos = it + 1;
    if (pos == chops.end() && afterChopId < 0)
        for (auto it = chops.begin(); it != chops.end(); ++it)
            if (it->stemId == stemId)
                pos = it + 1;
    const int id = c.id;
    chops.insert (pos, c);
    edited();
    return id;
}

void Session::setFades (int chopId, double inMs, double outMs, bool remember)
{
    if (auto* c = chopById (chopId))
    {
        if (c->fadeInMs == inMs && c->fadeOutMs == outMs)
            return;
        if (remember)
            checkpoint();
        c->fadeInMs = inMs;
        c->fadeOutMs = outMs;
        changed();
    }
}

void Session::setGain (int chopId, double db, bool remember)
{
    if (auto* c = chopById (chopId))
    {
        db = juce::jlimit (-48.0, 0.0, db);
        if (c->gainDb == db)
            return;
        if (remember)
            checkpoint();
        c->gainDb = db;
        changed();
    }
}

void Session::setReverse (int chopId, bool on)
{
    if (auto* c = chopById (chopId))
        if (c->reverse != on)
        {
            checkpoint();
            c->reverse = on;
            changed();
        }
}

void Session::setSeam (int chopId, bool on)
{
    if (auto* c = chopById (chopId))
        if (c->seam != on)
        {
            checkpoint();
            c->seam = on;
            changed();
        }
}

int Session::toExportCount() const
{
    int n = 0;
    for (auto& c : chops)
        n += (c.approved && c.exported.empty()) ? 1 : 0;
    return n;
}

int Session::savedCount() const
{
    int n = 0;
    for (auto& c : chops)
        n += c.exported.empty() ? 0 : 1;
    return n;
}

// Names as they will land in the folder: saved chops keep their saved name, approved chops are
// numbered next (that's what Export writes), then the rest.
std::map<int, std::string> Session::names() const
{
    std::vector<std::string> files;
    const auto folder = outputFolder();
    if (folder.isDirectory())
        for (auto& f : folder.findChildFiles (juce::File::findFiles, false, "*.wav"))
            files.push_back (f.getFileName().toStdString());
    const auto pfx = effectivePrefix().toStdString();
    std::vector<Chop> order;
    for (int pass = 0; pass < 2; ++pass)
        for (auto& c : chops)
            if (c.exported.empty() && c.approved == (pass == 0))
                order.push_back (c);
    auto out = naming::assignNames (order, pfx, naming::existingCounts (files, pfx));
    for (auto& c : chops)
        if (! c.exported.empty())
            out[c.id] = c.exported;
    return out;
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
    if (busy_ || toExportCount() == 0)
        return;
    player.stop();
    const auto folder = outputFolder();
    const auto nm = names();
    std::vector<Chop> list;   // approved and not saved yet; the rest are skipped
    for (auto& c : chops)
        if (c.approved && c.exported.empty())
            list.push_back (c);
    std::map<int, StemPtr> byId;
    for (auto& s : stems)
        byId[s->id] = s;
    run ("Writing files", [this, folder, nm, list, byId] (std::function<bool()> cancelled) -> std::function<void()> {
        if (! folder.createDirectory())
            throw std::runtime_error ("Couldn't create the folder " + folder.getFullPathName().toStdString());
        juce::StringArray written;
        std::vector<std::pair<int, std::string>> saved;
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
            saved.emplace_back (c.id, name.toStdString());
        }
        return [this, written, folder, saved]() {
            for (auto& [id, name] : saved)
                if (auto* c = chopById (id))
                    c->exported = name;
            lastExportFiles = written;
            lastExportFolder = folder;
            ++exportCount;
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
    undoStack.clear();
    redoStack.clear();
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

void Session::previewStem (int stemId, int fromSample)
{
    auto* st = stemById (stemId);
    if (st == nullptr || st->frames() == 0)
        return;
    const int from = juce::jlimit (0, st->frames() - 1, fromSample);
    // up to two minutes from the spot (plenty for listening through; keeps the copy small)
    const int to = juce::jmin (st->frames(), from + 120 * st->sr);
    std::vector<std::vector<float>> part;
    for (auto& ch : st->audio)
        part.emplace_back (ch.begin() + from, ch.begin() + to);
    stemPlayFrom = from;
    stemPlayLen = to - from;
    player.play (part, st->sr, STEM_PLAY + stemId, false);
}

void Session::stopPreview()
{
    player.stop();
}

} // namespace xk
