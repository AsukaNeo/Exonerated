#!/usr/bin/env python3
"""gx16.py - log and dump the textures the D3D11 back end binds. Run from
deathrow/ (py -3 patches/scripts/gx16.py). Patches
../xboxrecomp/src/kernel/nv2a_gpu_d3d11.cpp (.pre_gx16).

gpu2: on the D3D11 path the "Tonight's Game" crowd draws cleanly (the CPU
path's vertical stripes are gone), but the top-left "YOUR AD HERE" panel
comes out squashed, with every other row blank, while the larger copy of
the same ad at the bottom is right. Suspects: a smaller mip level (or a
second, smaller texture) decoded or uploaded wrong, or a video/YUV surface.

With RECOMP_GPU_TEX_LOG set, get_texture prints one [GPU-TEX] line per
distinct binding and path (feedback, alias-null, direct, cache, upload,
refresh): guest address, size, format, linear, pitch, mip levels, filter,
bytes. If the value is not "1" it is a file prefix, and each new upload or
refresh also dumps its first 3 mip levels, decoded with the CPU sampler, as
<prefix>NNN_L<level>.bmp (up to 150 textures).
"""
import shutil, sys

EX = "../xboxrecomp/src/kernel/nv2a_gpu_d3d11.cpp"
raw = open(EX, encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
src = raw.replace("\r\n", "\n")
if "[gx16]" in src:
    sys.exit("already patched: " + EX)
fails = 0

def rep(label, old, new):
    global fails, src
    if src.count(old) == 1:
        src = src.replace(old, new); print("OK  ", label)
    else:
        fails += 1; print("FAIL", label, src.count(old))

HELPER = r'''/* [gx16] RECOMP_GPU_TEX_LOG: one line per distinct texture binding and
 * path; a prefix value also dumps the first mip levels of uploads. */
extern "C" ptrdiff_t xbox_GetMemoryOffset(void);
struct Gx16Key { const uint8_t *source; uint32_t width, height, format, linear, pitch, levels; const char *path; };
static std::vector<Gx16Key> gx16_seen;

static void gx16_dump(const Nv2aGpuTexture &binding, const char *prefix, unsigned id)
{
    uint32_t levels = binding.mip_levels ? binding.mip_levels : 1;
    for (uint32_t level = 0; level < levels && level < 3; level++) {
        uint32_t w = std::max(binding.width >> level, 1u), h = std::max(binding.height >> level, 1u);
        std::vector<uint32_t> image((size_t)w * h, 0xFFFF00FFu);
        for (uint32_t y = 0; y < h; y++)
            for (uint32_t x = 0; x < w; x++) {
                uint32_t *p = &image[(size_t)y * w + x];
                if (level ? !(binding.decode_level && binding.decode_level(binding.decode_context, 0, level, x, y, p))
                          : !(binding.decode && binding.decode(binding.decode_context, x, y, p)))
                    *p = 0xFFFF00FFu;
            }
        char name[512];
        std::snprintf(name, sizeof name, "%s%03u_L%u.bmp", prefix, id, level);
        FILE *f = std::fopen(name, "wb");
        if (!f) continue;
        uint32_t data = (uint32_t)image.size() * 4;
        uint8_t header[54] = {'B', 'M'};
        auto put = [&](int at, uint32_t v) { std::memcpy(header + at, &v, 4); };
        put(2, 54 + data); put(10, 54); put(14, 40); put(18, w); put(22, (uint32_t)-(int32_t)h);
        header[26] = 1; header[28] = 32; put(34, data);
        std::fwrite(header, 1, sizeof header, f);
        std::fwrite(image.data(), 1, data, f);
        std::fclose(f);
    }
}

static void gx16_note(const Nv2aGpuTexture &binding, const char *path)
{
    static const char *setting = std::getenv("RECOMP_GPU_TEX_LOG");
    static unsigned dumps;
    if (!setting || gx16_seen.size() >= 600) return;
    for (const auto &k : gx16_seen)
        if (k.source == binding.source && k.width == binding.width && k.height == binding.height &&
            k.format == binding.format && k.linear == binding.linear && k.pitch == binding.pitch &&
            k.levels == binding.mip_levels && k.path == path) return;
    gx16_seen.push_back({binding.source, binding.width, binding.height, binding.format, binding.linear,
                         binding.pitch, binding.mip_levels, path});
    bool dump = std::strcmp(setting, "1") != 0 && dumps < 150 &&
                (std::strcmp(path, "upload") == 0 || std::strcmp(path, "refresh") == 0);
    std::fprintf(stderr, "[GPU-TEX] %-10s va %08X %ux%u fmt %02X linear %u pitch %u levels %u filter %08X addr %u/%u bytes %u%s",
                 path, (uint32_t)((uintptr_t)binding.source - (uintptr_t)xbox_GetMemoryOffset()),
                 binding.width, binding.height, binding.format, binding.linear, binding.pitch,
                 binding.mip_levels, binding.filter, binding.address_u, binding.address_v,
                 binding.source_bytes, dump ? "" : "\n");
    if (dump) {
        std::fprintf(stderr, " -> dump %03u\n", dumps);
        gx16_dump(binding, setting, dumps++);
    }
}

static ID3D11ShaderResourceView *get_texture(const Nv2aGpuTexture &binding, const Surface &destination)
{
'''

rep("helper",
    "static ID3D11ShaderResourceView *get_texture(const Nv2aGpuTexture &binding, const Surface &destination)\n{\n",
    HELPER)
rep("feedback",
    "            return get_feedback_texture(destination);\n",
    "            gx16_note(binding, \"feedback\");                  /* [gx16] */\n"
    "            return get_feedback_texture(destination);\n")
rep("alias-null",
    "                     (const void *)destination.memory, destination.width, destination.height, destination.pitch);\n"
    "        return nullptr;\n",
    "                     (const void *)destination.memory, destination.width, destination.height, destination.pitch);\n"
    "        gx16_note(binding, \"alias-null\");                    /* [gx16] */\n"
    "        return nullptr;\n")
rep("direct",
    "        return direct->view.Get();\n"
    "    }\n"
    "    CachedTexture *refresh = nullptr;\n",
    "        gx16_note(binding, \"direct\");                        /* [gx16] */\n"
    "        return direct->view.Get();\n"
    "    }\n"
    "    CachedTexture *refresh = nullptr;\n")
rep("cache",
    "            if (auto *view = check(textures[it->second])) return view;\n",
    "            if (auto *view = check(textures[it->second])) { gx16_note(binding, \"cache\"); return view; } /* [gx16] */\n")
rep("upload",
    "    if (refresh) {\n"
    "        ComPtr<ID3D11Resource> resource;\n",
    "    gx16_note(binding, refresh ? \"refresh\" : \"upload\");        /* [gx16] */\n"
    "    if (refresh) {\n"
    "        ComPtr<ID3D11Resource> resource;\n")

if fails:
    sys.exit(f"{fails} edit(s) failed -- nothing written")
shutil.copyfile(EX, EX + ".pre_gx16")
open(EX, "w", encoding="utf-8", newline="").write(src.replace("\n", "\r\n") if crlf else src)
print("version gx16 v1; written; backup *.pre_gx16")
