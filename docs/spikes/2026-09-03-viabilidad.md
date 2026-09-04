# Spikes de viabilidad — 2026-09-03

Tres pruebas baratas antes de escribir la spec del Motor. Máquina: ASUS Vivobook,
i9-13900H (20 hilos), Iris Xe (Vulkan, Mesa), 23 GB RAM, Arch Linux. Artefactos temporales
en el scratchpad de la sesión; aquí quedan los números y las conclusiones.

## A. LLM local para redactar (llama.cpp b10793, Qwen3 GGUF Q4_K_M)

**Pregunta:** ¿puede un modelo local, en este hardware, redactar el guion desde la
transcripción de una prédica (27.5k tokens con marcas de tiempo)?

Benchmark corto (`llama-bench`, pp2048 / tg64):

| Modelo | Backend | Prompt (t/s) | Generación (t/s) |
|---|---|---|---|
| Qwen3 8B | Vulkan (iGPU) | 99.4 | 2.31 |
| Qwen3 8B | CPU 14 hilos | 36.4 | 5.25 |
| Qwen3 4B | Vulkan | 161.4 | 4.69 |
| Qwen3 4B | CPU | 63.8 | 9.20 |

Prueba real, 8B por CPU, prédica entera (27 532 tokens) + petición de metadata reutilizando
el prefijo:

| Petición | Tiempo | pp real | tg real | Calidad |
|---|---|---|---|---|
| Guion (3000 tokens) | 100.5 min | 18.2 t/s (25 min) | 0.66 t/s (75 min) | Degradada: bucle «Génesis 8:1 … 8:186», estructura solo de los minutos 9 a 15, pasaje «Génesis 6-9» |
| Metadata (533 tokens) | 14.5 min | caché de prefijo (119 tokens nuevos) | 0.62 t/s | Genérica |

A contexto largo la generación en CPU cae 8× respecto al benchmark y la calidad se
derrumba. **Un solo prompt con toda la transcripción no es viable en este hardware.**

Prueba por trozos: 10 minutos de prédica (3 198 tokens), extracción a JSON (tema,
versículos con minuto, frases textuales, un short):

| Modelo | Tiempo | pp | tg | Calidad |
|---|---|---|---|---|
| 4B CPU | 116 s | 61.7 | 7.52 | JSON válido; 5 versículos correctos (Gn 8:11-15); frases textuales reales; minutos con ±9 s de error |
| 8B CPU | 192 s | 37.1 | 4.27 | Igual, tema algo más preciso |

Extrapolado a una prédica de 78 min (8 trozos): **15 min con 4B, 26 min con 8B**, en
segundo plano mientras corre el render. Ninguno entendió «short de 30 a 60 s» (devolvieron
el trozo entero).

**Conclusiones de diseño:**
1. Redactor = map-reduce: extracción por trozos de 10 min → redacción corta sobre los extractos.
2. El LLM entrega frases textuales; el anclaje al SRT es determinista (`srt_util`), nunca el
   minuto que dice el modelo.
3. Candidatos a shorts por heurística (silencios + frases fuertes); el LLM solo titula.
4. Por defecto 4B; 8B con GPU dedicada o si el usuario acepta esperar. Vulkan en Iris Xe
   sirve para leer el prompt, no para generar.

## B. Empaquetar el motor Python para tres sistemas

**Pregunta:** ¿se puede distribuir faster-whisper + numpy + PIL + FastAPI como un binario
sin Python instalado, en Windows, macOS y Linux?

- Ruedas binarias para **Python 3.12** en `win_amd64`, `macosx arm64` y `manylinux`:
  faster-whisper, ctranslate2, onnxruntime, numpy, pillow, rembg, av, tokenizers,
  huggingface_hub, fastapi, uvicorn, pydantic. Todas presentes. Tamaño de ruedas: 83 MB
  (Windows), 55 MB (macOS), 123 MB (Linux).
- `llama-cpp-python` **no** tiene ruedas en PyPI: se empaqueta el binario `llama-server`
  de los releases de llama.cpp (34 MB la variante Vulkan) y se habla con él por HTTP.
- PyInstaller 6.22, Python 3.12.14 (mise), `--onedir`: compila en 20 s, **397 MB** (av 100 MB,
  ctranslate2 135 MB, onnxruntime 29 MB, numpy 42 MB). El binario corrió con entorno vacío
  (`env -i`), cargó large-v3 desde disco en 6.3 s, transcribió 20 s de audio en 16 s
  (con la CPU ocupada por el LLM) y levantó FastAPI en `127.0.0.1:<puerto aleatorio>` con
  token: 401 sin token, 200 con token.
- Tauri: en la máquina ya están rustc 1.98, cargo, webkit2gtk-4.1, gtk3, librsvg, Node 26.

**Conclusiones:** viable sin sorpresas. Los instaladores de Windows y macOS se compilan en
esas plataformas (GitHub Actions con matriz). `av` se puede evitar si se decodifica con
ffmpeg y se pasa numpy a faster-whisper (−100 MB).

## C. Licencia del texto bíblico RVR1960

**Pregunta:** ¿se puede empaquetar RVR1960 completo dentro de la app?

**1. Titularidad y vigencia**
- Titular: © 1960 Sociedades Bíblicas en América Latina; renovado © 1988 Sociedades Bíblicas Unidas (SBU). Los derechos los administra American Bible Society (ABS) como representante en EE.UU.; la marca "Reina-Valera 1960®" se reclama registrada y "solo usable bajo licencia". https://bibles.com/pages/american-bible-society-rights-and-permissions · https://www.biblegateway.com/versions/Reina-Valera-1960-RVR1960-Biblia/
- EE.UU.: obra de 1960 con aviso y renovación → 95 años desde publicación → dominio público el 1-ene-2056. https://guides.library.cornell.edu/copyright/publicdomain · https://en.wikipedia.org/wiki/Reina_Valera
- Colombia: Ley 23/1982 art. 21 = vida del autor + 80 años (personas naturales); art. 27 (reformado por Ley 1915/2018) = 70 años desde la primera publicación si el titular es persona jurídica (→ fin de 2030). El texto original del art. 27 (1982) daba solo 30 años a personas jurídicas, y la Ley 1915 art. 14 solo aplica a obras que no hubieran pasado ya al dominio público. Eso abre un argumento teórico (que el plazo habría vencido en 1990 en Colombia), pero no encontré ninguna fuente, doctrina ni sentencia que lo sostenga; SBU/ABS afirman vigencia mundial. No recomiendo apoyarse en él. https://normograma.mintic.gov.co/mintic/compilacion/docs/ley_0023_1982.htm · https://normograma.dian.gov.co/dian/compilacion/docs/ley_1915_2018.htm · https://www.wipo.int/edocs/lexdocs/laws/es/co/co012es.pdf
- Debate público: ABS insiste en que "no está en dominio público"; blogs hispanos lo aceptan y solo discuten la fecha (un post cita "2035" con la regla vieja de 75 años). La única solicitud de marca en USPTO (serie 76513359, ABS, 2003) figura ABANDONADA sin declaración de uso. http://bibliadelososagradasescrituras1569.blogspot.com/2013/07/biblias-con-y-sin-derechos-de-autor.html · https://www.trademarkia.com/reina-valera-1960-76513359

**2. Términos de uso del titular**
- Sin permiso escrito: hasta 500 versículos, que no sean ≥50 % de un libro bíblico ni ≥25 % del texto total de la obra, uso no comercial, con la leyenda: "Texto bíblico: Reina-Valera 1960® © Sociedades Bíblicas en América Latina, 1960. Renovado © Sociedades Bíblicas Unidas, 1988. Utilizado con permiso." En video/electrónico, la leyenda debe ir en el producto, el empaque y los créditos. https://bibles.com/pages/american-bible-society-rights-and-permissions · https://sba.org.ar/politica-sobre-derechos-y-permisos-de-uso-de-los-textos-biblicos/
- Excepción iglesia local: boletines, órdenes de culto y grabaciones no comerciales solo requieren la sigla "(RVR 1960)". https://www.sbch.cl/sitio/multimedia/permisos-de-uso/
- Requiere permiso escrito: apps/software, texto completo, presentaciones de video/visuales fuera del límite, audio, letras de canciones, IA. Contacto: licensing@americanbible.org + formulario "Permission Request Form". https://www.americanbible.org/rights-and-permissions/

**3. APIs y fuentes de datos**
- API.Bible (ABS): sí ofrece RVR1960 (es de la propia ABS); requiere aceptar licencia por versión; Starter $0 (5.000 llamadas/mes, 3 Biblias licenciadas, no comercial); caché permitida solo <500 versículos consecutivos y purgada cada ≤14 días → **no sirve para copia offline completa**; exige aviso de copyright y snippet FUMS en web. https://scripture.api.bible/faq · https://docs.api.bible/common-questions/ · https://care.api.bible/article/369-understanding-api-bible-licensing
- Bible Gateway: sin API pública; los paquetes "API" en GitHub son scrapers. https://github.com/Glowstudent777/BibleGateway-API-NPM
- YouVersion Platform (platform.youversion.com): API REST gratuita con licencias por versión aceptadas en el portal; RVR1960 está en YouVersion (id 149) por acuerdo ABS/SBU, pero el permiso offline se negocia caso a caso y las condiciones no son públicas sin cuenta. https://developers.youversion.com/api/licenses · https://blog.youversion.com/2010/10/reina-valera-1960-rvr60-now-available-offline-2/
- Faithlife/Biblia API (bibliaapi.com): incluye RVR60; prohíbe expresamente extraer el contenido a otra base de datos; exige logo Biblia; servicio "experimental". https://bibliaapi.com/docs/Available_Bibles · https://bibliaapi.com/docs/Terms_of_Use
- bolls.life: sirve RV1960 sin licencia publicada (junto a NIV/ESV); su GPL cubre solo el código. Distribución no autorizada. https://bolls.life/static/bolls/app/views/languages.json · https://learnofchrist.com/resources/bolls-bible-api
- getbible.net: no incluye RVR1960 (solo Reina-Valera antiguas); advierte que las traducciones con copyright requieren permiso del titular. https://get.bible/bible-data-sets/ · https://github.com/getbible/v2/blob/master/translations.json
- GitHub (mrk214/bible-data-es-spa, develop4God/bible_versions, dscottpi/bibles, alejandroch1202/biblia-api…): JSON/SQLite de RVR1960 bajo "MIT" que solo cubre el código; ninguno acredita licencia del texto → copias no autorizadas. https://github.com/mrk214/bible-data-es-spa · https://github.com/develop4God/bible_versions

**4. Versiones en español libres**
- Reina-Valera 1909: dominio público (eBible.org). https://ebible.org/spaRV1909/copyright.htm
- Valera 1865: CC0 (Ministerios Valera 1865; módulo SWORD SpaRV1865). https://www.valera1865.org/leer-la-biblia/
- Reina-Valera Antigua (1569/1602) y Biblia del Oso: dominio público (Bible Gateway: "sin información de copyright"). https://www.biblegateway.com/versions/Reina-Valera-Antigua-RVA-Biblia/
- Palabra de Dios para ti (2020, Biblia completa, Asociación Bíblica Latinoamericana): CC BY 4.0. https://ebible.org/find/details.php?id=spapddpt
- La Biblia en Español Sencillo (2019, completa): CC BY 4.0. https://ebible.org/find/details.php?id=spabes
- Versión Biblia Libre (solo NT): CC BY-SA 4.0. https://ebible.org/find/details.php?id=spavbl · https://github.com/seven1m/open-bibles
- NO libres: La Palabra Hispanoamericana (© Sociedad Bíblica de España 2010) https://www.bible.com/versions/28 ; Reina Valera Gómez (© H. Gómez 2010, texto descargable pero con copyright) https://reinavaleragomez.com/

**5. Vía formal de permiso**
- La vía es ABS: Permission Request Form → licensing@americanbible.org, indicando pasajes, medio, % del texto, distribución y precio. "Fair use" sin costo; fuera de límites "se evalúa individualmente", se sugieren donaciones; sin plazo de respuesta publicado. https://www.americanbible.org/rights-and-permissions/
- Sociedades locales (SBA, SB Chilena) publican la misma política y formulario para uso ministerial no comercial. Sociedad Bíblica Colombiana no publica página de permisos; contacto: contacto@sbcol.org, (+57) 310 5354852, Calle 78 # 9-53 Bogotá. https://sociedadbiblicacolombiana.org/ · https://sba.org.ar/politica-sobre-derechos-y-permisos-de-uso-de-los-textos-biblicos/
- Atribución obligatoria: la leyenda del punto 2 en video, empaque y créditos.

**Recomendación (menor → mayor riesgo)**
1. **Pedir licencia a ABS (licensing@americanbible.org) para copia interna offline de RVR1960 en la herramienta**, copiando a la Sociedad Bíblica Colombiana. Uso no comercial de iglesia local, probablemente gratis o con donación. Mientras responde, seguir con el flujo actual (copiar por prédica), que cae en la excepción de iglesia local: pocos versículos, video no comercial, leyenda "(RVR 1960)" + aviso completo en créditos.
2. **Empaquetar un texto libre para el modo offline** (RVR1909 o Valera 1865 CC0; o "Palabra de Dios para ti" CC BY 4.0 si se quiere lenguaje moderno) y dejar RVR1960 solo como entrada manual/pegado del pastor. Riesgo cero; costo: el pastor lee RVR1960 y el subtítulo diría otra versión, salvo que se pegue a mano.
3. **API.Bible plan Starter** para consultar RVR1960 por versículo en tiempo de edición (online), respetando caché <500 versículos/14 días y aviso de copyright. Legal, pero no cumple el requisito de "texto completo offline" y añade dependencia de red.
Descartar: bases JSON/SQLite de GitHub, bolls.life o scraping de Bible Gateway — es la opción técnicamente más cómoda y la única claramente infractora.
