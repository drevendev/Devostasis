# Conformance cases

Identifiers come from the research units that defined them and are never
reused. "Test" names the pytest function that implements the case.

## Observation contract (PV-OBS-001)

| Case | Meaning | Test |
| --- | --- | --- |
| C1 | observed zero is AVAILABLE with value 0 | `test_c1_observed_zero_is_available_with_value_zero` |
| C2 | tier limitation is UNAVAILABLE without value | `test_c2_tier_limitation_is_unavailable_without_value`, adapter `test_c2_c3_c7_http_failures_become_explicit_statuses` |
| C3 | permission denial is FORBIDDEN | same |
| C4 | truncated history is PARTIAL with coverage | `test_c4_truncated_history_is_partial_with_coverage`, adapter `test_c4_pagination_cap_is_partial` |
| C5 | stale evidence keeps its value but is not fresh | `test_c5_stale_evidence_keeps_value_but_is_not_fresh` |
| C6 | connector ambiguity is UNKNOWN | `test_c6_connector_ambiguity_is_unknown` |
| C7 | transient failure is ERROR | `test_c7_transient_failure_is_error_not_unknown` |

## Vitals V0.x repairs

| Case | Meaning | Test |
| --- | --- | --- |
| T1 | configured CI with zero runs is NO_RECENT_RUNS | `test_t1_no_recent_runs_is_neither_clean_nor_uninstrumented` |
| R3 | zero observed activity with an unavailable channel is DEGRADED DORMANT | `test_r3_zero_activity_with_unavailable_channel_is_degraded_dormant_lower_bound` |
| V0.7 precedence | unresolved sibling blocks PASS, never hides FAIL | `test_v0_7_unresolved_sibling_blocks_pass_but_not_fail` |
| R54 | same-revision retry keeps historical failure | `test_r54_same_revision_retry_success_keeps_historical_failure` |
| R55 | retry-count invariance | `test_r55_retry_count_invariance` |
| R56 | newer revision is a distinct sample | `test_r56_newer_revision_is_a_distinct_sample` |
| R57 | order and surface invariance | `test_r57_order_and_surface_invariance` |

## Seven-Vital taxonomy (PV-VIT-010, PV-VIT-012)

| Case | Meaning | Test |
| --- | --- | --- |
| V1-01 | empty repository with complete observations | `test_v1_01_empty_repository_with_complete_observations` |
| V1-02 | commits without change requests or targets | `test_v1_02_commits_without_change_requests_or_targets` |
| V1-03 to V1-04 | linkage bands | `test_direction_bands` |
| V1-05 | forbidden planning enumeration is UNKNOWN | `test_v1_05_forbidden_planning_enumeration_is_unknown_not_undeclared` |
| V1-06 | clear Debt with heavy Clutter | `test_v1_06_clear_debt_can_coexist_with_heavy_clutter` |
| V1-07 | mapping change makes history incomparable | `test_art_04_rpt_10_semantic_config_change_is_incomparable` |
| V1-08 | fail then rerun pass | `test_r54_...` |
| V1-10 | unavailable channel never becomes zero | `test_v1_10_unavailable_channel_never_becomes_zero_but_lower_bound_still_classifies` |
| V1-11 | branch enumeration unavailable cannot emit exact CLEAN | `test_v1_11_branch_enumeration_unavailable_cannot_emit_exact_clean` |
| V1-12 | dependency metadata, no aggregate | `test_v1_12_snapshot_carries_dependency_metadata_and_no_aggregate` |
| V1-13 | no calibrated Debt policy | `test_v1_13_no_calibrated_policy_keeps_large_debt_as_present` |
| V1-14 | mass-linking yields neutral FULLY_LINKED | `test_v1_14_mass_linking_yields_neutral_fully_linked_with_diagnostic` |
| V1-15 | provider and order invariance | `test_r57_order_and_surface_invariance`, `test_g4_same_observations_produce_identical_snapshot_digest` |

## Artifact and history (PV-ARTIFACT-001..003, PV-REPORT-001)

| Case | Meaning | Test |
| --- | --- | --- |
| ART-01 / RPT-1 | baseline without fabricated delta | `test_art_01_first_bundle_is_baseline_without_fabricated_delta` |
| ART-02 / ART-14 | repeatability and cross-implementation identity | `test_art_02_and_art_14_identity_is_reproducible_across_builds` |
| ART-03 / RPT-3 | history gap | `test_rpt_3_history_gap_keeps_current_snapshot_and_infers_no_change` |
| ART-04 / RPT-10 | semantic boundary is INCOMPARABLE | `test_art_04_rpt_10_semantic_config_change_is_incomparable` |
| ART-06 | neutral rendering | `test_art_06_neutral_rendering_of_fully_linked_and_present` |
| ART-07 | immutability | `test_art_07_immutability` |
| ART-12 | renderer purity | `test_art_20_21_12_persisted_bundle_verifies_from_its_own_contents`, CLI `test_build_verify_render_and_index` |
| ART-13 / ART-22 | acyclic identity | `test_art_13_and_art_22_preimage_excludes_post_identity_members` |
| ART-16 | observed_at is identity-bearing | `test_art_16_observed_at_is_identity_bearing` |
| ART-17 | effective config collision | `test_art_17_config_change_changes_bundle_id`, `test_art_17_byte_affecting_option_changes_the_digest` |
| ART-18 | optional member identity | `test_art_18_enabled_html_without_renderer_fails_closed`, `test_art_18_optional_member_presence_is_identity_bearing` |
| ART-19 | config canonicalization invariance | `test_art_19_*` |
| ART-20 / ART-21 | persisted effective config preimage | `test_art_20_21_12_persisted_bundle_verifies_from_its_own_contents` |
| RPT-2 | interval from previous successful bundle | `test_second_run_is_comparable_with_unchanged_and_changed_transitions` |
| CONFIG_IDENTITY_UNCLASSIFIED | unknown config fails closed | `test_unclassified_configuration_input_fails_closed` |

Cases not yet implemented as tests are listed in the ROADMAP under the
synthetic fixture suite.
