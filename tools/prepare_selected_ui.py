"""Lossless extraction of decorative pixels from approved UI boards.

Requested illustrated buttons retain their approved artwork and native controls.
Live labels, timers and navigation remain accessible application elements.
"""
import json
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'webapp/assets/ui-doodle-v1'
DEST = ROOT / 'webapp/assets/ui-selected-v3'
DEST.mkdir(exist_ok=True)
REGIONS = {
    'home-desktop': ('02-home-desktop.png', (615, 120, 1505, 1020)),
    'home-record-desktop': ('02-home-desktop.png', (76, 559, 525, 725)),
    'home-record-mobile': ('01-home-mobile.png', (133, 1108, 721, 1332)),
    'home-map-desktop': ('02-home-desktop.png', (76, 837, 492, 956)),
    'home-map-mobile': ('01-home-mobile.png', (180, 1474, 665, 1630)),
    'capture-idle-button': ('03-capture-idle.png', (263, 1128, 592, 1452)),
    'capture-idle-art': ('03-capture-idle.png', (0, 611, 853, 1134)),
    'capture-import-button': ('03-capture-idle.png', (239, 1478, 614, 1588)),
    'capture-ready': ('03-capture-idle.png', (320, 1600, 534, 1648)),
    'permission-import-button': ('05-capture-permission.png', (117, 1323, 736, 1500)),
    'raw-generate-button': ('07-raw-success.png', (78, 1209, 779, 1391)),
    'cassette-small-blue': ('08-library-mobile.png', (58, 1120, 164, 1200)),
    'cassette-small-yellow': ('08-library-mobile.png', (58, 1212, 164, 1295)),
    'cassette-small-red': ('08-library-mobile.png', (58, 1305, 164, 1390)),
    'library-record': ('09-library-desktop-v2.png', (1090, 280, 1447, 490)),
    'editor-record': ('13-editor-mobile-v2.png', (26, 407, 333, 650)),
    'transport-start': ('12-editor-desktop.png', (517, 481, 579, 545)),
    'transport-undo': ('12-editor-desktop.png', (607, 481, 670, 545)),
    'transport-redo': ('12-editor-desktop.png', (829, 481, 893, 545)),
    'transport-pause': ('12-editor-desktop.png', (702, 464, 800, 562)),
    'icon-play': ('01-home-mobile.png', (181, 1382, 221, 1425)),
    'icon-volume': ('13-editor-mobile-v2.png', (31, 1029, 83, 1077)),
    'icon-microphone': ('13-editor-mobile-v2.png', (110, 1520, 159, 1575)),
    'icon-music': ('13-editor-mobile-v2.png', (462, 1525, 509, 1577)),
    'icon-tune': ('13-editor-mobile-v2.png', (42, 1661, 85, 1705)),
    'icon-piano': ('13-editor-mobile-v2.png', (232, 1272, 293, 1333)),
    'icon-minus': ('12-editor-desktop.png', (1310, 520, 1345, 548)),
    'icon-plus': ('12-editor-desktop.png', (1419, 518, 1450, 551)),
    'nav-home': ('01-home-mobile.png', (67, 1695, 139, 1767)),
    'nav-map': ('01-home-mobile.png', (277, 1695, 350, 1767)),
    'nav-community': ('01-home-mobile.png', (491, 1700, 571, 1767)),
    'nav-album': ('01-home-mobile.png', (713, 1696, 786, 1767)),
    'icon-heart-white': ('12-editor-desktop.png', (354, 350, 405, 402)),
    'capture-recording': ('04-capture-recording.png', (0, 510, 853, 1160)),
    'capture-permission': ('05-capture-permission.png', (0, 580, 853, 1130)),
    'raw-saved': ('07-raw-success.png', (100, 240, 810, 754)),
    'library-hero': ('09-library-desktop-v2.png', (393, 320, 1040, 604)),
    'library-footer': ('09-library-desktop-v2.png', (0, 840, 1505, 970)),
    'editor-hero': ('12-editor-desktop.png', (682, 125, 1503, 462)),
    'editor-context': ('13-editor-mobile-v2.png', (48, 194, 357, 365)),
    'auth-speaker': ('29-account-auth-v2.png', (1130, 132, 1290, 414)),
    'import-empty': ('10-sample-states.png', (103, 428, 473, 693)),
    'import-error': ('10-sample-states.png', (1165, 430, 1495, 681)),
    'auth-left': ('29-account-auth-v2.png', (0, 532, 280, 980)),
    'auth-right': ('29-account-auth-v2.png', (1292, 210, 1605, 930)),
    'password-art': ('31-password-delete.png', (231, 167, 730, 385)),
    'delete-art': ('31-password-delete.png', (950, 154, 1322, 385)),
    'profile-background': ('20-profile-edit.png', (34, 166, 819, 330)),
    'profile-empty': ('20-profile-edit.png', (310, 1390, 573, 1575)),
    'profile-stats': ('20-profile-edit.png', (70, 1081, 234, 1210)),
    'send-stats': ('20-profile-edit.png', (482, 1081, 663, 1203)),
    'listening-top': ('21-listening-desktop.png', (331, 0, 1450, 153)),
    'listening-left': ('21-listening-desktop.png', (0, 268, 323, 770)),
    'listening-mobile-footer': ('22-listening-mobile.png', (0, 1395, 853, 1672)),
}
for i, (x, y) in enumerate([(75, 721), (266, 721), (459, 721), (648, 721), (75, 882), (266, 882), (459, 882), (648, 882)]):
    REGIONS['avatar-'+str(i)] = ('20-profile-edit.png', (x, y, x+140, y+140))
scene_ids = ['sea-window', 'rainy-city', 'autumn-lake', 'snow-mountain', 'spring-meadow', 'desert-dusk']
for i, scene in enumerate(scene_ids):
    x, y = [283,445,607][i%3], [435,616][i//3]
    REGIONS[scene] = ('27-community-composer-v2.png', (x,y,x+134,y+117))
for name, (file, rect) in REGIONS.items():
    with Image.open(SOURCE/file) as image:
        image.crop(rect).save(DEST/(name+'.webp'), lossless=True)
(DEST/'sources.json').write_text(json.dumps(REGIONS,ensure_ascii=False,indent=2),encoding='utf-8')
regions_path=ROOT/'webapp/assets/ui-raster-v2/regions.json'
regions=json.loads(regions_path.read_text(encoding='utf-8'))
for name,(_,rect) in REGIONS.items():
    w,h=rect[2]-rect[0],rect[3]-rect[1]
    regions[name]={'src':'/assets/ui-selected-v3/'+name+'.webp','source':[w,h],'rect':[0,0,w,h]}
regions_path.write_text(json.dumps(regions,ensure_ascii=False),encoding='utf-8')
(ROOT/'studio/src/raster-regions.json').write_text(json.dumps(regions,ensure_ascii=False),encoding='utf-8')
js=ROOT/'webapp/assets/soundtrace-raster.js'
text=js.read_text(encoding='utf-8')
start=text.index('const regions=')+len('const regions=')
end=text.index(';\nconst cells=',start)
js.write_text(text[:start]+json.dumps(regions,ensure_ascii=False)+text[end:],encoding='utf-8')
print('Prepared',len(REGIONS),'approved decorative regions')
