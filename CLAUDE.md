WORKING RULES
1. Never open, cat or print binary/mesh/image files (.blend .glb .stl .png .zip). Inspect them only with scripts that print 20 lines or fewer.
2. Pipe long output through `tail -20`; use -q for pip/npm/git.
3. Keep each source file under ~300 lines. Edit files; don't rewrite whole files.
4. No frameworks, bundlers or test suites. Plain HTML + ES modules; three.js from a CDN via importmap.
5. Don't web-search unless something is blocked; the anatomy rules are in docs/SPEC.md.
6. Raw downloads go in data/raw/ (git-ignored). Commit only code and final assets/. Keep assets/ under 25 MB.
7. One phase per session. At the end: update docs/PROGRESS.md, commit, push to main, and tell me exactly what to test.
8. If a download is blocked, stop and give me the exact URL; I will upload the file to data/upload/.
- At the end of each phase, rewrite docs/PROGRESS.md (max 30 lines) with: Done, Decisions (with numbers), Known problems, Next step, Key files.
- When compacting, keep file names, measurements, decisions and open problems.
