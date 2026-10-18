/*
 * First-run game import (game_import.h).
 *
 * A downloaded Exonerated holds no game files. The first time it starts, or
 * when a disc image or default.xbe is dropped onto it, it asks for the
 * player's own Deathrow and checks it *before* copying anything: a disc
 * image's default.xbe is read straight out of the image and hashed, so a
 * wrong release is refused in seconds rather than after a gigabyte copy.
 *
 * A disc image is unpacked into "game.partial" and renamed to "game" only
 * when it is whole, so an interrupted copy is never mistaken for a game.
 */
#include <windows.h>
#include <commctrl.h>
#include <commdlg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "game_check.h"
#include "game_import.h"
#include "xiso.h"

#pragma comment(lib, "comctl32.lib")
#pragma comment(lib, "comdlg32.lib")

#define TITLE "Exonerated"

static const char RELEASE[] =
    "Deathrow for the original Xbox, North American release (version 3)";

/* An error, in a box for the player and in the log for a report. */
static void error_box(const char *msg)
{
    fprintf(stderr, "[IMPORT] %s\n", msg);
    MessageBoxA(NULL, msg, TITLE, MB_ICONERROR);
}

static void ini_path(const char *exe_dir, char *out, size_t n)
{
    snprintf(out, n, "%s\\exonerated.ini", exe_dir);
}

void dr_game_import_remembered(const char *exe_dir, char *dir, size_t n)
{
    char ini[MAX_PATH];
    ini_path(exe_dir, ini, sizeof ini);
    GetPrivateProfileStringA("game", "dir", "", dir, (DWORD)n, ini);
}

static int ends_with(const char *s, const char *tail)
{
    size_t a = strlen(s), b = strlen(tail);
    return a >= b && !_stricmp(s + a - b, tail);
}

static void *read_file(const char *path, size_t *size)
{
    HANDLE f = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    LARGE_INTEGER sz;
    void *buf = NULL;
    DWORD got = 0;

    *size = 0;
    if (f == INVALID_HANDLE_VALUE)
        return NULL;
    if (GetFileSizeEx(f, &sz) && sz.QuadPart > 0 && sz.QuadPart < (64LL << 20)
        && (buf = malloc((size_t)sz.QuadPart)) != NULL
        && ReadFile(f, buf, (DWORD)sz.QuadPart, &got, NULL) && got == (DWORD)sz.QuadPart)
        *size = (size_t)sz.QuadPart;
    else {
        free(buf);
        buf = NULL;
    }
    CloseHandle(f);
    return buf;
}

/* The verdict on a default.xbe, as the player should read it. */
static int check_xbe(const void *xbe, size_t size, const char *what)
{
    char found[41], msg[1024];
    if (xbe && dr_game_check(xbe, size, found))
        return 1;
    snprintf(msg, sizeof msg,
             "%s is not the supported version of Deathrow.\n\n"
             "Exonerated works only with %s, because it is built from that "
             "exact program. Other releases and modified copies are refused.\n\n"
             "Found:    %s\nExpected: %s",
             what, RELEASE, xbe && found[0] ? found : "(no readable default.xbe)",
             DR_XBE_SHA1);
    error_box(msg);
    return 0;
}

/* ---- progress window ---------------------------------------------------- */

typedef struct {
    HWND  wnd, bar, text;
    int   cancel;
    int   last_pct;
} Progress;

static LRESULT CALLBACK progress_proc(HWND h, UINT m, WPARAM w, LPARAM l)
{
    if (m == WM_CLOSE) {
        Progress *p = (Progress *)GetWindowLongPtrA(h, GWLP_USERDATA);
        if (p && MessageBoxA(h, "Stop copying the game? You can start again later.",
                             TITLE, MB_YESNO | MB_ICONQUESTION) == IDYES)
            p->cancel = 1;
        return 0;
    }
    return DefWindowProcA(h, m, w, l);
}

static void progress_open(Progress *p, uint64_t total)
{
    INITCOMMONCONTROLSEX icc = { sizeof icc, ICC_PROGRESS_CLASS };
    WNDCLASSA wc;
    RECT r = { 0, 0, 460, 110 };
    char line[160];

    memset(p, 0, sizeof *p);
    p->last_pct = -1;
    InitCommonControlsEx(&icc);
    memset(&wc, 0, sizeof wc);
    wc.lpfnWndProc = progress_proc;
    wc.hInstance = GetModuleHandleA(NULL);
    wc.hCursor = LoadCursorA(NULL, IDC_ARROW);
    wc.hbrBackground = (HBRUSH)(COLOR_BTNFACE + 1);
    wc.lpszClassName = "ExoneratedImport";
    RegisterClassA(&wc);
    AdjustWindowRect(&r, WS_CAPTION | WS_SYSMENU, FALSE);
    p->wnd = CreateWindowA(wc.lpszClassName, TITLE " - setting up your game",
                           WS_CAPTION | WS_SYSMENU | WS_VISIBLE,
                           CW_USEDEFAULT, CW_USEDEFAULT, r.right - r.left, r.bottom - r.top,
                           NULL, NULL, wc.hInstance, NULL);
    if (!p->wnd)
        return;
    SetWindowLongPtrA(p->wnd, GWLP_USERDATA, (LONG_PTR)p);
    snprintf(line, sizeof line, "Copying the game from your disc image (%.1f GB)...",
             (double)total / (1024.0 * 1024.0 * 1024.0));
    p->text = CreateWindowA("STATIC", line, WS_CHILD | WS_VISIBLE,
                            20, 18, 420, 20, p->wnd, NULL, wc.hInstance, NULL);
    p->bar = CreateWindowA(PROGRESS_CLASSA, NULL, WS_CHILD | WS_VISIBLE,
                           20, 50, 420, 22, p->wnd, NULL, wc.hInstance, NULL);
    SendMessageA(p->text, WM_SETFONT, (WPARAM)GetStockObject(DEFAULT_GUI_FONT), TRUE);
    SendMessageA(p->bar, PBM_SETRANGE32, 0, 100);
}

static void pump(void)
{
    MSG msg;
    while (PeekMessageA(&msg, NULL, 0, 0, PM_REMOVE)) {
        TranslateMessage(&msg);
        DispatchMessageA(&msg);
    }
}

static int progress_step(void *ctx, uint64_t done, uint64_t total)
{
    Progress *p = (Progress *)ctx;
    int pct = total ? (int)(done * 100 / total) : 100;
    if (p->bar && pct != p->last_pct) {
        p->last_pct = pct;
        SendMessageA(p->bar, PBM_SETPOS, (WPARAM)pct, 0);
    }
    pump();
    return p->cancel;
}

static void progress_close(Progress *p)
{
    if (p->wnd)
        DestroyWindow(p->wnd);
    pump();
}

/* ---- the two kinds of input --------------------------------------------- */

static int import_iso(const char *exe_dir, const char *iso, char *game_dir, size_t n)
{
    char err[512], msg[1024], dest[MAX_PATH], partial[MAX_PATH], what[MAX_PATH + 16];
    const char *base = strrchr(iso, '\\');
    ULARGE_INTEGER free_bytes;
    Progress p;
    DrXiso *x;
    void *xbe;
    size_t xbe_size;
    uint64_t total;
    int rc;

    snprintf(what, sizeof what, "\"%s\"", base ? base + 1 : iso);
    fprintf(stderr, "[IMPORT] disc image %s\n", iso);
    x = dr_xiso_open(iso, err, sizeof err);
    if (!x) {
        snprintf(msg, sizeof msg, "Could not read %s as an Xbox disc image.\n\n%s", what, err);
        error_box(msg);
        return 0;
    }
    xbe = dr_xiso_read_root_file(x, "default.xbe", &xbe_size);
    if (!check_xbe(xbe, xbe_size, what)) {
        free(xbe);
        dr_xiso_close(x);
        return 0;
    }
    free(xbe);

    total = dr_xiso_total_bytes(x);
    if (GetDiskFreeSpaceExA(exe_dir, &free_bytes, NULL, NULL)
        && free_bytes.QuadPart < total + (64ull << 20)) {
        snprintf(msg, sizeof msg,
                 "Not enough free disk space next to Exonerated to unpack the game.\n\n"
                 "Needed: %.1f GB\nFree:   %.1f GB",
                 (double)total / 1073741824.0, (double)free_bytes.QuadPart / 1073741824.0);
        error_box(msg);
        dr_xiso_close(x);
        return 0;
    }

    snprintf(dest, sizeof dest, "%s\\game", exe_dir);
    snprintf(partial, sizeof partial, "%s\\game.partial", exe_dir);
    progress_open(&p, total);
    rc = dr_xiso_extract_all(x, partial, progress_step, &p, err, sizeof err);
    progress_close(&p);
    dr_xiso_close(x);
    if (rc != 0) {
        if (!p.cancel) {
            snprintf(msg, sizeof msg, "Copying the game stopped.\n\n%s", err);
            error_box(msg);
        }
        return 0;
    }
    RemoveDirectoryA(dest);           /* an empty "game" made by hand; never a full one */
    if (!MoveFileA(partial, dest)) {
        snprintf(msg, sizeof msg,
                 "The game was unpacked to\n%s\nbut could not be renamed to \"game\" "
                 "(error %lu). Is there already a \"game\" folder? Rename it, then "
                 "start Exonerated again.", partial, GetLastError());
        error_box(msg);
        return 0;
    }
    snprintf(game_dir, n, "%s", dest);
    return 1;
}

static int import_xbe(const char *exe_dir, const char *xbe_path, char *game_dir, size_t n)
{
    char dir[MAX_PATH], data[MAX_PATH], ini[MAX_PATH], *slash;
    size_t size;
    void *xbe = read_file(xbe_path, &size);
    int ok = check_xbe(xbe, size, "This default.xbe");

    free(xbe);
    if (!ok)
        return 0;
    if (!GetFullPathNameA(xbe_path, sizeof dir, dir, NULL))
        snprintf(dir, sizeof dir, "%s", xbe_path);
    if ((slash = strrchr(dir, '\\')) != NULL)
        *slash = 0;
    snprintf(data, sizeof data, "%s\\data", dir);
    if (GetFileAttributesA(data) == INVALID_FILE_ATTRIBUTES) {
        MessageBoxA(NULL, "The game's \"data\" folder is missing next to default.xbe.\n\n"
                    "Use the complete files from your disc (default.xbe together with "
                    "its data folder), or choose the disc image (.iso) instead.",
                    TITLE, MB_ICONERROR);
        return 0;
    }
    /* Used where it is, and remembered, rather than copied. */
    ini_path(exe_dir, ini, sizeof ini);
    WritePrivateProfileStringA("game", "dir", dir, ini);
    snprintf(game_dir, n, "%s", dir);
    return 1;
}

static int ask_for_game(char *path, size_t n)
{
    OPENFILENAMEA ofn;
    memset(&ofn, 0, sizeof ofn);
    path[0] = 0;
    ofn.lStructSize = sizeof ofn;
    ofn.lpstrFilter = "Deathrow disc image or default.xbe\0*.iso;*.xiso;default.xbe\0"
                      "All files\0*.*\0";
    ofn.lpstrFile = path;
    ofn.nMaxFile = (DWORD)n;
    ofn.lpstrTitle = "Choose your Deathrow disc image (.iso) or default.xbe";
    ofn.Flags = OFN_FILEMUSTEXIST | OFN_PATHMUSTEXIST | OFN_HIDEREADONLY;
    return GetOpenFileNameA(&ofn) != 0;
}

int dr_game_import(const char *exe_dir, const char *from, char *game_dir, size_t n)
{
    char path[MAX_PATH];

    if (from && *from) {
        snprintf(path, sizeof path, "%s", from);
        return ends_with(path, ".xbe") ? import_xbe(exe_dir, path, game_dir, n)
                                       : import_iso(exe_dir, path, game_dir, n);
    }
    if (MessageBoxA(NULL,
                    "Welcome to Exonerated.\n\n"
                    "To play, it needs your own copy of Deathrow for the original Xbox "
                    "(North American release). Next, choose its disc image (.iso), or "
                    "the default.xbe from its files.\n\n"
                    "This is only needed once.",
                    TITLE, MB_OKCANCEL | MB_ICONINFORMATION) != IDOK)
        return 0;
    for (;;) {
        int ok;
        if (!ask_for_game(path, sizeof path))
            return 0;
        ok = ends_with(path, ".xbe") ? import_xbe(exe_dir, path, game_dir, n)
                                     : import_iso(exe_dir, path, game_dir, n);
        if (ok)
            return 1;
        if (MessageBoxA(NULL, "Choose another file?", TITLE,
                        MB_YESNO | MB_ICONQUESTION) != IDYES)
            return 0;
    }
}
