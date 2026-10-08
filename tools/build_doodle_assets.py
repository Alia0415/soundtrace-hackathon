"""Original responsive SVG illustrations for the approved SoundTrace UI direction."""
from pathlib import Path

DEST = Path(__file__).resolve().parents[1] / 'webapp/assets/doodle'
DEST.mkdir(exist_ok=True)
BLUE = '#00a8f0'
def save(name, body, box='0 0 600 480'):
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{box}" fill="none"><g stroke="#000" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round">{body}</g></svg>'
    (DEST / (name+'.svg')).write_text(svg, encoding='utf-8')
def blue(path):
    return f'<path d="{path}" stroke="{BLUE}"/>'
sun = '<circle cx="460" cy="93" r="17" fill="#f5ba16" stroke="none"/><path d="M460 59v-12m-35 30-10-6m76 7 11-5m-60 49-8 10m53-10 8 9" stroke="#f5ba16"/>'
birds = '<path d="M84 100q12-12 24 0 10-12 22-3m70-42q8-10 19 0 8-10 18-2"/>'
waves = blue('M48 302q40-8 80 0t80 0m-127 23h105m42-10q45-8 90 0t90 0m-189 28h60m88-4h115m-310 25q60-8 118 0m96-3h40')
scenes = {
 'sea-window': birds+'<path d="m303 240 12-125 22 1 14 124m-42-107h32m-25-28 14-28 14 28m-28 57h22m-18 35h22M40 280q90-42 166-24t160-9 181 20M378 276l38-16 43 11-11 25h-51z"/>'+waves+sun,
 'rainy-city': '<path d="M60 330V159l52-32 55 34v166m-81-160v20m30-19v20m-30 25v20m30-20v20m58 102V210l53-34 44 20v132m37 0V133l80-26 61 31v197M366 81v240m-28-226 28-20 27 21-14 32h-25zm-17 34h47M29 368q193-45 529-2"/>'+blue('M68 353h102m49 20h154m42-23h88')+'<path d="m56 72-8 23m85-30-8 23m73-49-9 29m68-15-9 26m90-49-8 25m100-26-8 25m49 156-8 26m-56-7-8 25m-282-56-8 23m-62 27-8 23"/>'+sun,
 'autumn-lake': '<path d="M43 272 149 173l53 54 69-120 95 140 98-76 98 105M83 247V119m0 67q-80-35-17-64-42-51 18-64 75 17 41 69 67 41-42 68M465 267V174m-55 46q-30-64 28-71 50-46 70 12 57 55-28 63M359 310l110-2m-101 0v44m88-44v44m-91-25h91M348 364h130"/>'+waves+sun,
 'snow-mountain': '<path d="m22 300 173-203 99 118 74-146 199 249m-425-157 38 9 24-21 31 40 24-3m62-25 34 15 21-29 44 35 25-2M65 301l32-68 31 68zm32-48-41 89h81m-39-6v34m61-64 31-75 33 73m-32-44-43 98h85m-43-5v30M304 367l18-51 17 51m-7-21 22 10m-35-10-18 10"/>'+blue('M26 388h129m54-11h113m66 9h165')+'<circle cx="439" cy="93" r="20" fill="#f5ba16" stroke="none"/>',
 'spring-meadow': birds+'<path d="M26 270q130-90 268-24t267-9M22 370q100-65 220-9t306-18"/>'+''.join(f'<g transform="translate({x} {y})"><path d="M0 0v55m0-19q-25-19-27-4 4 11 27 15m0-25q24-16 28-3-3 10-28 15"/><path d="M-5-8q-29-25-23-4-25 15-2 20 0 29 24 10 24 18 25-9 22-10-1-23-2-24-23 6Z"/><circle cy="2" r="6" fill="#f5ba16" stroke="none"/></g>' for x,y in [(100,288),(213,317),(345,290),(452,317)])+sun,
 'desert-dusk': '<path d="M22 304q109-119 270-42t272-1M14 358q140-107 281-19t273-1M368 314V162q8-17 18 0v76m-19-32h-27v-48q-7-12-15 0v51q0 18 42 18m19 27h29q12 0 12-16v-43q-8-14-16 0v36h-25M220 299l13-29 30-7 10 19 35 7v17m-66-10v35m38-26v25m-48-53-21-6"/>'+sun+blue('M67 365h112m57 19h80m120-13h92'),
}
for name, body in scenes.items(): save(name, body)
vinyl = '<circle cx="341" cy="226" r="157" fill="#fff"/><circle cx="341" cy="226" r="139"/><circle cx="341" cy="226" r="118"/><circle cx="341" cy="226" r="92"/><circle cx="341" cy="226" r="43" fill="#00a8f0"/><circle cx="341" cy="226" r="7" fill="#000"/><path d="m81 77 225 10-9 318-230-10Z" fill="#fff"/><path d="m87 108 192 8-6 205-189-8Z"/><path d="m110 270 37-56 43 38 25-58 44 64"/>'+blue('M95 282q45-8 84 0t80 0m-127 22h101')+'<circle cx="218" cy="160" r="16" fill="#f5ba16" stroke="none"/><path d="M98 353h145m-147 20h81"/>'
tape = '<path d="m65 124 463-7 8 253-471 9Z" fill="#fff"/><path d="m89 147 413-7 4 146-413 8Z"/><rect x="112" y="183" width="365" height="90" rx="24"/><circle cx="165" cy="228" r="33"/><circle cx="426" cy="228" r="33"/>'+''.join(f'<path d="M{cx-18} 228h36m-18-18v36m-13-31 26 26m0-26-26 26" stroke="#00a8f0"/>' for cx in (165,426))+'<path d="m204 210 174-4v45H204zM176 323h240l18 35H159zm-55-184h-9m377-1h10m-10 208h10m-377 1h-9"/>'+blue('M251 162h97')
photo = '<path d="m142 69 298 12-9 353-300-14Z" fill="#fff"/><path d="m161 102 254 6-8 233-252-9Z"/><path d="m179 257 56-62 45 34 27-54 76 78"/>'+blue('M175 281h208m-160 22h116')+'<circle cx="342" cy="159" r="21" fill="#f5ba16" stroke="none"/><path d="m158 374 169 7m-180 20 86 3"/><path d="m258 68 42-13 11 34-43 12Z" fill="#f5ba16"/>'
mail = '<path d="M161 324V132q1-76 86-76h137q88 6 88 78v190H161Z" fill="#fff"/><path d="M325 322V133q0-62 63-77M325 157h98v32h-98m52 146v81m-178-81v81m-17 0h33m146 0h33M162 117h130v53H162zm131-45h56V26h51v36h-51"/>'+blue('M349 26h51v36h-51Z')+'<path d="m185 234 99-3 5 73-106 2Z"/><path d="m184 236 55 35 45-38"/>'
for name, body, box in [('vinyl',vinyl,'50 50 465 390'),('tape',tape,'45 90 510 300'),('photo',photo,'115 35 340 420'),('mailbox',mail,'130 5 365 455')]: save(name,body,box)
save('microphone','<g transform="translate(55 0)"><rect x="169" y="72" width="154" height="238" rx="76" transform="rotate(12 246 191)" fill="#fff"/><path d="M174 160h138m-145 20h139m-140 22h137m-133 22h128m-73-130v144m23-140v147m-46-141v138M137 253q-13 137 118 115 73-11 86-66m-104 70-13 66m-43 5h119"/><path d="m153 98 3-22m-43 51-25-12m251-25 18-22" stroke="#f5ba16"/></g>'+blue('M36 268h23l10-27 12 55 12-72 12 90 10-49h23m304 0h22l10-36 10 67 12-81 12 104 10-49h21'))
save('hero','<g transform="translate(290 10)"><path d="m105 65 124-57v317l-124 40Zm14 6 96-44v291l-96 28m20-112 59-24m-81 41 98-35m-98-53 98-39M249 0v358m11-291h173v222H260m0-112h173"/><path d="M272 214q31-27 61-8t91-15m-59-7 8-56h14l9 54m-25-49h19m-22-10 11-20 11 20m-44 160h75"/>'+blue('M276 232h78m-56 15h111m-125 17h71')+'<path d="M240 340h169l25 25H211zm-22 26v82h203v-80m-98 0v79m-84-48h61m48 0h54m-105 19h3m56 0h3m-120 26v20m185-20v20M403 315v-57m0 17q-31-23-25-3 1 18 25 23m0-35q27-29 28-4 0 17-28 25"/><g transform="translate(211 300) scale(.24)">'+vinyl+'</g></g><path d="m121 180 88-28 23 105-89 23Z" fill="#fff"/><ellipse cx="128" cy="232" rx="23" ry="54" transform="rotate(-13 128 232)" fill="#fff"/><path d="m143 189 15 69m15-77 18 66M72 249l-32 21m41 3-10 29m12-77-38-4M99 267q-21 0-38 10l-40 71m109-72-18 53q-11 32-45 38M52 304l33-38q15-17 26-5l-20 35"/>'+blue('M231 206C401 122 335 443 476 348S339 256 530 230')+'<path d="m141 140-8-19m32 13 6-23m-69 43-24-12" stroke="#f5ba16"/>','0 0 800 520')
save('notebook','<path d="m178 78 204 18-27 311-214-18Z" fill="#fff"/><path d="m177 96 178 16-22 275-177-16m10-250-36-3m33 53-37-3m33 53-37-3m33 53-37-3m33 53-37-3m33 53-37-3m30-288 12-19m191 336 90-192 19-1 8 17-99 186-22 16Z"/>'+blue('M204 162h122m-129 33h125m-91 98q21-47 35-13t22-18 28 15')+'<path d="m392 93 15-23m7 35 22-10" stroke="#f5ba16"/>')
save('map','<path d="m83 144 141-39 150 52 130-37v263l-130 35-150-51-141 31Zm141-39v262m150-210v261M129 285l60-53 63 14 48-76m76 135 71-33 33 18"/>'+blue('M152 318q20-34 56-14t54 16 56-32 100 66')+'<path d="M311 124c0 36-45 81-45 81s-44-44-44-81a45 45 0 0 1 89 0Z" fill="#fff"/><circle cx="266" cy="124" r="14" stroke="#00a8f0"/><path d="m434 171 18-4 3 17-18 4Z" fill="#f5ba16"/>')
# All 26 choice drawings are actual independent SVGs, with a single visual language.
icons = {
 'mood-calm':'<path d="M27 68q30-13 61 0m-52 13h50M42 48l25 5 16-5-7 12H49zm20-9V19l19 23H62Z"/>',
 'mood-happy':'<circle cx="56" cy="53" r="29"/><path d="M45 43v3m24-3v3M41 58q17 21 32 0"/>',
 'mood-excited':'<path d="m24 75 26-48 38 40m-38-40 5 58m12-72 7 11m14 4 12-2m-2 21 11 5"/>',
 'mood-missing':'<path d="m18 34 72-2 3 49-74 3Zm2 0 36 27 34-29m-8-16q7-12 14 0 7-12 13 0 0 8-13 17-14-9-14-17Z"/>',
 'mood-sad':'<path d="M34 57q-22-4-17-22 3-17 20-11 9-26 29-14 17 5 18 22 24 0 21 25H34Zm5 13-5 11m27-11-5 11m29-11-5 11"/>',
 'mood-tired':'<path d="m21 36 53-2 2 43-50 4Z M30 48l35-2m-22 13 12-1m25 3h22v22H79zm22 3q19-1 13 13h-12"/>',
 'mood-hopeful':'<path d="M56 91V54m0 18Q21 55 22 34q34 0 34 31m0-12q18-35 37-34-3 25-37 34M21 95h75"/>',
 'mood-nostalgic':'<path d="m17 23 55 5-4 60-56-5Z M24 34l37 3-3 34-37-3m8-5 13-18 14 16"/><circle cx="84" cy="70" r="22"/><circle cx="84" cy="70" r="8"/>',
 'weather-sunny':'<circle cx="56" cy="55" r="23"/><path d="M56 17V7m0 96V92m38-38h11M7 54h11m15-24-7-8m62 62 8 8m-9-65 8-8m-70 71 8-8"/>',
 'weather-cloudy':'<path d="M24 75Q7 72 14 53q3-13 19-12 6-32 31-20 20 0 23 28 26-3 23 26H24Z"/>',
 'weather-rainy':'<path d="M19 65Q4 42 26 34 32 10 58 19q19-1 26 22 21-1 19 24H19Zm15 10-8 19m28-19-8 19m28-19-8 19m28-19-8 19"/>',
 'weather-snowy':'<path d="M56 11v91M16 33l79 48M17 82l78-51M41 21l15 14 16-14M41 91l15-14 16 14M17 48l18-3-4-18m61 40-19 2 4 19M19 68l16 2-4 18m61-42-19-2 4-18"/>',
 'weather-foggy':'<path d="M33 48 56 15l29 33H33Zm12-9-24 35h68M13 81h93M20 94h78"/>',
 'weather-windy':'<path d="M12 35h60q25 0 15-19-11-7-18 4M14 52h74q30 0 19 27-13 13-22-5M27 69h29m-4 22q17-20 33-2-20 22-33 2Z"/>',
 'weather-night':'<path d="M72 17Q22 14 18 58q0 47 50 36 24-6 26-32-42 17-43-18 0-17 21-27Z M91 13l4 9 10 2-8 7 1 10-9-5-10 5 2-11-7-6 11-2Z"/>',
 'activity-work':'<path d="M12 89h93M24 83V48h60v35M33 48V30h43v18M57 30V14h26l16 19H57Zm0 62v16"/>',
 'activity-study':'<path d="M13 31q23-13 43 1 26-15 48-4v62q-28-12-48 1-22-10-43 0Zm43 1v59M27 47h15m-15 13h15m30-14h15m-15 15h15"/>',
 'activity-walk':'<path d="M25 17q27-8 23 19l-2 24-20 22-15-12 12-22-8-10Zm56 20q27-8 23 19l-2 24-20 22-15-12 12-22-8-10Z"/>',
 'activity-hike':'<path d="m8 89 37-71 33 68m-21 0 22-47 25 50M31 45l15 5 8-11m-39 61h93"/>',
 'activity-date':'<path d="M12 48h35v29H12Zm35 5q18-2 16 12-3 12-16 8m20-26h30v29H67zm30 5q18-2 15 13-3 9-15 7M17 91h91M47 23q5-9 12 0 8-9 13 0-2 11-13 17-12-6-12-17Z"/>',
 'activity-travel':'<rect x="22" y="33" width="75" height="64" rx="7"/><path d="M45 33V18h28v15M35 34v62m49-62v62m-54 1v8m60-8v8"/>',
 'activity-commute':'<path d="M23 83V24q34-16 72 0v58ZM31 34h54v26H31zm-8 37h72M37 84l-13 20m54-20 13 20m-56-13h45"/><circle cx="39" cy="72" r="4"/><circle cx="80" cy="72" r="4"/>',
 'activity-home':'<path d="M29 45q-8-32 25-32h12q29-1 20 32m-52 27V43q-18-9-21 8v29h85V53q-5-21-23-9v27H34Zm-10 10v20m63-20v20"/>',
 'activity-exercise':'<path d="M17 68 31 27l19 4 7 23 28 10 17 17q-43 20-89 5Z M15 87h88M49 50l-12 9m20-1-12 8m21-3-12 8"/>',
 'activity-gathering':'<ellipse cx="57" cy="67" rx="47" ry="16"/><path d="M21 80v23m72-23v23M25 56V42h14v16m37-2V42h14v15M14 16q43 24 89 0m-68 6v16m24-11v16m23-20v16"/>',
 'other':'<path d="m30 13 61 7-8 84-62-5Zm-7 22h18m-20 18h18m-20 19h18m-20 18h18m20-5 35-49 9 8-37 48-12 5Z"/>',
}
for name, body in icons.items():
    save(name, body+'<path d="M45 109q13-4 27-1" stroke="#00a8f0" stroke-width="4"/>', '0 0 120 120')
(DEST/'mic-icon.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#000" stroke-width="1.5" stroke-linecap="round"><rect x="9" y="2" width="6" height="13" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v4m-4 0h8"/></svg>',encoding='utf-8')
print(f'{len(list(DEST.glob("*.svg")))} original doodle assets ready')
