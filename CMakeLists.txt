cmake_minimum_required(VERSION 3.20)

# ============================================================================
# YOUR_GAME_NAME - Static Recompilation
#
# Copy this template to your game project root and customize:
#   1. Change the project name below
#   2. Set XBOXRECOMP_DIR to where you cloned xboxrecomp
#   3. Adjust source file lists as you add game-specific code
#   4. Add any game-specific compile definitions or link libraries
# ============================================================================

project(deathrow_recomp C)
# add_compile_definitions(RECOMP_ABI_CHECK)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

# Common definitions
add_compile_definitions(
    WIN32_LEAN_AND_MEAN
    NOMINMAX
)

# ── xboxrecomp toolkit ──────────────────────────────────────────
#
# Option A: xboxrecomp as a subdirectory (simplest)
#   Place xboxrecomp/ next to your game project and use a relative path.
#
# Option B: find_package (if you install xboxrecomp system-wide)
#   find_package(xboxrecomp REQUIRED)
#
# Adjust this path to point to your xboxrecomp clone:
set(XBOXRECOMP_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../xboxrecomp" CACHE PATH
    "Path to the xboxrecomp toolkit root directory")

# Add xboxrecomp as a subdirectory -- this builds all 6 runtime libraries
# and provides the 'xboxrecomp' umbrella target to link against.
add_subdirectory(${XBOXRECOMP_DIR} ${CMAKE_BINARY_DIR}/xboxrecomp)

# ── Recompiled game executable ──────────────────────────────────

# Collect generated recompiled code.
# The recomp pipeline outputs files into src/recomp/gen/.
# With --split 1000, you get gen_0000.c, gen_0001.c, etc.
# CONFIGURE_DEPENDS so re-running the recompiler picks up added/removed files
# without a manual re-configure. A plain GLOB is evaluated once at configure
# time, so a newly generated file (an extra chunk, recomp_stubs_unresolved.c)
# is silently left out of the build and shows up as unresolved externals.
file(GLOB RECOMP_GEN_SOURCES CONFIGURE_DEPENDS "src/recomp/gen/*.c")

# Core game sources
set(GAME_SOURCES
    src/main.c
    src/game_check.c
    # First-run import of the player's game, and the disc-image reader it uses.
    src/game_import.c
    src/xiso.c
    src/recomp_manual.c
    # Add game-specific sources here, e.g.:
    # src/asset_loader.c
    # src/custom_renderer.c
)

# The recomp pipeline also generates a dispatch header and function declarations.
# These are included by the generated .c files:
#   src/recomp/gen/recomp_funcs.h    - extern declarations for all recompiled functions
#   src/recomp/recomp_dispatch.h     - binary search dispatch table
#   src/recomp/recomp_types.h        - register model, ICALL macros, MEM helpers

add_executable(${PROJECT_NAME} WIN32
    ${GAME_SOURCES}
    ${RECOMP_GEN_SOURCES}
)

# Link against the xboxrecomp umbrella target (all 6 runtime libraries)
target_link_libraries(${PROJECT_NAME} PRIVATE xboxrecomp)

# Include paths for generated recomp headers
target_include_directories(${PROJECT_NAME} PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/src
    ${CMAKE_CURRENT_SOURCE_DIR}/src/recomp
    ${XBOXRECOMP_DIR}/include
)

# Windows SDK libraries needed at link time
target_link_libraries(${PROJECT_NAME} PRIVATE
    d3d11
    dxgi
    dxguid
    xinput
    winmm
    # SHA-1 of default.xbe for the game check (src/game_check.c).
    bcrypt
    # Lets the fault handler resolve the host RIP back to the generated
    # function's symbol, i.e. to the guest function that faulted.
    dbghelp
)

# MSVC-specific: large address aware, increase section limit for big generated files
if(MSVC)
    target_link_options(${PROJECT_NAME} PRIVATE
        /LARGEADDRESSAWARE
    )
    # The generated code files can be very large. Increase object file section limit.
    target_compile_options(${PROJECT_NAME} PRIVATE /bigobj /MP4)
endif()

# ── Game-specific additions ─────────────────────────────────────
#
# Add any game-specific libraries, loaders, or custom renderers below.
# Examples:
#
# # Custom texture loader for your game's format
# target_sources(${PROJECT_NAME} PRIVATE src/texture_loader.c)
#
# # If your game uses RenderWare, you may need a RW bridge layer
# target_sources(${PROJECT_NAME} PRIVATE src/rw_bridge.c)
#
# # Additional compile definitions for debugging
# target_compile_definitions(${PROJECT_NAME} PRIVATE
#     ENABLE_ICALL_TRACE=1
#     VERBOSE_KERNEL_LOG=1
# )

# sampling profiler (off unless RECOMP_PROF=1)
target_sources(deathrow_recomp PRIVATE src/prof_sampler.c)
target_link_options(deathrow_recomp PRIVATE /MAP)

# The window's title prefix and its settings file (exonerated.ini), see
# xboxrecomp/src/video/fb_present.c.
target_compile_definitions(xbox_video PRIVATE RECOMP_APP_NAME="Exonerated")

# Last place main.c looks for the game files (after RECOMP_GAME_DIR and the
# assets folders): the toolkit's game_files, where regen.sh reads the XBE.
# DR_RELEASE: a downloadable build (tools/make_release.py). It looks for the
# game only where a player has it -- next to the exe, or a folder they
# picked -- and carries no path from the machine that built it.
option(DR_RELEASE "Build for a downloadable release" OFF)
if(DR_RELEASE)
    target_compile_definitions(deathrow_recomp PRIVATE DR_RELEASE=1)
else()
    file(TO_NATIVE_PATH "${XBOXRECOMP_DIR}/game_files" DR_FALLBACK_GAME_DIR_NATIVE)
    string(REPLACE "\\" "\\\\" DR_FALLBACK_GAME_DIR_C "${DR_FALLBACK_GAME_DIR_NATIVE}")
    target_compile_definitions(deathrow_recomp PRIVATE
        DR_FALLBACK_GAME_DIR="${DR_FALLBACK_GAME_DIR_C}")
endif()

# The overlay's logo and the launcher's title card, embedded in the exe
# (RECOMP_OVERLAY_LOGO, RECOMP_TITLE_CARD, RECOMP_TITLE_MARK). The .rc is
# configured with absolute paths so rc.exe finds the PNGs from any folder.
set(DR_OVERLAY_LOGO "${CMAKE_CURRENT_SOURCE_DIR}/assets/exonerated-logo.png")
set(DR_TITLE_CARD "${CMAKE_CURRENT_SOURCE_DIR}/assets/exonerated-wordmark.png")
set(DR_TITLE_MARK "${CMAKE_CURRENT_SOURCE_DIR}/assets/asukaneo-mark.png")
# The version the launcher shows (tools/make_release.py passes it).
set(DR_VERSION "dev" CACHE STRING "Version shown on the launcher")
target_compile_definitions(deathrow_recomp PRIVATE DR_VERSION="${DR_VERSION}")
# The exe's icon and the settings menu's theme (RECOMP_ICON, RECOMP_THEME),
# and its version in the four numbers a VERSIONINFO takes: v0.9.2-beta is
# 0,9,2,0 and "dev" is 0,0,0,0.
set(DR_ICON "${CMAKE_CURRENT_SOURCE_DIR}/assets/exonerated.ico")
set(DR_THEME "${CMAKE_CURRENT_SOURCE_DIR}/assets/exonerated-theme.txt")
set(DR_VERSION_RC "0,0,0,0")
if(DR_VERSION MATCHES "([0-9]+)\\.([0-9]+)\\.([0-9]+)")
    set(DR_VERSION_RC "${CMAKE_MATCH_1},${CMAKE_MATCH_2},${CMAKE_MATCH_3},0")
endif()
configure_file(src/exonerated.rc.in ${CMAKE_CURRENT_BINARY_DIR}/exonerated.rc @ONLY)
target_sources(deathrow_recomp PRIVATE ${CMAKE_CURRENT_BINARY_DIR}/exonerated.rc)
