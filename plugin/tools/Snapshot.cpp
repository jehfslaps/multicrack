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
    // export
    s.approveAll();
    s.exportAll();
    if (! waitIdle (s))
        return fail ("export timed out");
    std::printf ("exported %d files to %s\n", s.lastExportFiles.size(), s.lastExportFolder.getFullPathName().toRawUTF8());
    if (s.lastExportFiles.size() != (int) s.chops.size())
        return fail ("export count mismatch");
    editor->getView().setTheme (false);
    pump (100);
    save (*editor, outDir.getChildFile ("5_export_light.png"));
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
