#include "ui/Motion.h"

#if JUCE_WINDOWS
extern "C" __declspec (dllimport) int __stdcall SystemParametersInfoW (unsigned int, unsigned int, void*, unsigned int);
#endif

namespace xk::ui::motion
{

bool reducedMotion()
{
    if (juce::SystemStats::getEnvironmentVariable ("XENAKIS_REDUCED_MOTION", "0") != "0")
        return true;
#if JUCE_WINDOWS
    int on = 1;
    if (SystemParametersInfoW (0x1042 /* SPI_GETCLIENTAREAANIMATION */, 0, &on, 0))
        return on == 0;
#endif
    return false;
}

namespace
{
constexpr double STEP = 1.0 / 240.0;   // integrate at 240 Hz whatever the screen rate

class Clock : private juce::Timer, public juce::DeletedAtShutdown
{
public:
    static Clock& get()
    {
        if (instance == nullptr)
            instance = new Clock();
        return *instance;
    }
    static void forget (Spring* s)
    {
        if (instance != nullptr)
            instance->remove (s);
    }
    ~Clock() override { instance = nullptr; }

    void add (Spring* s)
    {
        if (std::find (live.begin(), live.end(), s) == live.end())
            live.push_back (s);
        if (! isTimerRunning())
        {
            last = juce::Time::getMillisecondCounterHiRes();
            startTimerHz (120);
        }
    }
    void remove (Spring* s)
    {
        live.erase (std::remove (live.begin(), live.end(), s), live.end());
        if (live.empty())
            stopTimer();
    }
    bool reduced()
    {
        const auto now = juce::Time::getMillisecondCounter();
        if (now - checked > 2000 || checked == 0)    // the user may change the Windows setting
        {
            checked = now;
            isReduced = reducedMotion();
        }
        return isReduced;
    }

private:
    void timerCallback() override
    {
        const double now = juce::Time::getMillisecondCounterHiRes();
        const double dt = juce::jmin (0.05, (now - last) / 1000.0);   // a stall never becomes a jump
        last = now;
        auto copy = live;
        for (auto* s : copy)
            if (std::find (live.begin(), live.end(), s) != live.end() && s->advance (dt))
                remove (s);
    }
    std::vector<Spring*> live;
    double last = 0;
    juce::uint32 checked = 0;
    bool isReduced = false;
    static inline Clock* instance = nullptr;
};
} // namespace

Spring::Spring (double v, Preset p, juce::Component* o) : value (v), goal (v), preset (p), owner (o) {}

Spring::~Spring() { Clock::forget (this); }

void Spring::to (double t)
{
    if (t == goal && ! moving())
        return;
    span = juce::jmax (std::abs (t - value), std::abs (velocity) * preset.response, 1e-9);
    goal = t;
    if (Clock::get().reduced())
    {
        jump (t);
        return;
    }
    Clock::get().add (this);
}

void Spring::jump (double v)
{
    Clock::forget (this);
    value = goal = v;
    velocity = 0.0;
    changed();
}

void Spring::changed()
{
    if (onChange)
        onChange (value);
    if (owner != nullptr)
        owner->repaint();
}

bool Spring::advance (double dt)
{
    const double w = juce::MathConstants<double>::twoPi / juce::jmax (1e-3, preset.response), z = preset.damping;
    acc += dt;
    while (acc >= STEP)
    {
        acc -= STEP;
        const double a = -w * w * (value - goal) - 2 * z * w * velocity;
        velocity += a * STEP;
        value += velocity * STEP;
    }
    const double eps = span * 1e-3;
    if (std::abs (value - goal) < eps && std::abs (velocity) < eps * w)
    {
        value = goal;
        velocity = 0.0;
        changed();
        return true;
    }
    changed();
    return false;
}

} // namespace xk::ui::motion
