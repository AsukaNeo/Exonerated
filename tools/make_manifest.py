"""make_manifest.py - write .recomp.json (the recomp.fyi row). Run from deathrow/.

  py -3 tools/make_manifest.py [path/to/default.xbe] [--status playable|released|...]
"""
import json, hashlib, struct, sys, urllib.request

args = sys.argv[1:]
status = 'playable'            # 'released' once a build is published on GitHub
if '--status' in args:
    i = args.index('--status')
    status = args[i + 1]
    del args[i:i + 2]
xbe = args[0] if args else '../xboxrecomp/game_files/default.xbe'
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
    'status': status,
    'targets': ['Windows'],
    'toolchain': 'Xboxrecomp',
    'approach': ('Static recompilation of the XBE to C with xboxrecomp; NV2A pushbuffers drawn '
                 'by a Direct3D 11 back end (up to 4x, widescreen), CPU rasteriser as fallback'),
    'maintainers': [{'name': 'AsukaNeo', 'link': 'https://github.com/AsukaNeo'}],
    'links': [{'label': 'Download', 'url': 'https://github.com/AsukaNeo/Exonerated/releases'}],
    'tags': ['widescreen', 'upscaling', 'launcher'],
    'help': ['Light-glow flicker on the GPU renderer',
             'Texture glitches (striped pre-match loading backdrop)',
             'Testing on more graphics cards',
             'Linux / Steam Deck build'],
    'notes': ('Plays full matches start to finish. GPU renderer (Direct3D 11) at up to 4x the '
              'Xbox resolution, in the game\'s own 16:9 mode; the game\'s movies play in the '
              'window. Title card with settings, F10 overlay (live render resolution, AF, '
              'sharpening, FXAA), controller with rumble, keyboard. The download needs your own '
              'North American disc (v3): the first start copies the game from your .iso. Next: '
              'flicker and texture glitches, testing on more GPUs.'),
}
if qid:
    m['wikidata'] = qid
keys = ['$schema', 'game', 'wikidata', 'system', 'type', 'original', 'project', 'status',
        'targets', 'toolchain', 'approach', 'maintainers', 'links', 'tags', 'help', 'notes']
m = {k: m[k] for k in keys if k in m}
assert len(m['notes']) <= 600 and len(m['approach']) <= 200
open('.recomp.json', 'w', encoding='utf-8', newline='\n').write(json.dumps(m, indent=2, ensure_ascii=False) + '\n')
print('XBE title:', title, '| title id %08X' % tid, '| region bits %X' % region)
print(open('.recomp.json', encoding='utf-8').read())
