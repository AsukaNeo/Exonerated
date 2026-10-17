import os, re
p=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src', 'recomp', 'gen', 'recomp_stubs_unresolved.c')
s=open(p,'rb').read().decode('utf-8','surrogateescape')
if '[STUB]' in s: print('stub_trace: already patched'); raise SystemExit
r=re.compile(r'(void\s+(sub_[0-9A-Fa-f]+)\s*\(void\)\s*\{)')
n=len(r.findall(s))
s=r.sub(lambda m: m.group(1)+' { static int _n; if (_n++ < 2) fprintf(stderr,"[STUB] '+m.group(2)+' ret=%08X\\n",(unsigned)MEM32(g_esp)); }', s)
open(p,'wb').write(('#include <stdio.h>\n'+s).encode('utf-8','surrogateescape'))
print('stub_trace: patched',n,'stubs')
