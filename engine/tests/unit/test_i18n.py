import pytest

from lychnia import i18n


def test_es_and_en_have_the_same_keys():
    es = i18n.load_messages("es")
    en = i18n.load_messages("en")
    assert set(es) == set(en)
    assert es  # not empty


def test_default_language_is_spanish(monkeypatch):
    monkeypatch.delenv("LYCHNIA_LANG", raising=False)
    assert i18n.current_language() == "es"


def test_env_var_selects_language(monkeypatch):
    monkeypatch.setenv("LYCHNIA_LANG", "en")
    assert i18n.current_language() == "en"
    assert i18n.t("validation.cut_end_before_start") == i18n.load_messages("en")["validation.cut_end_before_start"]


def test_unknown_env_language_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("LYCHNIA_LANG", "xx")
    assert i18n.current_language() == "es"


def test_t_formats_params():
    msg = i18n.t("validation.missing_field", lang="en", field="cut.end")
    assert "cut.end" in msg


def test_unknown_key_raises():
    with pytest.raises(KeyError):
        i18n.t("nope.missing", lang="es")


def test_flatten_nests_with_dots():
    assert i18n.flatten({"a": {"b": "x"}, "c": "y"}) == {"a.b": "x", "c": "y"}


def test_available_languages():
    assert i18n.available_languages() == ["en", "es"]
