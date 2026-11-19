// Fluid motion: damped springs instead of timers and easing curves (port of
// multicrack/ui/motion.py). Setting a new target redirects a spring from where it is now, at its
// current speed, so nothing jumps and every motion can be interrupted. One shared clock on the
// message thread drives every spring and only runs while something moves (never the audio
// thread).
#pragma once

#include "ui/Skin.h"

#include <functional>
#include <vector>

namespace xk::ui::motion
{

struct Preset { double response, damping; };   // response ~ seconds to settle; damping 1 = no overshoot
inline constexpr Preset UI { 0.38, 0.78 };     // panels, values
inline constexpr Preset PRESS { 0.10, 1.0 };   // button press
inline constexpr Preset FADE { 0.475, 1.0 };   // fades, quiet transitions
inline constexpr Preset SCROLL { 0.42, 1.0 };  // scrolling settle

bool reducedMotion();                           // Windows "Animation effects" off

class Spring
{
public:
    explicit Spring (double value = 0.0, Preset p = UI, juce::Component* owner = nullptr);
    ~Spring();
    Spring (const Spring&) = delete;
    Spring& operator= (const Spring&) = delete;

    void to (double target);                    // head there from here, keeping the speed
    void jump (double value);                   // be there now
    void setOwner (juce::Component* c) { owner = c; }
    void setPreset (Preset p) { preset = p; }
    double get() const { return value; }
    float getf() const { return (float) value; }
    double target() const { return goal; }
    bool moving() const { return value != goal || velocity != 0.0; }
    std::function<void (double)> onChange;

    bool advance (double dt);                   // (the clock calls this)

private:
    void changed();
    double value, goal, velocity = 0.0, acc = 0.0, span = 1.0;
    Preset preset;
    juce::Component::SafePointer<juce::Component> owner;
};

// animate when the component is on screen, otherwise just be there
inline void move (Spring& s, juce::Component& c, double v)
{
    if (c.isShowing())
        s.to (v);
    else
        s.jump (v);
}

// follow a state that is read while painting (e.g. a toggle set from code): the first time it
// is simply there, after that every change glides
inline void follow (Spring& s, bool& seen, double v)
{
    if (! seen)
    {
        seen = true;
        if (s.target() != v || s.moving())
            s.jump (v);
    }
    else if (v != s.target())
        s.to (v);
}

inline float mix (float a, float b, float t) { return a + (b - a) * t; }
inline juce::Colour mix (juce::Colour a, juce::Colour b, float t) { return a.interpolatedWith (b, juce::jlimit (0.0f, 1.0f, t)); }

} // namespace xk::ui::motion
