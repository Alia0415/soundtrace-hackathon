# Cassette cabinet design QA — 2026-09-30

- Source visual truth: `C:\Users\aliaying\AppData\Local\Temp\codex-clipboard-33c2b297-7476-4815-8abb-f19da65ab925.png`
- Implementation target: `http://127.0.0.1:4173/?v=cassette-cabinet`
- Intended viewport: mobile portrait, 393 CSS px wide
- Source pixels: 852 x 1844
- Implementation pixels: unavailable because the in-app browser runtime exited before capture
- State: memory cabinet, doors open, carry tray visible

**Findings**

- [P1] Browser-rendered comparison is unavailable.
  Location: full cabinet screen.
  Evidence: the in-app browser failed twice with `windows sandbox failed: registered Core setup is not complete for the installed app`; no implementation screenshot could be captured.
  Impact: hotspot alignment, label placement, tray fit, drag behavior, and mobile overflow cannot be accepted from build output alone.
  Fix: reopen the local preview after the Codex browser runtime is available, capture the 393 px cabinet state, and compare it with the supplied reference.

**Required fidelity surfaces**

- Fonts and typography: source intent is represented in CSS, but browser rendering and wrapping are unverified.
- Spacing and layout rhythm: the image and nine hotspots share a fixed 944:1340 stage; rendered alignment is unverified.
- Colors and visual tokens: new assets follow the blue, turquoise, cream, green, and restrained orange reference palette; final display is unverified.
- Image quality and asset fidelity: generated cabinet and transparent cassette assets are present; browser scaling and transparency edges are unverified.
- Copy and content: visible flow now consistently refers to cassettes; rendered truncation is unverified.

**Build evidence**

- Production build: passed on 2026-09-30.
- Generated source assets: `assets/painted-cassette-cabinet.png`, `assets/painted-cassette.png`.
- Primary interactions requiring browser verification: cassette audition, click-to-carry, drag-to-tray, remove from tray, disabled/enabled pool CTA, and mobile scrolling.
- Console errors checked: unavailable because browser capture was blocked.
- Full-view comparison evidence: blocked; implementation capture missing.
- Focused region comparison evidence: blocked; implementation capture missing.
- Comparison history: no visual iteration could run because the first implementation capture was unavailable.

**Implementation checklist**

- Capture the cabinet screen at 393 px CSS width.
- Confirm all nine hotspots match their painted cassettes.
- Confirm each label remains below its own cassette without overlap.
- Confirm the tray begins below the illustration and all three slots remain thumb-friendly.
- Test audition, click selection, drag selection, removal, and the pool CTA.
- Check the console, then repeat the source/implementation visual comparison.

final result: blocked

