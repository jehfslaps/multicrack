// xk_snapshot OUTDIR STEMS_FOLDER [WxH ...]
// Runs the real plug-in (processor + editor), loads and processes the stems, and saves
// PNG snapshots of each page in both themes and at each UI size. Also checks a few things
// and prints "snapshot ok" at the end (exit code 1 on failure).
#include "PluginEditor.h"
#include "PluginProcessor.h"

#include <cstdio>

static void pump (int ms)
{
    juce::MessageManager::getInstance()->runDispatchLoopUntil (ms);
}

static bool waitIdle (xk::Session& s, int timeoutMs = 600000)
{
    const auto t0 = juce::Time::getMillisecondCounter();
    pump (100);
    while (s.busy())
    {
        pump (50);
        if (juce::Time::getMillisecondCounter() - t0 > (juce::uint32) timeoutMs)
            return false;
    }
    pump (200);
    return true;
}

static void save (juce::Component& c, const juce::File& f)
{
    auto img = c.createComponentSnapshot (c.getLocalBounds(), true, 1.0f);
    f.deleteFile();
    juce::FileOutputStream out (f);
    juce::PNGImageFormat().writeImageToStream (img, out);
    std::printf ("saved %s (%dx%d)\n", f.getFileName().toRawUTF8(), img.getWidth(), img.getHeight());
}

static int fail (const char* why)
{
    std::printf ("SNAPSHOT FAILED: %s\n", why);
    return 1;
}

int main (int argc, char** argv)
{
    if (argc >= 2 && juce::String (argv[1]) == "--state-test")
    {
        juce::ScopedJuceInitialiser_GUI init;
        XenakisProcessor a;
        a.previewLevel->setValueNotifyingHost (0.0556f);
        juce::MemoryBlock mb;
        a.getStateInformation (mb);
        XenakisProcessor b;
        b.setStateInformation (mb.getData(), (int) mb.getSize());
        std::printf ("state bytes %d  a=%.4f  b=%.4f\n", (int) mb.getSize(), a.previewLevel->get(), b.previewLevel->get());
        return std::abs (a.previewLevel->get() - b.previewLevel->get()) < 1e-4f ? 0 : 1;
    }
    if (argc < 3)
        return fail ("usage: xk_snapshot OUTDIR STEMS [WxH ...]");
    juce::ScopedJuceInitialiser_GUI init;
    const juce::File outDir (juce::File::getCurrentWorkingDirectory().getChildFile (argv[1]));
    outDir.createDirectory();
    std::vector<std::pair<int, int>> sizes;
    for (int i = 3; i < argc; ++i)
    {
        auto s = juce::String (argv[i]);
        sizes.push_back ({ s.upToFirstOccurrenceOf ("x", false, false).getIntValue(), s.fromFirstOccurrenceOf ("x", false, false).getIntValue() });
    }
    if (sizes.empty())
        sizes = { { 1258, 799 } };

    auto proc = std::make_unique<XenakisProcessor>();
    proc->prepareToPlay (48000, 512);
    auto& s = proc->session;
    s.settings().set ("ui_size", "medium");
    s.settings().set ("review_split", "0.47");
    s.setBaseDir (juce::File::getSpecialLocation (juce::File::tempDirectory));
    std::unique_ptr<juce::AudioProcessorEditor> ed (proc->createEditor());
    auto* editor = dynamic_cast<XenakisEditor*> (ed.get());
    editor->setSize (sizes[0].first, sizes[0].second);
    editor->setVisible (true);
    pump (200);
    auto& view = editor->getView();
    view.setTheme (false);
    save (*editor, outDir.getChildFile ("0_empty_light.png"));

    s.addFiles ({ juce::String (argv[2]) });
    if (! waitIdle (s))
        return fail ("loading timed out");
    if (s.stems.empty())
        return fail ("no stems loaded");
    save (*editor, outDir.getChildFile ("1_load_light.png"));
    s.processAll();
    if (! waitIdle (s))
        return fail ("processing timed out");
    std::printf ("chops: %zu  bpm: %.2f  page: %d\n", s.chops.size(), s.songGrid ? s.songGrid->bpm : 0.0, view.currentPage());
    if (s.chops.empty())
        return fail ("no chops");
    if (view.currentPage() != 1)
        return fail ("did not switch to Review after processing");
    // approve a few, select one, fake a playhead
    for (size_t i = 0; i < 4 && i < s.chops.size(); ++i)
        s.setApproved (s.chops[i].id, true);
    auto& rv = view.review();
    const int pick = s.chops[juce::jmin<size_t> (8, s.chops.size() - 1)].id;
    rv.select (pick, true);
    pump (400);
    rv.tick();

    for (size_t k = 0; k < sizes.size(); ++k)
    {
        editor->setSize (sizes[k].first, sizes[k].second);
        pump (100);
        const auto tag = juce::String (sizes[k].first) + "x" + juce::String (sizes[k].second);
        view.setTheme (false);
        pump (50);
        save (*editor, outDir.getChildFile ("2_review_light_" + tag + ".png"));
        view.setTheme (true);
        pump (50);
        save (*editor, outDir.getChildFile ("3_review_dark_" + tag + ".png"));
        view.go (0);
        pump (50);
        save (*editor, outDir.getChildFile ("4_load_dark_" + tag + ".png"));
        view.go (1);
        pump (50);
    }
    // ---- the editor: trim + undo / redo, clone, your own chop, fades
    {
        auto* c = s.chopById (pick);
        const int s0 = c->start, e0 = c->end, n0 = (int) s.chops.size();
        s.setTrim (pick, s0 + 200, e0 - 200);
        if (s.chopById (pick)->start != s0 + 200)
            return fail ("trim did not apply");
        s.undo();
        if (s.chopById (pick)->start != s0)
            return fail ("undo did not restore the trim");
        s.redo();
        s.resetTrim (pick);
        if (s.chopById (pick)->start != s0 || s.chopById (pick)->end != e0)
            return fail ("reset trim");
        rv.select (pick, false);
        rv.cloneSelected();
        if ((int) s.chops.size() != n0 + 1)
            return fail ("clone");
        const int stemId = s.chopById (pick)->stemId;
        s.previewStem (stemId, s.chopById (pick)->end + 2000);
        pump (300);
        rv.tick();
        rv.newChopHere();
        if ((int) s.chops.size() != n0 + 2 || s.chopById (rv.selected)->origin != "manual")
            return fail ("new chop");
        std::printf ("editor: clone + own chop ok (%zu chops), own chop %d..%d\n", s.chops.size(),
                     s.chopById (rv.selected)->start, s.chopById (rv.selected)->end);
        s.setFades (rv.selected, 5.0, 120.0);
        s.setGain (rv.selected, -6.0);
        pump (100);
        view.setTheme (false);
        editor->setSize (sizes[0].first, sizes[0].second);
        pump (100);
        save (*editor, outDir.getChildFile ("7_editor_own_chop.png"));
        s.undo();
        s.undo();
        s.undo();
        s.undo();
        if ((int) s.chops.size() != n0)
            return fail ("undo back to the AI chops");
        s.stopPreview();
        rv.select (pick, false);
    }
    // drag-out file
    auto f = s.renderForDrag (pick);
    std::printf ("drag file: %s (%lld bytes)\n", f.getFileName().toRawUTF8(), (long long) f.getSize());
    if (! f.existsAsFile() || f.getSize() < 100)
        return fail ("drag file not written");
    // editor closes and reopens without losing anything
    ed.reset();
    pump (100);
    ed.reset (proc->createEditor());
    editor = dynamic_cast<XenakisEditor*> (ed.get());
    editor->setSize (sizes[0].first, sizes[0].second);
    pump (200);
    std::printf ("after reopening: %zu chops, page %d\n", s.chops.size(), editor->getView().currentPage());
    if (editor->getView().currentPage() != 1)
        return fail ("reopened editor did not show Review");
    // export only what's approved (4 chops); the rest are skipped
    s.outputFolder().deleteRecursively();
    const int a0 = s.approvedCount();
    if (s.toExportCount() != a0 || a0 == 0)
        return fail ("nothing to export with chops approved");
    editor->getView().setTheme (false);
    pump (100);
    save (*editor, outDir.getChildFile ("4b_review_partial.png"));
    s.exportAll();
    if (! waitIdle (s))
        return fail ("export timed out");
    pump (100);
    std::printf ("exported %d of %zu chops to %s\n", s.lastExportFiles.size(), s.chops.size(), s.lastExportFolder.getFullPathName().toRawUTF8());
    if (s.lastExportFiles.size() != a0 || s.toExportCount() != 0)
        return fail ("partial export count mismatch");
    if (editor->getView().currentPage() != 2)
        return fail ("did not show Export after exporting");
    save (*editor, outDir.getChildFile ("5_export_light.png"));
    // approve two more and export again: only the two new ones are added
    editor->getView().go (1);
    int added = 0;
    for (auto& c : s.chops)
        if (! c.approved && added < 2)
        {
            s.setApproved (c.id, true);
            ++added;
        }
    pump (50);
    save (*editor, outDir.getChildFile ("5b_review_after_export.png"));
    s.exportAll();
    if (! waitIdle (s))
        return fail ("second export timed out");
    pump (100);
    const int onDisk = s.lastExportFolder.getNumberOfChildFiles (juce::File::findFiles, "*.wav");
    std::printf ("second export: %d new, %d in the folder\n", s.lastExportFiles.size(), onDisk);
    if (s.lastExportFiles.size() != added || onDisk != a0 + added)
        return fail ("second export repeated or lost files");
    if (editor->getView().currentPage() != 2)
        return fail ("did not show Export after the second export");
    // then everything else
    s.approveAll();
    s.exportAll();
    if (! waitIdle (s))
        return fail ("export timed out");
    if (s.lastExportFolder.getNumberOfChildFiles (juce::File::findFiles, "*.wav") != (int) s.chops.size())
        return fail ("export count mismatch");
    // small UI size
    editor->setUiSize ("small");
    editor->getView().go (1);
    pump (100);
    save (*editor, outDir.getChildFile ("6_review_small.png"));
    editor->setUiSize ("medium");
    s.lastExportFolder.deleteRecursively();
    ed.reset();
    proc.reset();
    std::printf ("snapshot ok\n");
    return 0;
}
