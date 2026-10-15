import re, sys
f = sys.argv[1]; s = open(f, encoding='utf-8', errors='surrogateescape').read()
def sub(pat, fn, what):
    global s
    s, n = re.subn(pat, fn, s, count=1)
    print(('OK   ' if n else 'FAIL ') + what)
FF = r'''/* Deathrow: NV2A fixed-function transform, after xemu vsh-ff.c, so batches
 * drawn without a vertex program are rasterised instead of skipped. Position
 * follows the hardware: composite matrix, or skinning through MODEL_VIEW 0-3
 * and then the composite; xy divided by w plus the viewport offset. Lighting,
 * texgen and texture matrices are not modelled yet: colour is the vertex
 * diffuse (white when absent) and texcoords pass through.
 * RECOMP_NO_FF=1 restores the old skip. */
static float s_ff_mv[4][16], s_ff_cmat[16];
static uint32_t s_ff_skin;
static int s_ff_active;
static unsigned s_ff_batches;

static int s_ff_tr = -1;          /* RECOMP_FF_TRANSPOSE=1: other matrix order */

static void ff_mul(const float m[16], const float v[4], float r[4])
{
    int j;
    if (s_ff_tr < 0)
        s_ff_tr = getenv("RECOMP_FF_TRANSPOSE") != NULL;
    if (s_ff_tr) {
        for (j = 0; j < 4; j++)
            r[j] = v[0] * m[j] + v[1] * m[4 + j] + v[2] * m[8 + j] + v[3] * m[12 + j];
        return;
    }
    for (j = 0; j < 4; j++)
        r[j] = v[0] * m[4 * j] + v[1] * m[4 * j + 1]
             + v[2] * m[4 * j + 2] + v[3] * m[4 * j + 3];
}

static int ff_transform_vertex(uint32_t index, Nv2aVshOutput *out)
{
    static const int cnt[7] = {0, 2, 2, 3, 3, 4, 4}, mix[7] = {0, 1, 0, 1, 0, 1, 0};
    float pos[4], wt[4], eye[4], clip[4], t[4], w, wsum = 1.0f;
    const float *o = nv2a_vsh_constant(59);            /* VIEWPORT_OFFSET */
    uint32_t sk = s_ff_skin < 7 ? s_ff_skin : 0;
    int k, j, n = cnt[sk];

    memset(out, 0, sizeof *out);
    fetch_attr(&s_gpu.attr[0], index, pos);
    if (n == 0) {
        ff_mul(s_ff_mv[0], pos, eye);
        ff_mul(s_ff_cmat, pos, clip);
    } else {
        fetch_attr(&s_gpu.attr[1], index, wt);
        eye[0] = eye[1] = eye[2] = eye[3] = 0.0f;
        for (k = 0; k < n; k++) {
            float wk;
            if (mix[sk] && k == n - 1)
                wk = wsum;                   /* last weight makes the sum 1 */
            else {
                wk = wt[k];
                wsum -= wk;
            }
            ff_mul(s_ff_mv[k], pos, t);
            for (j = 0; j < 4; j++)
                eye[j] += t[j] * wk;
        }
        ff_mul(s_ff_cmat, eye, clip);
    }
    w = clip[3];                                       /* clampAwayZeroInf */
    if (w >= 0.0f)
        w = w < 5.421011e-20f ? 5.421011e-20f : (w > 1.844674e19f ? 1.844674e19f : w);
    else
        w = w > -5.421011e-20f ? -5.421011e-20f : (w < -1.844674e19f ? -1.844674e19f : w);
    out->pos[0] = clip[0] / w + o[0];
    out->pos[1] = clip[1] / w + o[1];
    out->pos[2] = clip[2] / w;
    out->pos[3] = w;
    if (!fetch_attr(&s_gpu.attr[3], index, out->d0))
        out->d0[0] = out->d0[1] = out->d0[2] = out->d0[3] = 1.0f;
    if (!fetch_attr(&s_gpu.attr[4], index, out->d1))
        out->d1[0] = out->d1[1] = out->d1[2] = out->d1[3] = 0.0f;
    for (k = 0; k < 4; k++)
        fetch_attr(&s_gpu.attr[9 + k], index, out->tex[k]);
    out->fog[0] = out->fog[1] = out->fog[2] = out->fog[3] = fabsf(eye[2]);
    return 1;
}

'''
sub(r'(?=static void xf_to_clip\()', lambda m: FF, 'add fixed-function transform')
sub(r'(for \(i = 0; i < 3; i\+\+\) \{ k\[i\] = sc\[i\]; o\[i\] = of\[i\]; \}\s*\})',
    lambda m: m.group(1) + '''
    if (s_ff_active) {           /* composite already scaled: undo offset only */
        k[0] = k[1] = k[2] = 1.0f;
        o[2] = 0.0f;
    }''', 'clip fixed-function triangles')
sub(r'if \(!transform_vertex\(s_gpu\.idx\[i\], &s_xf\[i\]\)\)',
    lambda m: 'if (!(s_ff_active ? ff_transform_vertex(s_gpu.idx[i], &s_xf[i])\n                          : transform_vertex(s_gpu.idx[i], &s_xf[i])))',
    'transform with fixed function when active')
sub(r'if \(!batch_is_screen_space\(\)\) \{\s*s_gpu\.batches_untransformed\+\+;\s*return;\s*\}',
    lambda m: '''if (!batch_is_screen_space()) {
        static int no_ff = -1;
        if (no_ff < 0)
            no_ff = getenv("RECOMP_NO_FF") != NULL;
        if (no_ff) {
            s_gpu.batches_untransformed++;
            return;
        }
        s_ff_active = 1;
        raster_batch_program();
        s_ff_active = 0;
        if ((++s_ff_batches % 20000) == 0)
            fprintf(stderr, "[FF] %u fixed-function batches drawn (skin mode %u)\\n",
                    s_ff_batches, s_ff_skin);
        return;
    }''', 'draw fixed-function batches')
sub(r'(\n[ \t]*)(if \(method >= 0x0A20 && method < 0x0A30\) \{)',
    lambda m: m.group(1) + '''if (method == 0x0328) {                        /* SET_SKIN_MODE */
            s_ff_skin = param;
            break;
        }
        if (method >= 0x0480 && method < 0x0580) {    /* SET_MODEL_VIEW_MATRIX 0-3 */
            uint32_t e = (method - 0x0480) / 4;
            memcpy(&s_ff_mv[e / 16][e % 16], &param, 4);
            break;
        }
        if (method >= 0x0680 && method < 0x06C0) {    /* SET_COMPOSITE_MATRIX */
            memcpy(&s_ff_cmat[(method - 0x0680) / 4], &param, 4);
            break;
        }''' + m.group(1) + m.group(2), 'parse fixed-function matrices')
open(f, 'w', encoding='utf-8', errors='surrogateescape', newline='').write(s)
