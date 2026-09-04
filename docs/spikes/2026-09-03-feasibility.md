# Feasibility spikes, 2026-09-03

Three cheap tests before writing the Engine spec. Machine: ASUS Vivobook,
i9-13900H (20 threads), Iris Xe (Vulkan, Mesa), 23 GB RAM, Arch Linux. Temporary artifacts
live in the session scratchpad; the numbers and conclusions are recorded here.

## A. Local LLM for writing (llama.cpp b10793, Qwen3 GGUF Q4_K_M)

**Question:** can a local model, on this hardware, write the outline from the transcript
of a sermon (27.5k tokens with timestamps)?

Short benchmark (`llama-bench`, pp2048 / tg64):

| Model | Backend | Prompt (t/s) | Generation (t/s) |
|---|---|---|---|
| Qwen3 8B | Vulkan (iGPU) | 99.4 | 2.31 |
| Qwen3 8B | CPU 14 threads | 36.4 | 5.25 |
| Qwen3 4B | Vulkan | 161.4 | 4.69 |
| Qwen3 4B | CPU | 63.8 | 9.20 |

Real test, 8B on CPU, whole sermon (27 532 tokens) + metadata request reusing the
prefix:

| Request | Time | real pp | real tg | Quality |
|---|---|---|---|---|
| Outline (3000 tokens) | 100.5 min | 18.2 t/s (25 min) | 0.66 t/s (75 min) | Degraded: loop «Génesis 8:1 … 8:186», structure only for minutes 9 to 15, passage «Génesis 6-9» |
| Metadata (533 tokens) | 14.5 min | prefix cache (119 new tokens) | 0.62 t/s | Generic |

At long context, CPU generation drops 8x compared to the benchmark and quality
collapses. **A single prompt with the whole transcript is not viable on this hardware.**

Chunked test: 10 minutes of sermon (3 198 tokens), extraction to JSON (topic,
verses with minute, verbatim quotes, one short):

| Model | Time | pp | tg | Quality |
|---|---|---|---|---|
| 4B CPU | 116 s | 61.7 | 7.52 | Valid JSON; 5 correct verses (Gn 8:11-15); real verbatim quotes; minutes off by ±9 s |
| 8B CPU | 192 s | 37.1 | 4.27 | Same, slightly more precise topic |

Extrapolated to a 78 min sermon (8 chunks): **15 min with 4B, 26 min with 8B**, in the
background while the render runs. Neither understood «30 to 60 s short» (they returned
the whole chunk).

**Design conclusions:**
1. Writer = map-reduce: extraction per 10 min chunk, then short writing over the extracts.
2. The LLM delivers verbatim quotes; anchoring to the SRT is deterministic (`srt_util`), never
   the minute the model says.
3. Short candidates by heuristic (silences + strong quotes); the LLM only writes titles.
4. 4B by default; 8B with a dedicated GPU or if the user agrees to wait. Vulkan on Iris Xe
   is good for reading the prompt, not for generating.

## B. Packaging the Python engine for three operating systems

**Question:** can faster-whisper + numpy + PIL + FastAPI be distributed as a binary
without Python installed, on Windows, macOS and Linux?

- Binary wheels for **Python 3.12** on `win_amd64`, `macosx arm64` and `manylinux`:
  faster-whisper, ctranslate2, onnxruntime, numpy, pillow, rembg, av, tokenizers,
  huggingface_hub, fastapi, uvicorn, pydantic. All present. Wheel size: 83 MB
  (Windows), 55 MB (macOS), 123 MB (Linux).
- `llama-cpp-python` has **no** wheels on PyPI: the `llama-server` binary from the
  llama.cpp releases is packaged instead (34 MB for the Vulkan variant) and talked to over HTTP.
- PyInstaller 6.22, Python 3.12.14 (mise), `--onedir`: builds in 20 s, **397 MB** (av 100 MB,
  ctranslate2 135 MB, onnxruntime 29 MB, numpy 42 MB). The binary ran with an empty environment
  (`env -i`), loaded large-v3 from disk in 6.3 s, transcribed 20 s of audio in 16 s
  (with the CPU busy with the LLM) and started FastAPI on `127.0.0.1:<random port>` with a
  token: 401 without token, 200 with token.
- Tauri: the machine already has rustc 1.98, cargo, webkit2gtk-4.1, gtk3, librsvg, Node 26.

**Conclusions:** viable, no surprises. The Windows and macOS installers are built on
those platforms (GitHub Actions with a matrix). `av` can be avoided by decoding with
ffmpeg and passing numpy to faster-whisper (−100 MB).

## C. License of the RVR1960 Bible text

**Question:** can the complete RVR1960 be bundled inside the app?

**1. Ownership and term**
- Holder: © 1960 Sociedades Bíblicas en América Latina; renewed © 1988 Sociedades Bíblicas Unidas (SBU, United Bible Societies). The rights are administered by American Bible Society (ABS) as representative in the US; the "Reina-Valera 1960®" mark is claimed as registered and "only usable under license". https://bibles.com/pages/american-bible-society-rights-and-permissions · https://www.biblegateway.com/versions/Reina-Valera-1960-RVR1960-Biblia/
- US: 1960 work with notice and renewal → 95 years from publication → public domain on 2056-01-01. https://guides.library.cornell.edu/copyright/publicdomain · https://en.wikipedia.org/wiki/Reina_Valera
- Colombia: Law 23/1982 art. 21 = life of the author + 80 years (natural persons); art. 27 (amended by Law 1915/2018) = 70 years from first publication when the holder is a legal entity (→ end of 2030). The original text of art. 27 (1982) gave legal entities only 30 years, and Law 1915 art. 14 only applies to works that had not already passed into the public domain. That opens a theoretical argument (that the term would have expired in 1990 in Colombia), but I found no source, doctrine or ruling that supports it; SBU/ABS claim worldwide validity. I do not recommend relying on it. https://normograma.mintic.gov.co/mintic/compilacion/docs/ley_0023_1982.htm · https://normograma.dian.gov.co/dian/compilacion/docs/ley_1915_2018.htm · https://www.wipo.int/edocs/lexdocs/laws/es/co/co012es.pdf
- Public debate: ABS insists it "is not in the public domain"; Spanish-language blogs accept that and only argue about the date (one post cites "2035" using the old 75-year rule). The only trademark application at USPTO (serial 76513359, ABS, 2003) shows as ABANDONED without a statement of use. http://bibliadelososagradasescrituras1569.blogspot.com/2013/07/biblias-con-y-sin-derechos-de-autor.html · https://www.trademarkia.com/reina-valera-1960-76513359

**2. Holder's terms of use**
- Without written permission: up to 500 verses, provided they are not ≥50 % of a book of the Bible nor ≥25 % of the total text of the work, non-commercial use, with the notice: "Texto bíblico: Reina-Valera 1960® © Sociedades Bíblicas en América Latina, 1960. Renovado © Sociedades Bíblicas Unidas, 1988. Utilizado con permiso." In video/electronic media the notice must appear on the product, the packaging and the credits. https://bibles.com/pages/american-bible-society-rights-and-permissions · https://sba.org.ar/politica-sobre-derechos-y-permisos-de-uso-de-los-textos-biblicos/
- Local church exception: bulletins, orders of service and non-commercial recordings only require the abbreviation "(RVR 1960)". https://www.sbch.cl/sitio/multimedia/permisos-de-uso/
- Requires written permission: apps/software, complete text, video/visual presentations beyond the limit, audio, song lyrics, AI. Contact: licensing@americanbible.org + the "Permission Request Form". https://www.americanbible.org/rights-and-permissions/

**3. APIs and data sources**
- API.Bible (ABS): does offer RVR1960 (it belongs to ABS itself); requires accepting a license per version; Starter $0 (5,000 calls/month, 3 licensed Bibles, non-commercial); caching allowed only for <500 consecutive verses and purged every ≤14 days → **not usable for a complete offline copy**; requires the copyright notice and the FUMS snippet on the web. https://scripture.api.bible/faq · https://docs.api.bible/common-questions/ · https://care.api.bible/article/369-understanding-api-bible-licensing
- Bible Gateway: no public API; the "API" packages on GitHub are scrapers. https://github.com/Glowstudent777/BibleGateway-API-NPM
- YouVersion Platform (platform.youversion.com): free REST API with per-version licenses accepted on the portal; RVR1960 is on YouVersion (id 149) by ABS/SBU agreement, but offline permission is negotiated case by case and the conditions are not public without an account. https://developers.youversion.com/api/licenses · https://blog.youversion.com/2010/10/reina-valera-1960-rvr60-now-available-offline-2/
- Faithlife/Biblia API (bibliaapi.com): includes RVR60; expressly forbids extracting the content into another database; requires the Biblia logo; "experimental" service. https://bibliaapi.com/docs/Available_Bibles · https://bibliaapi.com/docs/Terms_of_Use
- bolls.life: serves RV1960 with no published license (alongside NIV/ESV); its GPL only covers the code. Unauthorized distribution. https://bolls.life/static/bolls/app/views/languages.json · https://learnofchrist.com/resources/bolls-bible-api
- getbible.net: does not include RVR1960 (only old Reina-Valera editions); warns that copyrighted translations require the holder's permission. https://get.bible/bible-data-sets/ · https://github.com/getbible/v2/blob/master/translations.json
- GitHub (mrk214/bible-data-es-spa, develop4God/bible_versions, dscottpi/bibles, alejandroch1202/biblia-api…): RVR1960 JSON/SQLite under "MIT" that only covers the code; none credits a license for the text → unauthorized copies. https://github.com/mrk214/bible-data-es-spa · https://github.com/develop4God/bible_versions

**4. Free Spanish versions**
- Reina-Valera 1909: public domain (eBible.org). https://ebible.org/spaRV1909/copyright.htm
- Valera 1865: CC0 (Ministerios Valera 1865; SWORD module SpaRV1865). https://www.valera1865.org/leer-la-biblia/
- Reina-Valera Antigua (1569/1602) and Biblia del Oso: public domain (Bible Gateway: "no copyright information"). https://www.biblegateway.com/versions/Reina-Valera-Antigua-RVA-Biblia/
- Palabra de Dios para ti (2020, complete Bible, Asociación Bíblica Latinoamericana): CC BY 4.0. https://ebible.org/find/details.php?id=spapddpt
- La Biblia en Español Sencillo (2019, complete): CC BY 4.0. https://ebible.org/find/details.php?id=spabes
- Versión Biblia Libre (NT only): CC BY-SA 4.0. https://ebible.org/find/details.php?id=spavbl · https://github.com/seven1m/open-bibles
- NOT free: La Palabra Hispanoamericana (© Sociedad Bíblica de España 2010) https://www.bible.com/versions/28 ; Reina Valera Gómez (© H. Gómez 2010, downloadable text but copyrighted) https://reinavaleragomez.com/

**5. Formal permission path**
- The path is ABS: Permission Request Form → licensing@americanbible.org, stating passages, medium, % of the text, distribution and price. "Fair use" at no cost; beyond the limits it "is evaluated individually", donations are suggested; no published response time. https://www.americanbible.org/rights-and-permissions/
- Local societies (SBA, Chilean Bible Society) publish the same policy and form for non-commercial ministry use. Sociedad Bíblica Colombiana publishes no permissions page; contact: contacto@sbcol.org, (+57) 310 5354852, Calle 78 # 9-53 Bogotá. https://sociedadbiblicacolombiana.org/ · https://sba.org.ar/politica-sobre-derechos-y-permisos-de-uso-de-los-textos-biblicos/
- Mandatory attribution: the notice from point 2 on video, packaging and credits.

**Recommendation (lower → higher risk)**
1. **Request a license from ABS (licensing@americanbible.org) for an internal offline copy of RVR1960 in the tool**, copying the Sociedad Bíblica Colombiana. Non-commercial local church use, probably free or with a donation. While waiting for the answer, keep the current flow (copying per sermon), which falls under the local church exception: few verses, non-commercial video, "(RVR 1960)" abbreviation + full notice in the credits.
2. **Bundle a free text for offline mode** (RVR1909 or Valera 1865 CC0; or "Palabra de Dios para ti" CC BY 4.0 if modern language is wanted) and leave RVR1960 only as manual input/paste by the preacher. Zero risk; cost: the preacher reads RVR1960 and the subtitle would show a different version, unless it is pasted by hand.
3. **API.Bible Starter plan** to look up RVR1960 verse by verse at edit time (online), respecting the <500 verses/14 days cache and the copyright notice. Legal, but it does not meet the "complete offline text" requirement and adds a network dependency.
Discard: GitHub JSON/SQLite databases, bolls.life or scraping Bible Gateway: it is the technically most convenient option and the only clearly infringing one.
