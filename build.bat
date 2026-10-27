@echo off
rem ===========================================================================
rem  Exonerated - build Deathrow for PC from your own copy of the game.
rem
rem    1. Put your game in the "game" folder next to this file: either the
rem       disc image (Deathrow.iso) or its files (default.xbe and the data
rem       folder). Only the North American release (title 55530004, v3) works.
rem    2. Double-click build.bat (or run it from a command prompt).
rem    3. When it finishes, run "Play Exonerated.bat".
rem
rem  Nothing from the game is included in this project or uploaded anywhere:
rem  the game's code is lifted to C and compiled here, on your machine.
rem
rem    build.bat          build (lifts the game code only the first time)
rem    build.bat relift   lift the game code again, then build
rem ===========================================================================
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
set "ROOT=%CD%"
set "ASSETS=%ROOT%\game"
set "TOOLKIT=%ROOT%\..\xboxrecomp"
set "TOOLKIT_URL=https://github.com/sp00nznet/xboxrecomp.git"
set "TOOLKIT_TAG=v0.16.0"
set "XBE_SHA1=34ef43c83ffa6860019edc4fc183241107a11ed2"
set "GEN=%ROOT%\src\recomp\gen"
set "RELIFT=0"
if /i "%~1"=="relift" set "RELIFT=1"

echo.
echo  Exonerated - Deathrow PC build
echo  ==============================
echo.

rem ---- [1/6] tools ----------------------------------------------------------
echo [1/6] Checking tools...
set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if not exist "%VSWHERE%" goto :novs
set "VSDIR="
for /f "usebackq delims=" %%i in (`"%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "VSDIR=%%i"
if not defined VSDIR goto :novs
call "%VSDIR%\Common7\Tools\VsDevCmd.bat" -arch=x64 -host_arch=x64 >nul 2>nul
if errorlevel 1 goto :novs
where cmake >nul 2>nul || goto :nocmake

set "PY="
where py >nul 2>nul && (py -3 -c "import sys" >nul 2>nul && set "PY=py -3")
if not defined PY (where python >nul 2>nul && (python -c "import sys; sys.exit(sys.version_info < (3, 8))" >nul 2>nul && set "PY=python"))
if not defined PY goto :nopython
%PY% -c "import capstone" >nul 2>nul
if errorlevel 1 (
    echo       Installing the Python package "capstone" ^(the disassembler^)...
    %PY% -m pip install --user capstone || goto :nocapstone
)
where git >nul 2>nul || goto :nogit
echo       Visual Studio: %VSDIR%
echo       Python: %PY%

rem ---- [2/6] toolkit --------------------------------------------------------
echo [2/6] Getting the xboxrecomp toolkit...
if exist "%TOOLKIT%\CMakeLists.txt" (
    echo       Using the existing toolkit at %TOOLKIT%
) else (
    git -c advice.detachedHead=false clone --quiet --branch %TOOLKIT_TAG% "%TOOLKIT_URL%" "%TOOLKIT%" 2>nul || goto :notoolkit
    git -C "%TOOLKIT%" apply --whitespace=nowarn "%ROOT%\patches\xboxrecomp-local.patch" || goto :nopatch
    echo       Toolkit %TOOLKIT_TAG% cloned and Exonerated's patch applied.
)

rem ---- [3/6] game files -----------------------------------------------------
echo [3/6] Looking for your game in "%ASSETS%"...
if not exist "%ASSETS%" mkdir "%ASSETS%"
if not exist "%ASSETS%\default.xbe" (
    set "ISO="
    for %%f in ("%ASSETS%\*.iso") do if not defined ISO set "ISO=%%~ff"
    if not defined ISO goto :nogame
    echo       Unpacking !ISO! ...
    pushd "%TOOLKIT%"
    %PY% -m tools.xiso unpack "!ISO!" -o "%ASSETS%"
    set "RC=!errorlevel!"
    popd
    if not "!RC!"=="0" goto :badiso
    if not exist "%ASSETS%\default.xbe" goto :badiso
)
for /f "usebackq delims=" %%h in (`%PY% -c "import hashlib,sys;print(hashlib.sha1(open(sys.argv[1],'rb').read()).hexdigest())" "%ASSETS%\default.xbe"`) do set "SHA1=%%h"
if /i not "%SHA1%"=="%XBE_SHA1%" goto :wronggame
echo       Deathrow (North America, v3) found.

rem ---- [4/6] lift -----------------------------------------------------------
if "%RELIFT%"=="0" if exist "%GEN%\recomp_funcs.h" (
    echo [4/6] Game code already lifted ^(run "build.bat relift" to redo it^).
    goto :build
)
echo [4/6] Lifting the game code to C. This takes several minutes...
pushd "%TOOLKIT%"
%PY% -m tools.disasm "%ASSETS%\default.xbe" --text-only --extra-sections D3DX,XGRPH,DSOUND,WMADECXM,WMADEC,WMVDEC,XNET,D3D,XPP,DOLBY --seed-functions "%ROOT%\seeds\seed_functions.json" >nul || goto :liftfail
%PY% -m tools.func_id "%ASSETS%\default.xbe" >nul || goto :liftfail
%PY% -m tools.abi_analysis "%ASSETS%\default.xbe" >nul || goto :liftfail
%PY% -m tools.recomp "%ASSETS%\default.xbe" --all --split 250 --gen-dir "%GEN%" --exclude-manual "%ROOT%\src\recomp_manual.c" || goto :liftfail
popd
%PY% "%ROOT%\tools\stub_trace.py" || goto :liftfail

rem ---- [5/6] build ----------------------------------------------------------
:build
echo [5/6] Compiling. The first build takes a while...
if not exist "%ROOT%\build\CMakeCache.txt" (
    cmake -S "%ROOT%" -B "%ROOT%\build" -A x64 >"%ROOT%\build-configure.log" 2>&1 || goto :cmakefail
)
cmake --build "%ROOT%\build" --config Release >"%ROOT%\build.log" 2>&1
if errorlevel 1 goto :buildfail
if not exist "%ROOT%\build\Release\deathrow_recomp.exe" goto :buildfail

rem ---- [6/6] launcher -------------------------------------------------------
echo [6/6] Writing "Play Exonerated.bat"...
(
    echo @echo off
    echo rem Starts Exonerated. The run's log goes to exonerated.log.
    echo cd /d "%%~dp0"
    echo "build\Release\deathrow_recomp.exe" ^> exonerated.log 2^>^&1
) > "%ROOT%\Play Exonerated.bat"

echo.
echo  Done. Run "Play Exonerated.bat" to play.
echo.
if not defined CI pause
exit /b 0

rem ---- failures -------------------------------------------------------------
:novs
echo.
echo  Visual Studio's C++ build tools were not found.
echo  Install "Build Tools for Visual Studio 2022" (free) from
echo    https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022
echo  and tick "Desktop development with C++" (it includes CMake). Then run build.bat again.
goto :fail
:nocmake
echo.
echo  CMake was not found. In the Visual Studio Installer, add "C++ CMake tools for
echo  Windows" to your Build Tools, or install CMake from https://cmake.org/download/
goto :fail
:nopython
echo.
echo  Python 3.8 or newer was not found. Install it from https://www.python.org/downloads/
echo  and tick "Add python.exe to PATH" in the installer.
goto :fail
:nocapstone
echo.
echo  Could not install the Python package "capstone". Try: %PY% -m pip install capstone
goto :fail
:nogit
echo.
echo  Git was not found. Install it from https://git-scm.com/download/win
goto :fail
:notoolkit
echo.
echo  Could not download the xboxrecomp toolkit from %TOOLKIT_URL%.
echo  Check your internet connection and try again.
goto :fail
:nopatch
echo.
echo  The toolkit was downloaded, but Exonerated's patch did not apply. Delete
echo  "%TOOLKIT%" and run build.bat again; if it fails again, please report it.
goto :fail
:nogame
echo.
echo  No game found. Put Deathrow's disc image (*.iso) or its files
echo  (default.xbe and the data folder) in:
echo    %ASSETS%
goto :fail
:badiso
echo.
echo  The disc image could not be unpacked, or has no default.xbe.
echo  Use an Xbox disc image (XISO) of Deathrow, or put the extracted files in the game folder.
goto :fail
:wronggame
echo.
echo  game\default.xbe is not the supported Deathrow release.
echo    expected SHA-1 %XBE_SHA1%
echo    found    %SHA1%
echo  Only the North American release (title 55530004, version 3) is supported.
goto :fail
:liftfail
popd 2>nul
echo.
echo  Lifting the game code failed. See the messages above.
goto :fail
:cmakefail
echo.
echo  CMake could not configure the build. See build-configure.log.
goto :fail
:buildfail
echo.
echo  The build failed. The errors are in build.log; the lines with "error" are:
findstr /c:" error " "%ROOT%\build.log"
goto :fail
:fail
echo.
echo  BUILD FAILED
if not defined CI pause
exit /b 1
