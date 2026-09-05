"""Every message key used in code exists in es and en; no operator text is inlined."""
import re
from pathlib import Path

from lychnia import i18n

PACKAGE = Path(i18n.__file__).resolve().parents[1]
KEY_RE = re.compile(r"""["'](?:validation|status|action|task|template)\.[a-z0-9_]+["']""")
# accented lowercase words inside string literals are the fingerprint of inlined Spanish prose
SPANISH_RE = re.compile(r"""["'][^"'\n]*\b[a-z]*[áéíóúñ][a-z]*\b[^"'\n]*["']""")
ALLOWED_SPANISH_FILES = set()   # add a relative path here only with a comment explaining why


def _sources() -> list[Path]:
    return [p for p in PACKAGE.rglob("*.py") if ".venv" not in p.parts]


def _used_keys() -> set[str]:
    keys: set[str] = set()
    for src in _sources():
        keys.update(m.strip("\"'") for m in KEY_RE.findall(src.read_text(encoding="utf-8")))
    return keys


def test_every_key_used_in_code_exists_in_both_catalogs():
    used = _used_keys()
    assert used, "the scan found no keys; the regex or the package path is wrong"
    for lang in ("es", "en"):
        catalog = i18n.load_messages(lang)
        missing = sorted(k for k in used if k not in catalog)
        assert not missing, f"keys missing in {lang}.toml: {missing}"


def test_dynamic_status_keys_exist():
    from lychnia.orchestrator.status import State
    for lang in ("es", "en"):
        catalog = i18n.load_messages(lang)
        for state in State:
            assert f"status.{state.value}" in catalog, (lang, state)


def test_no_inlined_spanish_in_code():
    offenders = []
    for src in _sources():
        rel = src.relative_to(PACKAGE).as_posix()
        if rel in ALLOWED_SPANISH_FILES:
            continue
        for n, line in enumerate(src.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            if SPANISH_RE.search(line):
                offenders.append(f"{rel}:{n}: {line.strip()}")
    assert not offenders, "\n".join(offenders)
