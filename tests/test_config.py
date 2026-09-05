"""Configuration resolution and effective-config identity (ART-17, ART-18, ART-19, CONFIG_IDENTITY_UNCLASSIFIED)."""

import pytest

from devostasis.config import ConfigError, load_config_dict, single_project


def _config(**project):
    return load_config_dict({"config_version": "1", "projects": [dict({"repo": "acme/widget"}, **project)]})


def test_defaults_resolve_to_a_stable_effective_config():
    project = _config().projects[0]
    effective = project.effective_bundle_config()
    assert effective["planning_source"] == "milestones" and effective["debt_mapping"] is None
    assert effective["report_html"] == "DISABLED" and effective["activity"] == "ENABLED"


def test_art_19_omitted_default_and_explicit_default_canonicalize_identically():
    implicit = _config().projects[0]
    explicit = _config(planning={"source": "milestones"}, report_html=False, locale="en", activity={"enabled": True, "list_cap": 50}).projects[0]
    assert implicit.effective_config_digest() == explicit.effective_config_digest()


def test_art_19_reordered_debt_labels_canonicalize_identically():
    a = _config(debt={"labels": ["b", "a"], "mapping_version": "1"}).projects[0]
    b = _config(debt={"mapping_version": "1", "labels": ["a", "b"]}).projects[0]
    assert a.effective_config_digest() == b.effective_config_digest()


def test_art_17_byte_affecting_option_changes_the_digest():
    a = _config(activity={"list_cap": 50}).projects[0]
    b = _config(activity={"list_cap": 10}).projects[0]
    assert a.effective_config_digest() != b.effective_config_digest()


def test_art_18_optional_member_presence_is_identity_bearing():
    a = _config(report_html=False).projects[0]
    b = _config(report_html=True).projects[0]
    assert a.effective_config_digest() != b.effective_config_digest()


def test_unclassified_configuration_input_fails_closed():
    with pytest.raises(ConfigError, match="CONFIG_IDENTITY_UNCLASSIFIED"):
        _config(theme="clinical")
    with pytest.raises(ConfigError, match="CONFIG_IDENTITY_UNCLASSIFIED"):
        load_config_dict({"config_version": "1", "projects": [{"repo": "a/b"}], "webhook": "x"})


def test_debt_mapping_validation():
    with pytest.raises(ConfigError):
        _config(debt={"labels": [], "mapping_version": "1"})
    with pytest.raises(ConfigError):
        _config(debt={"labels": ["x"]})
    project = _config(debt={"labels": ["x", "x", "y"], "mapping_version": "v"}).projects[0]
    assert project.debt_mapping == {"labels": ["x", "y"], "mapping_version": "v"}


def test_semantic_config_ignores_presentation_options():
    a = _config(activity={"list_cap": 5}).projects[0]
    b = _config(activity={"list_cap": 500}).projects[0]
    assert a.semantic_config() == b.semantic_config()
    c = _config(planning={"source": "none"}).projects[0]
    assert a.semantic_config() != c.semantic_config()


def test_single_project_and_repo_validation():
    project = single_project("acme/widget", debt={"labels": ["debt"], "mapping_version": "1"})
    assert project.project_key == "github.com/acme/widget"
    with pytest.raises(ConfigError):
        single_project("not-a-repo")
    with pytest.raises(ConfigError):
        load_config_dict({"config_version": "1", "projects": [{"repo": "a/b"}, {"repo": "a/b"}]})
