#!/usr/bin/env python3
"""
Contract tests for the MCP tooling scaffold (plugin/pythonpath/tools/).

These deliberately do NOT require a running LibreOffice instance or the
`uno`/`unohelper` modules -- unlike plugin/test_plugin.py (needs a live
extension) or tests/test_client.py (needs `soffice` on PATH), this suite
only checks the scaffold's own contract:

  * every scaffolded tool from the design spec is registered exactly once,
    under its exact name, in its expected module -- checked by name, not
    just by count, so a tool silently landing in the wrong module (or a
    typo'd name that still keeps the count right) fails loudly;
  * none collide with the original 32 compatibility tool names;
  * every remaining stub handler (status="stub") returns the spec's error
    envelope shape with code NOT_IMPLEMENTED, regardless of the arguments
    passed in;
  * tools with status="implemented" (currently core_runtime.py's 12) stay
    marked as such, so a bad merge/rebase reverting one to "stub" is caught;
  * merge_into() never overwrites a pre-existing tool entry unless told to.

When a stub body gets a real implementation, flip its status="implemented"
in the @register_tool call (see registry.py) and move its coverage out of
this file's generic "returns NOT_IMPLEMENTED" check into a real behavioral
test file next to it -- see tests/test_core_runtime.py for the pattern
used for the first 12. This file is not meant to grow real per-tool
behavioral coverage in place.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "plugin", "pythonpath"))

from tools import get_registry  # noqa: E402
from tools.envelope import ERROR_CODES  # noqa: E402
from tools.registry import merge_into, schema  # noqa: E402

# The 32 spec tools explicitly marked "(existing)" (5 in document/session
# lifecycle, 27 in Writer text/navigation/editing/search/review). These
# already live in plugin/pythonpath/mcp_server.py and must never be
# shadowed by a scaffold stub.
EXISTING_COMPAT_TOOLS = {
    "list_open_documents", "create_document_live", "get_document_info_live",
    "save_document_live", "export_document_live",
    "insert_text_live", "get_text_content_live", "format_text_live",
    "get_paragraph_count_live", "get_document_outline_live", "get_paragraph_live",
    "get_paragraphs_range_live", "goto_paragraph_live", "goto_position_live",
    "get_cursor_position_live", "get_context_around_cursor_live", "select_paragraph_live",
    "select_text_range_live", "delete_selection_live", "replace_selection_live",
    "find_text_live", "find_and_replace_live", "find_and_replace_all_live",
    "get_comments_live", "add_comment_live", "get_track_changes_status_live",
    "set_track_changes_live", "get_tracked_changes_live", "accept_tracked_change_live",
    "reject_tracked_change_live", "accept_all_changes_live", "reject_all_changes_live",
}
assert len(EXISTING_COMPAT_TOOLS) == 32, "spec's own baseline is 32 tools -- update this set, not the count"

# Expected registrations per scaffold module, by exact tool name -- Phase A
# (core runtime, document lifecycle, undo/view/selection, styles) and
# Phase B - Writer complete (text/nav/editing, page layout/publishing,
# tables/sections/notes/content-controls/mail-merge).
EXPECTED_BY_MODULE = {
    "core_runtime": {
        "get_server_info_live", "get_capabilities_live", "get_tool_schema_live",
        "list_tools_live", "set_tool_profile_live", "get_session_state_live",
        "ping_live", "batch_execute_live", "validate_tool_call_live",
        "get_recent_errors_live", "get_diagnostics_live", "clear_diagnostics_live",
        # New tool, 2026-08-22 (Brian's new-tools assignment, priority #8,
        # not part of the original spec this module was sourced from) --
        # installation-level font listing, not document-scoped, same as
        # get_server_info_live above.
        "list_fonts_live",
    },
    "document_lifecycle": {
        "get_active_document_live", "activate_document_live", "open_document_live",
        "open_from_template_live", "close_document_live", "get_document_statistics_live",
        "save_as_document_live", "save_copy_live", "convert_document_live",
        "list_export_filters_live", "get_document_properties_live", "set_document_properties_live",
        "get_custom_properties_live", "set_custom_property_live", "remove_custom_property_live",
        "get_modified_state_live", "set_modified_state_live", "refresh_document_live",
        "reload_document_live", "print_document_live", "get_print_settings_live",
        "set_print_settings_live",
    },
    "undo_view_selection": {
        "get_undo_state_live", "undo_live", "redo_live", "begin_undo_context_live",
        "end_undo_context_live", "cancel_undo_context_live", "get_view_state_live",
        "set_zoom_live", "get_selection_live", "clear_selection_live",
        "get_document_events_live", "wait_for_document_event_live",
        "lock_document_updates_live", "unlock_document_updates_live",
        # New tool, 2026-08-22 (Brian's new-tools assignment, priority #7,
        # not part of the original spec this module was sourced from) --
        # write-side companion to get_view_state_live's current_page_number
        # addition (priority #6): navigate the Writer view cursor to a page.
        "goto_page_live",
    },
    "styles": {
        "list_style_families_live", "list_styles_live", "get_style_live", "create_style_live",
        "clone_style_live", "update_style_live", "rename_style_live", "delete_style_live",
        "apply_style_live", "get_direct_formatting_live", "clear_direct_formatting_live",
        "copy_formatting_live",
    },
    "writer_text": {
        "insert_paragraph_live", "append_paragraph_live", "insert_heading_live",
        "set_paragraph_text_live", "split_paragraph_live", "merge_paragraphs_live",
        "move_paragraphs_live", "copy_paragraphs_live", "set_paragraph_format_live",
        "set_character_format_live", "get_text_range_format_live", "find_regex_live",
        "replace_regex_live", "find_by_style_live", "replace_style_live",
        "update_comment_live", "delete_comment_live", "resolve_comment_live",
    },
    "writer_layout": {
        "get_page_layout_live", "set_page_layout_live", "apply_page_preset_live",
        "list_page_styles_live", "create_page_style_live", "update_page_style_live",
        "apply_page_style_live", "set_page_columns_live", "insert_page_break_live",
        "remove_page_break_live", "get_headers_footers_live", "set_header_live",
        "set_footer_live", "clear_header_live", "clear_footer_live",
        "insert_page_number_field_live", "insert_page_count_field_live",
        "insert_date_time_field_live", "insert_document_property_field_live",
        "list_fields_live", "update_fields_live", "delete_field_live",
        "list_bookmarks_live", "add_bookmark_live", "goto_bookmark_live",
        "rename_bookmark_live", "delete_bookmark_live", "insert_hyperlink_live",
        "list_hyperlinks_live", "update_hyperlink_live", "remove_hyperlink_live",
        "insert_cross_reference_live", "insert_caption_live", "list_document_indexes_live",
        "insert_toc_live", "update_index_live", "delete_index_live",
        "insert_alphabetical_index_live", "add_index_mark_live", "get_chapter_numbering_live",
        "set_chapter_numbering_live", "get_line_numbering_live", "set_line_numbering_live",
    },
    "writer_tables": {
        "list_tables_live", "insert_table_live", "get_table_live", "get_table_range_live",
        "set_table_range_live", "insert_table_rows_live", "delete_table_rows_live",
        "insert_table_columns_live", "delete_table_columns_live", "merge_table_cells_live",
        "split_table_cell_live", "set_table_format_live", "set_table_cell_format_live",
        "sort_table_live", "delete_table_live", "convert_text_to_table_live",
        "convert_table_to_text_live", "list_sections_live", "insert_section_live",
        "update_section_live", "delete_section_live", "add_footnote_live",
        "list_footnotes_live", "update_footnote_live", "delete_footnote_live",
        "add_endnote_live", "list_endnotes_live", "update_endnote_live",
        "delete_endnote_live", "get_note_settings_live", "set_note_settings_live",
        "list_content_controls_live", "insert_content_control_live", "get_content_control_live",
        "set_content_control_live", "delete_content_control_live", "preview_mail_merge_live",
        "mail_merge_live",
    },
    # Phase C - shared "Common drawing objects, images, shapes, and embedded
    # objects" section (Writer/Calc/Impress/Draw), not Writer-specific so it
    # was intentionally left out of Phase B.
    "drawing_objects": {
        "list_shapes_live", "get_shape_live", "insert_shape_live", "delete_shape_live",
        "duplicate_shape_live", "set_shape_geometry_live", "set_shape_style_live", "set_shape_text_live",
        "format_shape_text_live", "set_shape_alt_text_live", "set_shape_z_order_live", "align_shapes_live",
        "distribute_shapes_live", "group_shapes_live", "ungroup_shape_live", "combine_shapes_live",
        "split_shape_live", "bind_shapes_live", "unbind_shape_live", "insert_connector_live",
        "list_glue_points_live", "add_glue_point_live", "delete_glue_point_live", "insert_image_live",
        "replace_image_live", "set_image_properties_live", "export_shape_live", "list_embedded_objects_live",
        "insert_embedded_object_live", "activate_embedded_object_live", "delete_embedded_object_live",
        # New tool, 2026-08-22 (Brian's new-tools assignment, priority #4,
        # not part of the original 484-tool spec this section was sourced
        # from) -- shape-level search counterpart to find_cells_live.
        "find_shape_text_live",
    },
    # Phase C - "Charts and data visualizations" (Calc primarily; embedded
    # charts in Writer/Impress/Draw).
    "charts": {
        "list_charts_live", "create_chart_live", "get_chart_live", "delete_chart_live",
        "set_chart_type_live", "set_chart_data_live", "set_chart_title_live", "set_chart_legend_live",
        "get_chart_series_live", "set_chart_series_live", "add_chart_series_live", "remove_chart_series_live",
        "set_chart_axis_live", "set_chart_data_labels_live", "set_chart_gridlines_live",
        "add_chart_trendline_live", "remove_chart_trendline_live", "set_chart_error_bars_live",
        "set_chart_geometry_live", "export_chart_live",
    },
    # Phase C - Calc-complete, section 1: "Calc - sheets, cells, ranges,
    # formulas, layout".
    "calc_sheets": {
        "list_sheets_live", "get_active_sheet_live", "activate_sheet_live", "insert_sheet_live",
        "delete_sheet_live", "rename_sheet_live", "move_sheet_live", "copy_sheet_live", "hide_sheet_live",
        "show_sheet_live", "get_cell_live", "set_cell_live", "get_range_live", "set_range_live",
        "clear_range_live", "get_used_range_live", "insert_rows_live", "delete_rows_live",
        "insert_columns_live", "delete_columns_live", "insert_cells_live", "delete_cells_live",
        "copy_range_live", "move_range_live", "fill_series_live", "autofill_live", "set_range_format_live",
        "get_range_format_live", "merge_cells_live", "unmerge_cells_live", "set_row_height_live",
        "set_column_width_live", "hide_rows_live", "show_rows_live", "hide_columns_live", "show_columns_live",
        "freeze_panes_live", "unfreeze_panes_live", "recalculate_live", "evaluate_formula_live",
        "get_formula_dependencies_live", "get_formula_errors_live",
        # New tool, 2026-08-21 (Brian's new-tools assignment, priority #2,
        # not part of the original 484-tool spec this section was sourced
        # from) -- the missing Calc search primitive.
        "find_cells_live",
    },
    # Phase C - Calc-complete, section 2: "Calc - data management, analysis,
    # pivots, validation, external data".
    "calc_data": {
        "list_named_ranges_live", "create_named_range_live", "update_named_range_live",
        "delete_named_range_live", "sort_range_live", "apply_filter_live", "clear_filter_live",
        "get_filter_state_live", "list_conditional_formats_live", "add_conditional_format_live",
        "update_conditional_format_live", "delete_conditional_format_live", "get_data_validation_live",
        "set_data_validation_live", "clear_data_validation_live", "create_subtotals_live",
        "remove_subtotals_live", "list_pivot_tables_live", "create_pivot_table_live", "get_pivot_table_live",
        "update_pivot_table_live", "refresh_pivot_table_live", "delete_pivot_table_live",
        "list_scenarios_live", "create_scenario_live", "apply_scenario_live", "delete_scenario_live",
        "goal_seek_live", "solver_solve_live", "list_database_ranges_live", "create_database_range_live",
        "delete_database_range_live", "list_external_links_live", "create_external_link_live",
        "refresh_external_link_live", "delete_external_link_live", "import_csv_to_range_live",
        "export_range_to_csv_live", "group_rows_live", "ungroup_rows_live", "group_columns_live",
        "ungroup_columns_live",
    },
    # Phase C - Calc-complete, section 3: "Calc - page setup, print ranges,
    # annotations, protection".
    "calc_page": {
        "get_sheet_page_layout_live", "set_sheet_page_layout_live", "set_print_area_live",
        "clear_print_area_live", "set_repeating_print_rows_live", "set_repeating_print_columns_live",
        "add_cell_comment_live", "list_cell_comments_live", "delete_cell_comment_live", "protect_sheet_live",
        "unprotect_sheet_live", "set_cell_protection_live", "list_number_formats_live",
        "create_number_format_live", "apply_number_format_live",
    },
    # Phase D - "Impress - slides, masters, notes, transitions, animations, slideshow".
    "impress": {
        "list_slides_live", "get_active_slide_live", "activate_slide_live", "insert_slide_live",
        "duplicate_slide_live", "delete_slide_live", "move_slide_live", "rename_slide_live",
        "hide_slide_live", "show_slide_live", "get_slide_layout_live", "set_slide_layout_live",
        "set_slide_size_live", "set_slide_background_live", "list_master_pages_live",
        "apply_master_page_live", "create_master_page_live", "delete_master_page_live",
        "get_speaker_notes_live", "set_speaker_notes_live", "get_slide_transition_live",
        "set_slide_transition_live", "list_animations_live", "add_animation_live",
        "update_animation_live", "delete_animation_live", "reorder_animations_live",
        "set_shape_click_action_live", "get_presentation_settings_live", "set_presentation_settings_live",
        "list_custom_shows_live", "create_custom_show_live", "update_custom_show_live",
        "delete_custom_show_live", "start_slideshow_live", "stop_slideshow_live",
        "next_slideshow_effect_live", "previous_slideshow_effect_live", "goto_slideshow_slide_live",
        "export_slide_image_live", "export_all_slides_images_live",
        # New tool, 2026-08-22 (Brian's new-tools assignment, priority #3,
        # not part of the original 484-tool spec this section was sourced
        # from) -- "give me all the content of slide 7" instead of
        # list_shapes_live + N get_shape_live calls.
        "get_slide_content_live",
        # New tool, 2026-08-22 (Brian's new-tools assignment, priority #5) --
        # bulk counterpart to get_slide_content_live, wraps it in a loop
        # across the whole deck (or a chosen subset of slides).
        "get_presentation_content_live",
    },
    # Phase D - "Draw - pages, masters, layers, vector operations".
    "draw": {
        "list_draw_pages_live", "get_active_draw_page_live", "insert_draw_page_live",
        "duplicate_draw_page_live", "delete_draw_page_live", "move_draw_page_live",
        "rename_draw_page_live", "set_draw_page_size_live", "set_draw_page_background_live",
        "list_layers_live", "create_layer_live", "update_layer_live", "delete_layer_live",
        "assign_shape_layer_live", "export_draw_page_live", "export_selection_live",
        # New tool, 2026-08-22 (Brian's new-tools assignment, priority #9,
        # not part of the original spec this module was sourced from) --
        # the Draw counterpart to Impress's activate_slide_live.
        "activate_draw_page_live",
        # New tool, 2026-08-22 (Brian's new-tools assignment, priority #10,
        # not part of the original spec) -- the Draw counterpart to
        # Impress's get_slide_content_live.
        "get_draw_page_live",
    },
}

EXPECTED_TOOL_NAMES = set().union(*EXPECTED_BY_MODULE.values())


def _placeholder_for(prop_schema):
    """Return a type-appropriate throwaway value for a required JSON Schema property."""
    prop_type = prop_schema.get("type") if isinstance(prop_schema, dict) else None
    return {
        "string": "test",
        "integer": 1,
        "number": 1.0,
        "boolean": True,
        "array": [],
        "object": {},
    }.get(prop_type, "test")


def _call_with_placeholders(handler, parameters):
    """Call a stub handler with placeholder values for its required parameters."""
    properties = parameters.get("properties", {})
    required = parameters.get("required", [])
    kwargs = {name: _placeholder_for(properties.get(name, {})) for name in required}
    return handler(**kwargs)


def test_registry_matches_expected_names_exactly():
    """Registered tool names must equal the expected set -- not just match its size.

    Catches both a missing/typo'd registration and one landing under the
    wrong name, which a bare len() check would miss.
    """
    registry_names = set(get_registry().keys())
    missing = EXPECTED_TOOL_NAMES - registry_names
    unexpected = registry_names - EXPECTED_TOOL_NAMES
    assert not missing, f"expected tools missing from the registry: {sorted(missing)}"
    assert not unexpected, f"registry has tools not accounted for in EXPECTED_BY_MODULE: {sorted(unexpected)}"


def test_no_collisions_with_existing_compat_tools():
    collisions = set(get_registry().keys()) & EXISTING_COMPAT_TOOLS
    assert not collisions, f"scaffold stubs must not redefine existing compatibility tools: {collisions}"


def test_every_tool_has_a_valid_priority():
    valid_priorities = {"P0", "P1", "P2", "P3"}
    for name, metadata in get_registry().items():
        assert metadata["priority"] in valid_priorities, f"{name} has invalid priority {metadata['priority']!r}"


def test_every_tool_has_a_valid_status():
    for name, metadata in get_registry().items():
        assert metadata["status"] in ("stub", "implemented"), f"{name} has invalid status {metadata['status']!r}"


# Modules whose tools have real logic now, not NOT_IMPLEMENTED stub bodies.
# Update this set (and nothing else) as more modules get *fully* implemented.
IMPLEMENTED_MODULES = ("core_runtime", "document_lifecycle", "styles", "writer_text", "calc_sheets", "draw", "calc_page", "charts", "undo_view_selection", "drawing_objects")

# undo_view_selection.py is now fully implemented (all 14 tools) -- moved
# into IMPLEMENTED_MODULES above. get_document_events_live/wait_for_
# document_event_live were the last 2, landing in a deliberately separate
# pass from the other 12 (undo + view/selection/locking): event capture
# needed a persistent com.sun.star.document.XDocumentEventListener
# registered against the process-wide GlobalEventBroadcaster plus a
# bounded, seq-numbered event buffer with its own lifecycle -- see
# uno_bridge.py's "-- Document events --" section for the mechanism.

# drawing_objects.py is now fully implemented (all 31 tools) -- moved into
# IMPLEMENTED_MODULES above. combine_shapes_live/split_shape_live/
# bind_shapes_live/unbind_shape_live were re-enabled by the draw.py pass's
# dispatch-safety correction (the original .uno:Combine crash turned out
# to be an external-test-script artifact, not a real production risk --
# see docs/MCP_TOOLING_SCAFFOLD_PLAN.md's draw.py entry). insert_embedded_
# object_live is real, scoped to object_type="formula" (the one CLSID
# trusted without a live round trip -- see uno_bridge.py's
# _EMBEDDED_OBJECT_CLSIDS docstring). activate_embedded_object_live is
# the last one in: drives XEmbeddedObject.changeState() via the shape's
# ExtendedControlOverEmbeddedObject property (see uno_bridge.py's
# activate_embedded_object() docstring for the documented macro pattern
# this follows) -- written and unit-tested against the fake bridge, but
# NOT yet live-round-tripped against a real inserted formula object (the
# live instance was held for another agent's overnight session throughout
# this pass -- see the mcp-libre buzz channel, 2026-08-19/20). Next live
# pass: insert a formula object, activate it, confirm
# ExtendedControlOverEmbeddedObject/changeState() behave as documented.


def test_implemented_modules_tools_are_marked_implemented():
    """Every tool in an IMPLEMENTED_MODULES module carries real logic now --
    guard against one silently reverting to status="stub" (e.g. a bad
    merge/rebase)."""
    registry = get_registry()
    for module_name in IMPLEMENTED_MODULES:
        for name in EXPECTED_BY_MODULE[module_name]:
            assert registry[name]["status"] == "implemented", f"{name} (in {module_name}) should be status='implemented'"


# charts.py is now fully implemented (all 20 tools) -- moved into
# IMPLEMENTED_MODULES above. add_chart_series_live went real by writing raw
# in-memory values to a scratch sheet range first, then wiring that range
# into a new chart2 DataSeries via XDataProvider (see uno_bridge.py's
# add_chart_series docstring for the mechanism).


# impress.py is also a mixed module: 38 of its 41 tools are real. The
# remaining 3 stay status="stub" -- next/previous_slideshow_effect_live/
# goto_slideshow_slide_live (all three need a live XSlideShowController,
# confirmed always None headless -- see impress.py's module docstring).
# add/update/delete/reorder_animation_live are now real too: constructing/
# mutating a com.sun.star.animations.XAnimationNode tree via the generic
# animations module, scoped to a small honest effect set (see
# uno_bridge.py's _EFFECT_PRESETS docstring for why the rest of
# LibreOffice's preset library isn't reachable from the public UNO API).
IMPLEMENTED_IMPRESS_TOOL_NAMES = {
    "list_slides_live", "get_active_slide_live", "activate_slide_live", "insert_slide_live",
    "duplicate_slide_live", "delete_slide_live", "move_slide_live", "rename_slide_live",
    "hide_slide_live", "show_slide_live", "get_slide_layout_live", "set_slide_layout_live",
    "set_slide_size_live", "set_slide_background_live", "list_master_pages_live",
    "apply_master_page_live", "create_master_page_live", "delete_master_page_live",
    "get_speaker_notes_live", "set_speaker_notes_live", "get_slide_transition_live",
    "set_slide_transition_live", "list_animations_live",
    "add_animation_live", "update_animation_live", "delete_animation_live", "reorder_animations_live",
    "set_shape_click_action_live", "get_presentation_settings_live", "set_presentation_settings_live",
    "list_custom_shows_live", "create_custom_show_live", "update_custom_show_live",
    "delete_custom_show_live", "start_slideshow_live", "stop_slideshow_live",
    "export_slide_image_live", "export_all_slides_images_live",
    "get_slide_content_live", "get_presentation_content_live",
}


def test_implemented_impress_tools_are_marked_implemented():
    """Same guard as test_implemented_modules_tools_are_marked_implemented,
    for the 38 individually-implemented tools in the mixed impress.py
    module (see IMPLEMENTED_IMPRESS_TOOL_NAMES)."""
    registry = get_registry()
    for name in IMPLEMENTED_IMPRESS_TOOL_NAMES:
        assert registry[name]["status"] == "implemented", f"{name} should be status='implemented'"
    still_stub = EXPECTED_BY_MODULE["impress"] - IMPLEMENTED_IMPRESS_TOOL_NAMES
    for name in still_stub:
        assert registry[name]["status"] == "stub", f"{name} should still be status='stub' (no real code path this pass, see module docstring)"


# calc_data.py: all 42 tools are real as of a follow-up pass --
# create/refresh/delete_external_link_live (the last 3) are built on
# com.sun.star.sheet.XAreaLinks, a separate mechanism from
# list_external_links_live's original doc.ExternalDocLinks read-only
# side, see calc_data.py's module docstring. Kept as an explicit name
# set (not folded into test_implemented_modules_tools_are_marked_
# implemented) so a future regression in this module has the same
# per-name guard the mixed-module era relied on.
IMPLEMENTED_CALC_DATA_TOOL_NAMES = {
    "list_named_ranges_live", "create_named_range_live", "update_named_range_live",
    "delete_named_range_live", "sort_range_live", "apply_filter_live", "clear_filter_live",
    "get_filter_state_live", "list_conditional_formats_live", "add_conditional_format_live",
    "update_conditional_format_live", "delete_conditional_format_live", "get_data_validation_live",
    "set_data_validation_live", "clear_data_validation_live", "create_subtotals_live",
    "remove_subtotals_live", "list_pivot_tables_live", "create_pivot_table_live", "get_pivot_table_live",
    "update_pivot_table_live", "refresh_pivot_table_live", "delete_pivot_table_live",
    "list_scenarios_live", "create_scenario_live", "apply_scenario_live", "delete_scenario_live",
    "goal_seek_live", "solver_solve_live", "list_database_ranges_live", "create_database_range_live",
    "delete_database_range_live", "list_external_links_live", "create_external_link_live",
    "refresh_external_link_live", "delete_external_link_live", "import_csv_to_range_live",
    "export_range_to_csv_live", "group_rows_live", "ungroup_rows_live", "group_columns_live",
    "ungroup_columns_live",
}


def test_implemented_calc_data_tools_are_marked_implemented():
    """Same guard as test_implemented_modules_tools_are_marked_implemented,
    for all 42 individually-implemented tools in calc_data.py (see
    IMPLEMENTED_CALC_DATA_TOOL_NAMES) -- still_stub is empty now, kept
    for symmetry with the other mixed-module tests in this file."""
    registry = get_registry()
    for name in IMPLEMENTED_CALC_DATA_TOOL_NAMES:
        assert registry[name]["status"] == "implemented", f"{name} should be status='implemented'"
    still_stub = EXPECTED_BY_MODULE["calc_data"] - IMPLEMENTED_CALC_DATA_TOOL_NAMES
    for name in still_stub:
        assert registry[name]["status"] == "stub", f"{name} should still be status='stub' (no real code path this pass, see module docstring)"


# writer_layout.py is also a mixed module: 42 of its 43 tools are real.
# The remaining 1 (set_chapter_numbering_live) stays status="stub" --
# ChapterNumberingRules.replaceByIndex() genuinely doesn't accept a
# write this pass (see module docstring); get_chapter_numbering_live
# (read-only) IS real.
IMPLEMENTED_WRITER_LAYOUT_TOOL_NAMES = {
    "get_page_layout_live", "set_page_layout_live", "apply_page_preset_live", "list_page_styles_live",
    "create_page_style_live", "update_page_style_live", "apply_page_style_live", "set_page_columns_live",
    "insert_page_break_live", "remove_page_break_live", "get_headers_footers_live", "set_header_live",
    "set_footer_live", "clear_header_live", "clear_footer_live", "insert_page_number_field_live",
    "insert_page_count_field_live", "insert_date_time_field_live", "insert_document_property_field_live",
    "list_fields_live", "update_fields_live", "delete_field_live", "list_bookmarks_live", "add_bookmark_live",
    "goto_bookmark_live", "rename_bookmark_live", "delete_bookmark_live", "insert_hyperlink_live",
    "list_hyperlinks_live", "update_hyperlink_live", "remove_hyperlink_live", "insert_cross_reference_live",
    "insert_caption_live", "list_document_indexes_live", "insert_toc_live", "update_index_live",
    "delete_index_live", "insert_alphabetical_index_live", "add_index_mark_live", "get_chapter_numbering_live",
    "get_line_numbering_live", "set_line_numbering_live",
}


def test_implemented_writer_layout_tools_are_marked_implemented():
    """Same guard as test_implemented_modules_tools_are_marked_implemented,
    for the 42 individually-implemented tools in the mixed
    writer_layout.py module (see IMPLEMENTED_WRITER_LAYOUT_TOOL_NAMES)."""
    registry = get_registry()
    for name in IMPLEMENTED_WRITER_LAYOUT_TOOL_NAMES:
        assert registry[name]["status"] == "implemented", f"{name} should be status='implemented'"
    still_stub = EXPECTED_BY_MODULE["writer_layout"] - IMPLEMENTED_WRITER_LAYOUT_TOOL_NAMES
    for name in still_stub:
        assert registry[name]["status"] == "stub", f"{name} should still be status='stub' (no real code path this pass, see module docstring)"


# writer_tables.py is also a mixed module: 37 of its 38 tools are real.
# The remaining 1 (mail_merge_live) stays status="stub" -- the real
# com.sun.star.text.MailMerge service's own Model property is read-only
# and its DocumentURL-based execute() path needs a DataSourceName
# resolvable through com.sun.star.sdb.DatabaseContext, which refuses to
# register an ad hoc DataSource without a persisted .odb file (see module
# docstring); preview_mail_merge_live (the real data-connection half) IS
# real.
IMPLEMENTED_WRITER_TABLES_TOOL_NAMES = {
    "list_tables_live", "insert_table_live", "get_table_live", "get_table_range_live",
    "set_table_range_live", "insert_table_rows_live", "delete_table_rows_live",
    "insert_table_columns_live", "delete_table_columns_live", "merge_table_cells_live",
    "split_table_cell_live", "set_table_format_live", "set_table_cell_format_live",
    "sort_table_live", "delete_table_live", "convert_text_to_table_live",
    "convert_table_to_text_live", "list_sections_live", "insert_section_live",
    "update_section_live", "delete_section_live", "add_footnote_live",
    "list_footnotes_live", "update_footnote_live", "delete_footnote_live",
    "add_endnote_live", "list_endnotes_live", "update_endnote_live",
    "delete_endnote_live", "get_note_settings_live", "set_note_settings_live",
    "list_content_controls_live", "insert_content_control_live", "get_content_control_live",
    "set_content_control_live", "delete_content_control_live", "preview_mail_merge_live",
}


def test_implemented_writer_tables_tools_are_marked_implemented():
    """Same guard as test_implemented_modules_tools_are_marked_implemented,
    for the 37 individually-implemented tools in the mixed
    writer_tables.py module (see IMPLEMENTED_WRITER_TABLES_TOOL_NAMES)."""
    registry = get_registry()
    for name in IMPLEMENTED_WRITER_TABLES_TOOL_NAMES:
        assert registry[name]["status"] == "implemented", f"{name} should be status='implemented'"
    still_stub = EXPECTED_BY_MODULE["writer_tables"] - IMPLEMENTED_WRITER_TABLES_TOOL_NAMES
    for name in still_stub:
        assert registry[name]["status"] == "stub", f"{name} should still be status='stub' (no real code path this pass, see module docstring)"


def test_stub_shape_contract():
    """Every remaining stub, called with placeholder args, returns the
    spec's NOT_IMPLEMENTED error envelope. Tools with status="implemented"
    (currently core_runtime.py's 12) are excluded -- they have real logic
    and real behavioral tests instead (see tests/test_core_runtime.py);
    calling them here with placeholder args and no installed
    tools.context would raise, not return NOT_IMPLEMENTED.
    """
    for name, metadata in get_registry(status="stub").items():
        result = _call_with_placeholders(metadata["handler"], metadata["parameters"])
        assert result["success"] is False, f"{name} stub should not report success"
        assert result["error"]["code"] == "NOT_IMPLEMENTED", f"{name} stub returned unexpected error code"
        assert "document_id" in result, f"{name} response is missing document_id"
        assert "elapsed_ms" in result and isinstance(result["elapsed_ms"], int), f"{name} response is missing elapsed_ms"


def test_merge_into_does_not_overwrite_existing_tools_by_default():
    sentinel = object()
    existing_tools = {"ping_live": {"description": "original", "parameters": schema(), "handler": sentinel}}
    added = merge_into(existing_tools)
    assert "ping_live" not in added
    assert existing_tools["ping_live"]["handler"] is sentinel

    # overwrite=True should replace it
    added = merge_into(existing_tools, overwrite=True)
    assert "ping_live" in added
    assert existing_tools["ping_live"]["handler"] is not sentinel


def test_error_envelope_rejects_unknown_codes():
    from tools import envelope

    try:
        envelope.build_error("NOT_A_REAL_CODE", "boom")
        assert False, "expected ValueError for an unknown error code"
    except ValueError:
        pass


def test_error_codes_match_spec_list():
    spec_codes = {
        "NO_ACTIVE_DOCUMENT", "WRONG_DOCUMENT_TYPE", "OBJECT_NOT_FOUND", "AMBIGUOUS_SELECTOR",
        "UNSUPPORTED_CAPABILITY", "INVALID_RANGE", "INVALID_PARAMETER", "FILE_EXISTS",
        "PERMISSION_DENIED", "UNO_EXCEPTION", "DATABASE_ERROR", "TIMEOUT", "SECURITY_POLICY_DENIED",
    }
    # NOT_IMPLEMENTED and INVALID_STATE are scaffold-only additions, not part
    # of the spec's own list -- see envelope.py's ERROR_CODES comment.
    assert spec_codes <= ERROR_CODES
    assert ERROR_CODES - spec_codes == {"NOT_IMPLEMENTED", "INVALID_STATE"}


if __name__ == "__main__":
    tests = [
        test_registry_matches_expected_names_exactly,
        test_no_collisions_with_existing_compat_tools,
        test_every_tool_has_a_valid_priority,
        test_every_tool_has_a_valid_status,
        test_implemented_modules_tools_are_marked_implemented,
        test_implemented_undo_tools_are_marked_implemented,
        test_implemented_impress_tools_are_marked_implemented,
        test_implemented_calc_data_tools_are_marked_implemented,
        test_implemented_writer_layout_tools_are_marked_implemented,
        test_implemented_writer_tables_tools_are_marked_implemented,
        test_stub_shape_contract,
        test_merge_into_does_not_overwrite_existing_tools_by_default,
        test_error_envelope_rejects_unknown_codes,
        test_error_codes_match_spec_list,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"\nAll {len(tests)} tool scaffold contract tests passed ({len(EXPECTED_TOOL_NAMES)} tools registered).")
