# Conformance cases

Identifiers come from the research units that defined them and are never
reused. "Test" names the pytest function that implements the case, or the
executable vector that does: `vector:<CASE>` is the vector with that case id in
`tests/vectors/`, run by `devostasis vectors` and by the test suite
([vectors.md](vectors.md)). Every vector in the corpus is cited here and every
citation resolves; both directions are a test (`test_spec_drift.py`).

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

## Calibration repairs (PV-CAL-002, PV-CAL-003)

| Case | Meaning | Test |
| --- | --- | --- |
| FLOW-EQ-01 | empty queue with a slow historical median is NO_QUEUE | `test_flow_eq_01_empty_queue_with_slow_historical_median_is_no_queue` |
| FLOW-EQ-02 | an extreme historical median cannot gridlock an empty queue | `test_flow_eq_02_extreme_historical_median_cannot_gridlock_an_empty_queue` |
| FLOW-EQ-03 | a live queue keeps the > 168 h predicate | `test_flow_eq_03_live_queue_keeps_the_congested_median_threshold` |
| FLOW-EQ-04 | a live large queue keeps the gridlocked predicate | `test_flow_eq_04_live_large_queue_keeps_the_gridlocked_predicate` |
| FLOW-EQ-05 | a missing open count never becomes an empty queue | `test_flow_eq_05_missing_open_count_never_becomes_an_empty_queue` |
| FLOW-EQ-06 | provider and order invariance | `test_flow_eq_06_provider_and_order_invariance` |
| FLOW-PREC-01 | sub-hour medians are preserved | `test_flow_prec_01_sub_hour_medians_are_preserved` |
| FLOW-PREC-02 | an even sample uses the exact arithmetic mean | `test_flow_prec_02_even_sample_uses_the_exact_arithmetic_mean` |
| FLOW-PREC-03 / 04 | 604800 s is not > 168 h, 604801 s is | `test_flow_prec_03_04_lower_boundary_is_exact_in_seconds` |
| FLOW-PREC-05 | 1209600 s is not > 336 h, 1209601 s is | `test_flow_prec_05_upper_boundary_is_exact_in_seconds` |
| FLOW-PREC-06 | empty queue takes precedence over any median | `test_flow_prec_06_empty_queue_takes_precedence_over_any_median` |
| FLOW-PREC-07 | the median is invariant under permutation | `test_flow_prec_07_median_is_invariant_under_permutation` |
| FLOW-PREC-08 | fractional timestamps stay exact | `test_flow_prec_08_fractional_timestamps_are_exact` |
| FLOW-PREC-09 | partial evidence stays UNKNOWN | `test_flow_prec_09_partial_evidence_stays_unknown` |
| PULSE-CAP-01 | invariant lower bound forces one band | `test_pulse_cap_01_invariant_lower_bound_forces_one_band`, `test_pulse_cap_01_exact_days_with_capped_commits_is_forced_quiet` |
| PULSE-CAP-02 | a reachable boundary lists every reachable band, no exact band | `test_pulse_cap_02_boundary_crossing_lists_every_reachable_band_and_no_exact_band` |
| PULSE-CAP-03 | an unconstrained required tail is UNKNOWN | `test_pulse_cap_03_unconstrained_required_tail_is_unknown` |
| PULSE-CAP-04 | optional channels cannot make a capped required input exact | `test_pulse_cap_04_optional_channel_cannot_make_capped_required_input_exact` |
| PULSE-CAP-05 | pagination metadata is non-semantic | `test_pulse_cap_05_pagination_metadata_is_non_semantic` |
| CI-OUTCOME-01 | timed_out is VERIFY_FAIL | `test_ci_outcome_01_timed_out_is_a_verification_failure` |
| CI-OUTCOME-02 | startup_failure is UNKNOWN | `test_ci_outcome_02_startup_failure_is_unknown_not_a_project_failure` |
| CI-OUTCOME-03 | a non-completed status outranks any conclusion | `test_ci_outcome_03_current_execution_state_outranks_a_conclusion` |
| CI-OUTCOME-04 | unknown conclusions fail closed | `test_ci_outcome_04_unknown_future_conclusions_fail_closed` |

## Gauges and demand (PV-REV-GAUGE-001, PV-ROLE-001)

| Case | Meaning | Test |
| --- | --- | --- |
| GAUGE-J1 | UNKNOWN or not-applicable Vital has value null | `test_unknown_and_not_applicable_states_have_no_value` |
| GAUGE-J2 | a DEGRADED bound carries a qualifier, never exact | `test_degraded_results_carry_a_bound_qualifier` |
| GAUGE-J3 | within a band the gauge never decreases with the phenomenon | `test_gauges_are_monotone_inside_a_band` |
| GAUGE-J4 | gauges of different Vitals are never ranked together | `test_role_01_same_level_gauge_invariance` |
| GAUGE-J5 | no aggregate over gauges | `test_demand_rows_and_attention_order` (`aggregate` is null) |
| GAUGE-J6 | constants or semantics change only with a new identifier | by construction: `devostasis.gauge.v1` is frozen in `gauges.py` |
| GAUGE-J7 | gauges.json is reproducible and identity-bound | `test_every_band_lands_inside_its_declared_range`, `test_art_20_21_12_persisted_bundle_verifies_from_its_own_contents` |
| ROLE-01 | same level, only gauges change, order unchanged | `test_role_01_same_level_gauge_invariance` |
| ROLE-02 | a Vital without a band is UNRESOLVED and sorts first | `test_unknown_vital_is_unresolved_and_first` |
| ROLE-03 | aggregate stays null | `test_demand_rows_and_attention_order` |
| ROLE-04 | overrides require a mapping version and valid values | `test_demand_overrides_require_a_mapping_version_and_valid_values` |

## Artifact and history (PV-ARTIFACT-001..005, PV-REPORT-001)

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
| ART-23 | member profile derived from the stored config | `test_art_23_member_profile_derives_from_the_stored_config` |
| ART-24 | replay only from a validated stored config | `test_art_24_replay_happens_only_from_a_validated_stored_config` |
| ART-25 | stored config schema verification | `test_art_25_stored_config_is_schema_validated_before_any_semantic_use`, `test_legacy_effective_config_v1_is_still_verifiable` |
| RPT-2 | interval from previous successful bundle | `test_second_run_is_comparable_with_unchanged_and_ordered_transitions` |
| RPT-7 | rename and transfer continuity by immutable project id | `test_rpt_7_a_renamed_repository_keeps_one_history`, `test_a_transfer_to_another_owner_is_the_same_event`, `test_an_old_name_reused_by_a_new_repository_is_a_new_project`, `test_a_locator_held_by_another_project_fails_closed`, `test_without_an_immutable_id_the_locator_is_the_identity` |
| rule boundary | a Vital with a changed rule id is INCOMPARABLE on its own | `test_rule_version_boundary_makes_one_vital_incomparable_inside_a_comparable_bundle` |
| CONFIG_IDENTITY_UNCLASSIFIED | unknown config fails closed | `test_unclassified_configuration_input_fails_closed` |

## Band ordering (PV-BAND-ORDER-001)

The fifteen cases the accepted contract requires, under the names it gives
them, executable as vectors. A case that names several pairs executes all of
them and passes only when every pair does, so a result citing `ORDER-nn` is a
result about research case `ORDER-nn` and nothing else. The claims that no pair
of bands can express are beside them in `tests/conformance/test_band_order.py`.

| Case | Meaning | Test |
| --- | --- | --- |
| ORDER-01 | `CLUTTER_TRANSITIVE_IMPROVEMENT`: HEAVY→LIGHT is IMPROVED, the reverse WORSENED | `vector:ORDER-01` |
| ORDER-02 | `FLOW_LIVE_QUEUE_ORDER`: GRIDLOCKED→CONGESTED→MOVING follows the WORSENED/IMPROVED direction | `vector:ORDER-02` |
| ORDER-03 | `FLOW_NO_QUEUE_INCOMPARABLE`: NO_QUEUE against MOVING and against GRIDLOCKED is CHANGED | `vector:ORDER-03` |
| ORDER-04 | `INTEGRITY_ESTABLISHED_CHAIN`: FAILING→FLAKY→CLEAN improving, the reverse worsening | `vector:ORDER-04` |
| ORDER-05 | `INTEGRITY_SPARSE_CHAIN`: SPARSE_MIXED→SPARSE is IMPROVED, the reverse WORSENED | `vector:ORDER-05` |
| ORDER-06 | `INTEGRITY_CROSS_FAMILY`: SPARSE→CLEAN, SPARSE_MIXED→FAILING and NO_RECENT_RUNS→CLEAN are CHANGED | `vector:ORDER-06` |
| ORDER-07 | `PULSE_NEUTRALITY`: every unequal Pulse band pair is CHANGED | `vector:ORDER-07` |
| ORDER-08 | `HORIZON_NEUTRALITY`: every unequal Horizon band pair is CHANGED | `vector:ORDER-08` |
| ORDER-09 | `DIRECTION_NEUTRALITY`: SCATTERED→FULLY_LINKED is CHANGED, and so is the reverse | `vector:ORDER-09` |
| ORDER-10 | `DEBT_NEUTRALITY`: PRESENT against CLEAR is CHANGED | `vector:ORDER-10` |
| ORDER-11 | `DEGRADED_NEVER_ORDERED`: a DEGRADED evaluation on either side emits no direction | `vector:ORDER-11` |
| ORDER-12 | `UNKNOWN_OBSERVABILITY_PRECEDENCE`: an appearing or disappearing band uses the observability transitions | `vector:ORDER-12` |
| ORDER-13 | `RULE_VERSION_BOUNDARY_PRECEDENCE`: a changed rule id stays INCOMPARABLE inside a declared chain | `vector:ORDER-13` |
| ORDER-14 | `GAUGE_INVARIANCE`: a gauge that moved inside unchanged bands stays UNCHANGED | `vector:ORDER-14`, `test_a_gauge_that_moved_inside_one_band_is_not_a_direction` |
| ORDER-15 | `CROSS_VITAL_PROHIBITION`: no rank of one Vital is compared with a rank of another | `vector:ORDER-15`, `test_no_order_is_declared_across_vitals`, `test_the_delta_declares_the_ordering_contract_it_applied_and_no_aggregate` |

Two of the accepted cases are half structural. ORDER-14 states that *changing
only a gauge* leaves the classification alone: a vector states bands and
derived metrics, so it proves that the delta ignores the moved metric, and the
pytest case beside it computes the gauge and proves it actually moved. ORDER-15
states that a comparator does not exist, which no pair of bands can express;
the vector proves that two Vitals moving in opposite directions are classified
independently and that a band two Vitals share is not ordered by the other
one's chain, and the pytest cases prove the absence itself.

Beyond the accepted set, this implementation keeps three cases of its own. They
carry `DEV-ORDER` identifiers, which are local to this repository and belong to
no research unit, so a result citing one can never be read as evidence about an
accepted case.

| Case | Meaning | Test |
| --- | --- | --- |
| DEV-ORDER-01 | Clutter improves one adjacent rank, not only across the transitive step ORDER-01 states | `vector:DEV-ORDER-01` |
| DEV-ORDER-02 | Clutter improves across the whole chain, HEAVY→CLEAN | `vector:DEV-ORDER-02` |
| DEV-ORDER-03 | NO_QUEUE is incomparable with CONGESTED too, the band between the two ORDER-03 names | `vector:DEV-ORDER-03` |
| ordering needs a comparable pair | a BASELINE, HISTORY_GAP or INCOMPARABLE comparison reports no direction | `test_a_bundle_that_is_not_comparable_never_reports_a_direction` |
| gauges establish no order | a gauge that moved inside a band is UNCHANGED | `test_a_gauge_that_moved_inside_one_band_is_not_a_direction` |
| ordered bands are emittable | every ordered band is one its Vital emits, and the unordered ones are exactly the descriptive and evidence states | `test_every_ordered_band_is_a_band_its_vital_can_emit`, `test_the_bands_left_unordered_are_exactly_the_descriptive_and_evidence_states` |

## The vector runner (target B1)

| Case | Meaning | Test |
| --- | --- | --- |
| runner | a wrong expectation fails, a correct one passes | `test_a_wrong_expectation_fails_and_says_what_it_expected`, `test_a_correct_vector_passes` |
| fail closed | an unknown kind, key, vital, comparison status or duplicate case id is an error, never a skip | `test_a_vector_that_cannot_run_is_rejected_at_load_time`, `test_a_comparison_status_the_engine_does_not_know_is_rejected`, `test_two_files_may_not_claim_the_same_case_id`, `test_a_missing_path_is_an_error_not_an_empty_run` |
| evidence is contract-checked | an envelope that violates the observation contract fails the vector | `test_an_envelope_that_violates_the_observation_contract_is_a_failure_not_a_pass` |
| published schema | the schema and the validator agree on the shape, including the partial evidence envelope and the comparison statuses | `test_the_published_vector_schema_and_the_runner_agree_on_the_shape`, `test_the_schema_publishes_the_partial_envelope_the_runner_actually_accepts`, `test_every_envelope_in_the_corpus_is_one_the_published_schema_accepts` |
| corpus | every vector in the corpus runs, and every declared kind is exercised | `test_conformance_vector`, `test_every_kind_the_format_declares_is_exercised_by_the_corpus` |

Cases not yet implemented as tests (T2..T9, R1, R2, R4..R53, ART-05,
ART-08..ART-11, ART-15, RPT-4..RPT-6, RPT-9) are listed in the ROADMAP under the
synthetic fixture suite. PV-TEST-001 will deliver them as executable JSON
vectors in the format of [vectors.md](vectors.md); the runner that will execute
them exists and is proved by the cases above.
