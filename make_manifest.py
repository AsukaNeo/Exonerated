import json, hashlib, struct, sys, urllib.request

xbe = sys.argv[1] if len(sys.argv) > 1 else '../xboxrecomp/game_files/default.xbe'
d = open(xbe, 'rb').read()
if d[:4] != b'XBEH':
    sys.exit('not an XBE: ' + xbe)
base = struct.unpack_from('<I', d, 0x104)[0]
cert = struct.unpack_from('<I', d, 0x118)[0] - base
tid = struct.unpack_from('<I', d, cert + 0x08)[0]
title = d[cert + 0x0C:cert + 0x0C + 80].decode('utf-16-le', 'replace').split('\0')[0]
region = struct.unpack_from('<I', d, cert + 0xA0)[0]
version = struct.unpack_from('<I', d, cert + 0xAC)[0]
serial = chr((tid >> 24) & 0xFF) + chr((tid >> 16) & 0xFF) + '-%03d' % (tid & 0xFFFF)
regions = [n for b, n in ((1, 'USA'), (2, 'Japan'), (4, 'PAL')) if region & b]
original = {'region': '/'.join(regions) or 'unknown', 'revision': str(version),
            'serial': serial, 'sha1': hashlib.sha1(d).hexdigest()}

qid = None
try:
    url = ('https://en.wikipedia.org/w/api.php?action=query&prop=pageprops'
           '&ppprop=wikibase_item&format=json&titles=Deathrow_(video_game)')
    req = urllib.request.Request(url, headers={'User-Agent': 'exonerated-manifest/1.0'})
    pages = json.load(urllib.request.urlopen(req, timeout=15))['query']['pages']
    qid = next(iter(pages.values())).get('pageprops', {}).get('wikibase_item')
except Exception as e:
    print('wikidata lookup failed (left out):', e)

m = {
    '$schema': 'https://recomp.fyi/schema/v1.json',
    'game': 'Deathrow',
    'system': 'Xbox',
    'type': 'recomp',
    'original': original,
    'project': 'Exonerated',
    'status': 'in-progress',
    'targets': ['Windows'],
    'toolchain': 'Xboxrecomp',
    'approach': 'Static recompilation of the XBE to C with xboxrecomp; software NV2A rasteriser with fixed-function T&L',
    'maintainers': [{'name': 'AsukaNeo', 'link': 'https://github.com/AsukaNeo'}],
    'help': ['Rasteriser speed (register combiners, texture sampling)',
             'Player texture artifacts',
             'NV2A fixed-function lighting',
             'Audio (APU / DirectSound)'],
    'notes': ('Boots to the menus and plays a full match end to end: team select, kickoff, '
              'replays, back to the main menu. Software rendering runs at roughly 8-9 fps in a '
              'match. Fixed-function draw calls are now rendered, which restored the players\' '
              'lower bodies. Next: rendering speed, jersey texture artifacts, lighting, audio.'),
}
if qid:
    m['wikidata'] = qid
keys = ['$schema', 'game', 'wikidata', 'system', 'type', 'original', 'project', 'status',
        'targets', 'toolchain', 'approach', 'maintainers', 'help', 'notes']
m = {k: m[k] for k in keys if k in m}
assert len(m['notes']) <= 600 and len(m['approach']) <= 200
open('.recomp.json', 'w', encoding='utf-8', newline='\n').write(json.dumps(m, indent=2, ensure_ascii=False) + '\n')
print('XBE title:', title, '| title id %08X' % tid, '| region bits %X' % region)
print(open('.recomp.json', encoding='utf-8').read())
