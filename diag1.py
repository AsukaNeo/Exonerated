import re, sys
f = sys.argv[1]; s = open(f, encoding='utf-8', errors='surrogateescape').read()
s, n = re.subn(r'default:\s*return 0;\s*\}\s*\}\s*(?=static int sample_texture\()', lambda m: '''default: {
        static unsigned char seen[256];
        if (!seen[fmt & 0xFF]) {
            seen[fmt & 0xFF] = 1;
            fprintf(stderr, "[TEXFMT] no decoder for format 0x%02X (%ux%u)\\n",
                    fmt, t->width, t->height);
        }
        return 0;
    }
    }
}

''', s, count=1)
print(('OK   ' if n else 'FAIL ') + 'log unsupported texture formats')
s, n = re.subn(r"(add them when a title's look depends on one\. \*/\r?\n)", lambda m: m.group(1) + """        {
            static unsigned char seen[32];
            if (!seen[mode & 31]) {
                seen[mode & 31] = 1;
                fprintf(stderr, "[STAGE] shader stage mode %u (stage %d) not modelled, reads 0\\n", mode, st);
            }
        }
""", s, count=1)
print(('OK   ' if n else 'FAIL ') + 'log unmodelled stage modes')
open(f, 'w', encoding='utf-8', errors='surrogateescape', newline='').write(s)
