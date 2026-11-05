cmake_minimum_required(VERSION 3.22)

# Xenakis as a VST3 / CLAP plug-in (plus a standalone build used for testing).
project(XenakisPlugin VERSION 1.0.0 LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)
if(MSVC)
    # one runtime for everything that ends up inside the plug-in; sources are UTF-8
    set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
    add_compile_options(/utf-8)
endif()

if(NOT DEFINED XENAKIS_VERSION)
    set(XENAKIS_VERSION "1.0.0")
endif()

include(FetchContent)
FetchContent_Declare(JUCE
    GIT_REPOSITORY https://github.com/juce-framework/JUCE.git
    GIT_TAG 9.0.5
    GIT_SHALLOW TRUE)
FetchContent_MakeAvailable(JUCE)

FetchContent_Declare(clap_juce_extensions
    GIT_REPOSITORY https://github.com/free-audio/clap-juce-extensions.git
    GIT_TAG 7adee3a1bd4684d4caa5601100e364abccff4b4d
    GIT_SUBMODULES_RECURSE TRUE)
FetchContent_MakeAvailable(clap_juce_extensions)

# ----------------------------------------------------------------- engine
# Pure C++ (no JUCE): analysis, tempo, chopping engines, naming, rendering.
add_library(xenakis_engine STATIC
    src/engine/Fft.cpp
    src/engine/Dsp.cpp
    src/engine/Tempo.cpp
    src/engine/Classify.cpp
    src/engine/Engines.cpp
    src/engine/Naming.cpp
    src/engine/Render.cpp
    src/engine/Pipeline.cpp)
target_include_directories(xenakis_engine PUBLIC src)
if(MSVC)
    target_compile_options(xenakis_engine PRIVATE /O2 /fp:fast /W3)
else()
    target_compile_options(xenakis_engine PRIVATE -O2 -Wall -Wno-sign-compare)
endif()

# ----------------------------------------------------------------- assets
juce_add_binary_data(XenakisAssets
    HEADER_NAME XenakisAssets.h
    NAMESPACE XenakisAssets
    SOURCES
        ../assets/fonts/IBMPlexMono-Regular.ttf
        ../assets/fonts/IBMPlexMono-Medium.ttf
        ../assets/fonts/IBMPlexMono-SemiBold.ttf
        ../assets/fonts/IBMPlexMono-Bold.ttf)

# ----------------------------------------------------------------- plug-in
juce_add_plugin(Xenakis
    COMPANY_NAME "Xenakis"
    COMPANY_WEBSITE "https://github.com/jehfslaps/multicrack"
    BUNDLE_ID com.xenakis.plugin
    PLUGIN_MANUFACTURER_CODE Xnks
    PLUGIN_CODE Xnk1
    FORMATS VST3 Standalone
    PRODUCT_NAME "Xenakis"
    VERSION ${XENAKIS_VERSION}
    IS_SYNTH FALSE
    NEEDS_MIDI_INPUT FALSE
    NEEDS_MIDI_OUTPUT FALSE
    IS_MIDI_EFFECT FALSE
    EDITOR_WANTS_KEYBOARD_FOCUS TRUE
    COPY_PLUGIN_AFTER_BUILD FALSE
    VST3_CATEGORIES Fx Tools
    ICON_BIG ../assets/Xenakis.png)

clap_juce_extensions_plugin(TARGET Xenakis
    CLAP_ID "com.xenakis.plugin"
    CLAP_FEATURES audio-effect utility stereo)

target_sources(Xenakis PRIVATE
    src/PluginProcessor.cpp
    src/PluginEditor.cpp
    src/Session.cpp
    src/PreviewPlayer.cpp
    src/AudioLoader.cpp
    src/ui/Skin.cpp
    src/ui/Widgets.cpp
    src/ui/Waveforms.cpp
    src/ui/LoadPage.cpp
    src/ui/ReviewPage.cpp
    src/ui/ExportPage.cpp)

target_compile_definitions(Xenakis PUBLIC
    JUCE_WEB_BROWSER=0
    JUCE_USE_CURL=0
    JUCE_VST3_CAN_REPLACE_VST2=0
    JUCE_DISPLAY_SPLASH_SCREEN=0
    JUCE_USE_MP3AUDIOFORMAT=1
    JUCE_USE_WINDOWS_MEDIA_FORMAT=1
    JUCE_MODAL_LOOPS_PERMITTED=0
    XENAKIS_VERSION="${XENAKIS_VERSION}")

target_link_libraries(Xenakis
    PRIVATE
        xenakis_engine
        XenakisAssets
        juce::juce_audio_utils
        juce::juce_audio_formats
        juce::juce_gui_extra
    PUBLIC
        juce::juce_recommended_config_flags
        juce::juce_recommended_lto_flags
        juce::juce_recommended_warning_flags)

# ------------------------------------------------------------- engine CLI
# Runs the engine on a folder of stems and prints what it finds (used to compare with the
# Python engine and in CI).
juce_add_console_app(xk_engine_cli PRODUCT_NAME "xk_engine_cli")
target_sources(xk_engine_cli PRIVATE tools/EngineCli.cpp src/AudioLoader.cpp)
target_compile_definitions(xk_engine_cli PRIVATE JUCE_WEB_BROWSER=0 JUCE_USE_CURL=0
    JUCE_USE_MP3AUDIOFORMAT=1 JUCE_USE_WINDOWS_MEDIA_FORMAT=1 XENAKIS_CLI=1)
target_link_libraries(xk_engine_cli PRIVATE xenakis_engine juce::juce_audio_formats
    juce::juce_recommended_config_flags)

# ------------------------------------------------------------ snapshot tool
# Loads stems into the real plug-in UI and saves PNGs of each page (used for screenshots).
juce_add_console_app(xk_snapshot PRODUCT_NAME "xk_snapshot")
target_sources(xk_snapshot PRIVATE tools/Snapshot.cpp
    src/PluginProcessor.cpp src/PluginEditor.cpp src/Session.cpp src/PreviewPlayer.cpp src/AudioLoader.cpp
    src/ui/Skin.cpp src/ui/Widgets.cpp src/ui/Waveforms.cpp src/ui/LoadPage.cpp src/ui/ReviewPage.cpp)
target_include_directories(xk_snapshot PRIVATE src)
target_compile_definitions(xk_snapshot PRIVATE JUCE_WEB_BROWSER=0 JUCE_USE_CURL=0 JUCE_USE_MP3AUDIOFORMAT=1
    JUCE_MODAL_LOOPS_PERMITTED=1 XENAKIS_VERSION="${XENAKIS_VERSION}" JucePlugin_Name="Xenakis")
target_link_libraries(xk_snapshot PRIVATE xenakis_engine XenakisAssets juce::juce_audio_utils
    juce::juce_audio_formats juce::juce_gui_extra juce::juce_recommended_config_flags)
