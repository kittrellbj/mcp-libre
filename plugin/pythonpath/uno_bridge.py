"""
LibreOffice MCP Extension - UNO Bridge Module

This module provides a bridge between MCP operations and LibreOffice UNO API,
enabling direct manipulation of LibreOffice documents.
"""

import builtins
import uno
import unohelper
from com.sun.star.beans import PropertyValue
from com.sun.star.text.ControlCharacter import PARAGRAPH_BREAK
from typing import Any, Optional, Dict, List
import logging
import os
import traceback

from uno_datetime import uno_datetime_to_iso

# Optional imports - these may not be available in all configurations
try:
    from com.sun.star.text import XTextDocument
except ImportError:
    XTextDocument = None

try:
    from com.sun.star.sheet import XSpreadsheetDocument
except ImportError:
    XSpreadsheetDocument = None

try:
    from com.sun.star.presentation import XPresentationDocument
except ImportError:
    XPresentationDocument = None

try:
    from com.sun.star.document import XDocumentEventListener
except ImportError:
    XDocumentEventListener = None

try:
    from com.sun.star.awt import XActionListener
except ImportError:
    XActionListener = None

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _is_instance(obj, cls):
    """Safe isinstance check that handles None class types"""
    if cls is None:
        return False
    return isinstance(obj, cls)


class UNOBridge:
    """Bridge between MCP operations and LibreOffice UNO API"""
    
    def __init__(self):
        """Initialize the UNO bridge"""
        try:
            self.ctx = uno.getComponentContext()
            self.smgr = self.ctx.ServiceManager
            self.desktop = self.smgr.createInstanceWithContext(
                "com.sun.star.frame.Desktop", self.ctx)
            logger.info("UNO Bridge initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize UNO Bridge: {e}")
            raise
    
    def get_application_version(self) -> Dict[str, Any]:
        """
        Return the running LibreOffice application's version info via UNO
        configuration, not the extension's own version.

        Reads /org.openoffice.Setup/Product from the UNO configuration
        provider -- the standard way an extension queries "what LibreOffice
        am I running inside", independent of any document being open.

        Returns:
            {"success": True, "name": ..., "version": ..., "version_about_box": ...}
            or {"success": False, "error": ...} if the configuration query fails.
        """
        try:
            provider = self.smgr.createInstanceWithContext(
                "com.sun.star.configuration.ConfigurationProvider", self.ctx)

            node_path = PropertyValue()
            node_path.Name = "nodepath"
            node_path.Value = "/org.openoffice.Setup/Product"

            access = provider.createInstanceWithArguments(
                "com.sun.star.configuration.ConfigurationAccess", (node_path,))

            return {
                "success": True,
                "name": access.getByName("ooName"),
                "version": access.getByName("ooSetupVersion"),
                "version_about_box": access.getByName("ooSetupVersionAboutBox"),
            }
        except Exception as e:
            logger.error(f"Failed to read application version: {e}")
            return {"success": False, "error": str(e)}

    def get_capabilities(self) -> Dict[str, Any]:
        """
        Return which optional UNO interfaces this bridge resolved at import
        time, and which document types create_document()/the doc-type
        detection in _get_document_type() actually support.

        This reflects real state (the module-level guarded imports at the
        top of this file succeeding or falling back to None), not a
        hardcoded claim -- on a LibreOffice build/platform where one of
        these interfaces is unavailable, the corresponding flag is False.
        """
        return {
            "supported_document_types": ["writer", "calc", "impress", "draw"],
            "optional_uno_interfaces": {
                "XTextDocument": XTextDocument is not None,
                "XSpreadsheetDocument": XSpreadsheetDocument is not None,
                "XPresentationDocument": XPresentationDocument is not None,
                "XDocumentEventListener": XDocumentEventListener is not None,
                "XActionListener": XActionListener is not None,
            },
        }

    def create_document(self, doc_type: str = "writer") -> Any:
        """
        Create new document using UNO API
        
        Args:
            doc_type: Type of document ('writer', 'calc', 'impress', 'draw')
            
        Returns:
            Document object
        """
        try:
            url_map = {
                "writer": "private:factory/swriter",
                "calc": "private:factory/scalc", 
                "impress": "private:factory/simpress",
                "draw": "private:factory/sdraw"
            }
            
            url = url_map.get(doc_type, "private:factory/swriter")
            doc = self.desktop.loadComponentFromURL(url, "_blank", 0, ())
            logger.info(f"Created new {doc_type} document")
            return doc
            
        except Exception as e:
            logger.error(f"Failed to create document: {e}")
            raise
    
    def get_active_document(self) -> Optional[Any]:
        """Get currently active document"""
        try:
            doc = self.desktop.getCurrentComponent()
            if doc:
                logger.info("Retrieved active document")
            return doc
        except Exception as e:
            logger.error(f"Failed to get active document: {e}")
            return None
    
    def get_document_info(self, doc: Any = None) -> Dict[str, Any]:
        """Get information about a document"""
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc:
                return {"error": "No document available"}

            doc_type = self._get_document_type(doc)

            info = {
                "title": getattr(doc, 'Title', 'Unknown') if hasattr(doc, 'Title') else "Unknown",
                "url": doc.getURL() if hasattr(doc, 'getURL') else "",
                "modified": doc.isModified() if hasattr(doc, 'isModified') else False,
                "type": doc_type,
                "has_selection": self._has_selection(doc)
            }

            # Add document-specific information
            if _is_instance(doc, XTextDocument):
                text = doc.getText()
                info["word_count"] = len(text.getString().split())
                info["character_count"] = len(text.getString())

                # Add track_changes status for Writer documents
                tc_status = self.get_track_changes_status(doc)
                if tc_status.get("success"):
                    info["track_changes"] = {
                        "recording": tc_status.get("recording", False),
                        "showing": tc_status.get("showing", False),
                        "pending_count": tc_status.get("pending_count", 0)
                    }
            elif _is_instance(doc, XSpreadsheetDocument):
                sheets = doc.getSheets()
                info["sheet_count"] = sheets.getCount()
                info["sheet_names"] = [sheets.getByIndex(i).getName()
                                     for i in range(sheets.getCount())]

            return info

        except Exception as e:
            logger.error(f"Failed to get document info: {e}")
            return {"error": str(e)}
    
    def insert_text(self, text: str, position: Optional[int] = None, doc: Any = None) -> Dict[str, Any]:
        """
        Insert text into a document
        
        Args:
            text: Text to insert
            position: Position to insert at (None for current cursor position)
            doc: Document to insert into (None for active document)
            
        Returns:
            Result dictionary
        """
        try:
            if doc is None:
                doc = self.get_active_document()
            
            if not doc:
                return {"success": False, "error": "No active document"}

            # Check if it's a Writer document
            is_writer = _is_instance(doc, XTextDocument) or \
                        (hasattr(doc, 'supportsService') and doc.supportsService("com.sun.star.text.TextDocument")) or \
                        hasattr(doc, 'getText')

            # Handle Writer documents
            if is_writer:
                text_obj = doc.getText()

                if position is None:
                    # Insert at current cursor position
                    cursor = doc.getCurrentController().getViewCursor()
                else:
                    # Insert at specific position
                    cursor = text_obj.createTextCursor()
                    cursor.gotoStart(False)
                    cursor.goRight(position, False)

                text_obj.insertString(cursor, text, False)
                logger.info(f"Inserted {len(text)} characters into Writer document")
                return {"success": True, "message": f"Inserted {len(text)} characters"}

            # Handle other document types
            else:
                return {"success": False, "error": f"Text insertion not supported for {self._get_document_type(doc)}"}
                
        except Exception as e:
            logger.error(f"Failed to insert text: {e}")
            return {"success": False, "error": str(e)}
    
    def format_text(self, formatting: Dict[str, Any], doc: Any = None) -> Dict[str, Any]:
        """
        Apply formatting to selected text
        
        Args:
            formatting: Dictionary of formatting options
            doc: Document to format (None for active document)
            
        Returns:
            Result dictionary
        """
        try:
            if doc is None:
                doc = self.get_active_document()
            
            if not doc or not _is_instance(doc, XTextDocument):
                return {"success": False, "error": "No Writer document available"}
            
            # Get current selection
            selection = doc.getCurrentController().getSelection()
            if selection.getCount() == 0:
                return {"success": False, "error": "No text selected"}
            
            # Apply formatting to selection
            text_range = selection.getByIndex(0)
            
            # Apply various formatting options
            if "bold" in formatting:
                text_range.CharWeight = 150.0 if formatting["bold"] else 100.0
            
            if "italic" in formatting:
                text_range.CharPosture = 2 if formatting["italic"] else 0
            
            if "underline" in formatting:
                text_range.CharUnderline = 1 if formatting["underline"] else 0
            
            if "font_size" in formatting:
                text_range.CharHeight = formatting["font_size"]
            
            if "font_name" in formatting:
                text_range.CharFontName = formatting["font_name"]
            
            logger.info("Applied formatting to selected text")
            return {"success": True, "message": "Formatting applied successfully"}
            
        except Exception as e:
            logger.error(f"Failed to format text: {e}")
            return {"success": False, "error": str(e)}
    
    def save_document(self, doc: Any = None, file_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Save a document
        
        Args:
            doc: Document to save (None for active document)
            file_path: Path to save to (None to save to current location)
            
        Returns:
            Result dictionary
        """
        try:
            if doc is None:
                doc = self.get_active_document()
            
            if not doc:
                return {"success": False, "error": "No document to save"}
            
            if file_path:
                # Save as new file
                url = uno.systemPathToFileUrl(file_path)
                doc.storeAsURL(url, ())
                logger.info(f"Saved document to {file_path}")
                return {"success": True, "message": f"Document saved to {file_path}"}
            else:
                # Save to current location
                if doc.hasLocation():
                    doc.store()
                    logger.info("Saved document to current location")
                    return {"success": True, "message": "Document saved"}
                else:
                    return {"success": False, "error": "Document has no location, specify file_path"}
                    
        except Exception as e:
            logger.error(f"Failed to save document: {e}")
            return {"success": False, "error": str(e)}
    
    def export_document(self, export_format: str, file_path: str, doc: Any = None) -> Dict[str, Any]:
        """
        Export document to different format
        
        Args:
            export_format: Target format ('pdf', 'docx', 'odt', 'txt', etc.)
            file_path: Path to export to
            doc: Document to export (None for active document)
            
        Returns:
            Result dictionary
        """
        try:
            if doc is None:
                doc = self.get_active_document()
            
            if not doc:
                return {"success": False, "error": "No document to export"}
            
            # Filter map for different formats
            filter_map = {
                'pdf': 'writer_pdf_Export',
                'docx': 'MS Word 2007 XML',
                'doc': 'MS Word 97',
                'odt': 'writer8',
                'txt': 'Text',
                'rtf': 'Rich Text Format',
                'html': 'HTML (StarWriter)'
            }
            
            filter_name = filter_map.get(export_format.lower())
            if not filter_name:
                return {"success": False, "error": f"Unsupported export format: {export_format}"}
            
            # Prepare export properties
            properties = (
                PropertyValue("FilterName", 0, filter_name, 0),
                PropertyValue("Overwrite", 0, True, 0),
            )
            
            # Export document
            url = uno.systemPathToFileUrl(file_path)
            doc.storeToURL(url, properties)
            
            logger.info(f"Exported document to {file_path} as {export_format}")
            return {"success": True, "message": f"Document exported to {file_path}"}

        except Exception as e:
            logger.error(f"Failed to export document: {e}")
            return {"success": False, "error": str(e)}

    # -- Document lifecycle (open/close/save-as/properties/etc.) --------
    #
    # These methods raise on failure rather than returning a
    # {"success": False, ...} dict, matching create_document()'s contract
    # (not save_document()/export_document()'s). The tools/document_lifecycle.py
    # callers need to distinguish specific failure reasons (file already
    # exists vs. permission denied vs. a UNO exception) to map onto the
    # spec's distinct error codes, which a single generic error string
    # can't support cleanly.

    def open_document(self, file_path: str, read_only: bool = False, hidden: bool = False,
                       password: Optional[str] = None, filter_name: Optional[str] = None) -> Any:
        """Open an existing file as a new document. Returns the loaded document component."""
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"No such file: {file_path}")
        url = uno.systemPathToFileUrl(file_path)
        props = [
            PropertyValue("ReadOnly", 0, read_only, 0),
            PropertyValue("Hidden", 0, hidden, 0),
        ]
        if password:
            props.append(PropertyValue("Password", 0, password, 0))
        if filter_name:
            props.append(PropertyValue("FilterName", 0, filter_name, 0))
        doc = self.desktop.loadComponentFromURL(url, "_blank", 0, tuple(props))
        if doc is None:
            raise RuntimeError(f"LibreOffice returned no document for {file_path} (unsupported format or filter?)")
        logger.info(f"Opened document from {file_path}")
        return doc

    def open_from_template(self, template_path: str, as_template: bool = True) -> Any:
        """Create a new document from an ODF/compatible template. Returns the new document component."""
        if not os.path.isfile(template_path):
            raise FileNotFoundError(f"No such template: {template_path}")
        url = uno.systemPathToFileUrl(template_path)
        props = (PropertyValue("AsTemplate", 0, as_template, 0),)
        doc = self.desktop.loadComponentFromURL(url, "_blank", 0, props)
        if doc is None:
            raise RuntimeError(f"LibreOffice returned no document for template {template_path}")
        logger.info(f"Created document from template {template_path} (as_template={as_template})")
        return doc

    def close_document(self, doc: Any, save: Any = False) -> None:
        """Close a document with explicit save/discard behavior.

        Args:
            save: True (store before closing), False (discard changes), or
                "prompt" -- not supported headlessly (there is no UI to
                answer a prompt), raises ValueError so the caller can
                surface a clear error instead of hanging.
        """
        if save == "prompt":
            raise ValueError("save='prompt' is not supported by a headless extension; pass true or false explicitly.")
        if save is True:
            if not doc.hasLocation():
                raise ValueError("Document has no location to save to; use save_as_document_live first.")
            doc.store()
        doc.close(False)
        logger.info("Closed document")

    def activate_document(self, doc: Any) -> None:
        """Bring a document's frame to the foreground."""
        controller = doc.getCurrentController()
        if controller is None:
            raise RuntimeError("Document has no controller to activate.")
        frame = controller.getFrame()
        if frame is None:
            raise RuntimeError("Document's controller has no frame to activate.")
        frame.activate()
        try:
            frame.getContainerWindow().toFront()
        except Exception:
            pass  # best-effort in headless environments with no real window

    def get_document_statistics(self, doc: Any) -> Dict[str, Any]:
        """Return counts appropriate to the document's type (pages/words/
        chars for Writer; sheets for Calc; slides/pages for Impress/Draw)."""
        doc_type = self._get_document_type(doc)
        stats: Dict[str, Any] = {"type": doc_type}

        if doc_type == "writer":
            text = doc.getText()
            content = text.getString()
            stats["word_count"] = len(content.split())
            stats["character_count"] = len(content)
            paragraph_count = 0
            enum = text.createEnumeration()
            while enum.hasMoreElements():
                enum.nextElement()
                paragraph_count += 1
            stats["paragraph_count"] = paragraph_count
            try:
                stats["page_count"] = doc.getCurrentController().PageCount
            except Exception:
                stats["page_count"] = None
        elif doc_type == "calc":
            sheets = doc.getSheets()
            stats["sheet_count"] = sheets.getCount()
            stats["sheet_names"] = [sheets.getByIndex(i).getName() for i in range(sheets.getCount())]
        elif doc_type in ("impress", "draw"):
            try:
                stats["page_count"] = doc.getDrawPages().getCount()
            except Exception:
                stats["page_count"] = None
        else:
            stats["warning"] = f"No statistics available for document type '{doc_type}'"

        return stats

    _DOCUMENT_PROPERTY_FIELDS = ("Title", "Subject", "Author", "Description", "ModifiedBy")

    def get_document_properties(self, doc: Any) -> Dict[str, Any]:
        """Return standard document metadata via XDocumentPropertiesSupplier."""
        props = doc.getDocumentProperties()
        result: Dict[str, Any] = {}
        for field in self._DOCUMENT_PROPERTY_FIELDS:
            result[field.lower() if field != "ModifiedBy" else "modified_by"] = getattr(props, field, None)
        result["keywords"] = list(getattr(props, "Keywords", ()) or ())
        result["creation_date"] = uno_datetime_to_iso(getattr(props, "CreationDate", None))
        result["modification_date"] = uno_datetime_to_iso(getattr(props, "ModificationDate", None))
        return result

    # Only these are exposed for writing -- CreationDate/ModificationDate/
    # ModifiedBy are UNO-managed and not meant to be set directly by a caller.
    _SETTABLE_DOCUMENT_PROPERTY_FIELDS = {"title": "Title", "subject": "Subject", "author": "Author",
                                           "description": "Description", "keywords": "Keywords"}

    def set_document_properties(self, doc: Any, properties: Dict[str, Any]) -> List[str]:
        """Set standard document metadata. Returns the list of field names actually applied."""
        doc_props = doc.getDocumentProperties()
        applied = []
        for key, value in properties.items():
            uno_field = self._SETTABLE_DOCUMENT_PROPERTY_FIELDS.get(key)
            if uno_field is None:
                continue  # unknown/unsettable field name -- caller is told via the returned list
            if uno_field == "Keywords":
                value = tuple(value) if value else ()
            setattr(doc_props, uno_field, value)
            applied.append(key)
        return applied

    def get_custom_properties(self, doc: Any) -> Dict[str, Any]:
        """Return user-defined document properties as a flat {name: value} dict."""
        container = doc.getDocumentProperties().getUserDefinedProperties()
        names = [p.Name for p in container.getPropertySetInfo().getProperties()]
        return {name: container.getPropertyValue(name) for name in names}

    def set_custom_property(self, doc: Any, name: str, value: Any, property_type: Optional[str] = None) -> None:
        """Create or update a user-defined document property."""
        from com.sun.star.beans import PropertyAttribute

        container = doc.getDocumentProperties().getUserDefinedProperties()
        existing_names = {p.Name for p in container.getPropertySetInfo().getProperties()}
        if name in existing_names:
            container.setPropertyValue(name, value)
        else:
            container.addProperty(name, PropertyAttribute.REMOVABLE, value)

    def remove_custom_property(self, doc: Any, name: str) -> None:
        """Delete a user-defined document property. Raises if it doesn't exist."""
        container = doc.getDocumentProperties().getUserDefinedProperties()
        existing_names = {p.Name for p in container.getPropertySetInfo().getProperties()}
        if name not in existing_names:
            raise KeyError(f"No custom property named '{name}'")
        container.removeProperty(name)

    def get_modified_state(self, doc: Any) -> bool:
        return doc.isModified()

    def set_modified_state(self, doc: Any, modified: bool) -> None:
        doc.setModified(modified)

    # -- Undo manager (com.sun.star.document.XUndoManagerSupplier/XUndoManager) --

    def _get_undo_manager(self, doc: Any) -> Any:
        """Return doc's XUndoManager via XUndoManagerSupplier.getUndoManager().

        Duck-typed like the rest of this file (hasattr, not an explicit UNO
        interface cast) -- every document type this bridge supports
        implements com.sun.star.document.OfficeDocument, which carries
        XUndoManagerSupplier, but guard anyway in case a future document
        type/build doesn't.

        Raises:
            NotImplementedError: doc has no getUndoManager() (or it returned
                nothing) -- callers should map this to UNSUPPORTED_CAPABILITY.
        """
        get_manager = getattr(doc, "getUndoManager", None)
        if get_manager is None:
            raise NotImplementedError("This document does not support XUndoManagerSupplier.getUndoManager().")
        manager = get_manager()
        if manager is None:
            raise NotImplementedError("Document's getUndoManager() returned nothing.")
        return manager

    def get_undo_state(self, doc: Any) -> Dict[str, Any]:
        """Return undo/redo availability and the title of the next action
        each direction would apply, per XUndoManager.isUndoPossible()/
        isRedoPossible()/getCurrentUndoActionTitle()/getCurrentRedoActionTitle().
        """
        manager = self._get_undo_manager(doc)
        can_undo = manager.isUndoPossible()
        can_redo = manager.isRedoPossible()
        return {
            "can_undo": can_undo,
            "can_redo": can_redo,
            "undo_title": manager.getCurrentUndoActionTitle() if can_undo else None,
            "redo_title": manager.getCurrentRedoActionTitle() if can_redo else None,
        }

    def undo(self, doc: Any, count: int = 1) -> Dict[str, Any]:
        """Undo up to `count` actions, stopping cleanly (no exception) when
        the undo stack is exhausted rather than assuming `count` are always
        available.
        """
        manager = self._get_undo_manager(doc)
        applied = 0
        for _ in range(count):
            if not manager.isUndoPossible():
                break
            manager.undo()
            applied += 1
        return {
            "requested": count, "applied": applied,
            "can_undo": manager.isUndoPossible(), "can_redo": manager.isRedoPossible(),
        }

    def redo(self, doc: Any, count: int = 1) -> Dict[str, Any]:
        """Redo up to `count` actions, stopping cleanly when the redo stack
        is exhausted (e.g. because a new action was recorded since the last
        undo, which clears the redo stack per UNO semantics)."""
        manager = self._get_undo_manager(doc)
        applied = 0
        for _ in range(count):
            if not manager.isRedoPossible():
                break
            manager.redo()
            applied += 1
        return {
            "requested": count, "applied": applied,
            "can_undo": manager.isUndoPossible(), "can_redo": manager.isRedoPossible(),
        }

    def begin_undo_context(self, doc: Any, title: str) -> Dict[str, Any]:
        """Open a named undo context (XUndoManager.enterUndoContext) that
        coalesces every undo action recorded until end/cancel into one
        visible Undo step.

        Returns {"baseline_count": N} -- the undo stack depth (per
        getAllUndoActionTitles()) immediately before the context opened.
        Callers must hold onto this and pass it back into
        cancel_undo_context(); it's how cancel tells "the context added one
        coalesced action to revert" apart from "the context was empty and
        UNO silently discarded it" without needing an XUndoManagerListener.
        """
        manager = self._get_undo_manager(doc)
        baseline_count = len(manager.getAllUndoActionTitles())
        manager.enterUndoContext(title)
        return {"baseline_count": baseline_count}

    def end_undo_context(self, doc: Any) -> Dict[str, Any]:
        """Close the current undo context (XUndoManager.leaveUndoContext),
        coalescing everything recorded inside it into one Undo step (or, if
        nothing was recorded, UNO discards the context with no visible
        step -- see begin_undo_context's docstring).
        """
        manager = self._get_undo_manager(doc)
        manager.leaveUndoContext()
        return {"resulting_count": len(manager.getAllUndoActionTitles())}

    def cancel_undo_context(self, doc: Any, baseline_count: int) -> Dict[str, Any]:
        """Close the current undo context and revert whatever it recorded.

        XUndoManager has no direct "cancel" primitive, so this leaves the
        context the same way end_undo_context does (which is what commits
        the pending actions into one coalesced step -- undo() raises
        UndoContextNotClosedException while a context is still open), then
        calls undo() while the stack is deeper than baseline_count to
        revert exactly the step(s) that context produced. Normally that's
        at most one undo() call (a closed context coalesces to a single
        action), but the loop (capped) is defensive rather than assuming
        that invariant always holds.
        """
        manager = self._get_undo_manager(doc)
        manager.leaveUndoContext()
        reverted = 0
        max_iterations = 1000
        while len(manager.getAllUndoActionTitles()) > baseline_count and reverted < max_iterations:
            if not manager.isUndoPossible():
                break
            manager.undo()
            reverted += 1
        resulting_count = len(manager.getAllUndoActionTitles())
        return {"reverted_count": reverted, "restored": resulting_count <= baseline_count, "resulting_count": resulting_count}

    # -- View state, zoom, selection, document-update locking --------------

    # com.sun.star.view.DocumentZoomType constants. Not modeled as a
    # uno.Enum on the controller -- ZoomType is a plain short property
    # using this constants group -- so these are the caller-facing names
    # for set_zoom's `mode` parameter; BY_VALUE is used internally when
    # `percent` is set (see set_zoom) rather than exposed as a `mode` value.
    _ZOOM_MODE_TO_TYPE = {"optimal": 0, "page": 2, "width": 1}
    _ZOOM_TYPE_TO_MODE = {0: "optimal", 1: "width", 2: "page", 3: "value", 4: "width_exact"}

    def _get_controller(self, doc: Any) -> Any:
        controller = doc.getCurrentController()
        if controller is None:
            raise RuntimeError("Document has no current controller.")
        return controller

    def _get_zoom_property_set(self, controller: Any) -> Any:
        """Return the XPropertySet that carries ZoomValue/ZoomType.

        Live-verified against a real Writer document that these are NOT
        direct properties of the controller itself -- reading
        controller.ZoomValue silently returns None and writing
        controller.ZoomType raises a UNO exception. The real location is
        controller.ViewSettings (an XPropertySet; service
        com.sun.star.text.ViewSettings for Writer, and per the UNO API the
        same XViewSettingsSupplier.ViewSettings pattern is documented for
        Calc/Impress/Draw controllers too, though only Writer was
        available to live-verify this pass -- falls back to the
        controller itself if ViewSettings isn't present, in case some
        controller type doesn't follow this pattern.
        """
        view_settings = getattr(controller, "ViewSettings", None)
        if view_settings is not None and hasattr(view_settings, "getPropertyValue"):
            return view_settings
        return controller

    def get_view_state(self, doc: Any) -> Dict[str, Any]:
        """Return controller/view mode, zoom, and a document-type-specific
        visible sheet/page/slide indicator, plus a selection summary."""
        controller = self._get_controller(doc)
        doc_type = self._get_document_type(doc)
        zoom_props = self._get_zoom_property_set(controller)
        zoom_type = zoom_props.getPropertyValue("ZoomType") if hasattr(zoom_props, "getPropertyValue") else None
        state: Dict[str, Any] = {
            "type": doc_type,
            "zoom_value": zoom_props.getPropertyValue("ZoomValue") if hasattr(zoom_props, "getPropertyValue") else None,
            "zoom_mode": self._ZOOM_TYPE_TO_MODE.get(zoom_type, zoom_type),
            "has_selection": self._has_selection(doc),
        }
        if doc_type == "calc":
            try:
                active_sheet = controller.getActiveSheet()
                state["active_sheet"] = active_sheet.getName() if active_sheet else None
            except Exception:
                state["active_sheet"] = None
        elif doc_type in ("impress", "draw"):
            try:
                current_page = controller.getCurrentPage()
                state["current_page_name"] = current_page.Name if current_page else None
            except Exception:
                state["current_page_name"] = None
        return state

    def set_zoom(self, doc: Any, percent: Optional[int] = None, mode: Optional[str] = None) -> Dict[str, Any]:
        """Set zoom percent (exact value) or a named fit mode. Exactly one
        of percent/mode should be meaningful; if both are given, percent
        wins (mode is applied first, then overridden by the exact value)."""
        if percent is None and mode is None:
            raise ValueError("Provide either percent or mode.")
        controller = self._get_controller(doc)
        zoom_props = self._get_zoom_property_set(controller)
        if not hasattr(zoom_props, "setPropertyValue"):
            raise NotImplementedError("This document's controller does not expose a settable zoom property set.")
        if mode is not None:
            zoom_type = self._ZOOM_MODE_TO_TYPE.get(mode)
            if zoom_type is None:
                raise ValueError(f"Unknown zoom mode '{mode}', expected one of {sorted(self._ZOOM_MODE_TO_TYPE)}")
            zoom_props.setPropertyValue("ZoomType", zoom_type)
        if percent is not None:
            zoom_props.setPropertyValue("ZoomType", 3)  # BY_VALUE -- otherwise a fit-mode set above would override ZoomValue
            zoom_props.setPropertyValue("ZoomValue", percent)
        return {"zoom_value": zoom_props.getPropertyValue("ZoomValue"),
                "zoom_mode": self._ZOOM_TYPE_TO_MODE.get(zoom_props.getPropertyValue("ZoomType"))}

    def get_selection(self, doc: Any) -> Dict[str, Any]:
        """Return a document-type-specific summary of the current selection."""
        controller = self._get_controller(doc)
        doc_type = self._get_document_type(doc)
        result: Dict[str, Any] = {"type": doc_type, "has_selection": self._has_selection(doc)}
        selection = controller.getSelection()
        if selection is None:
            return result

        if doc_type == "writer":
            try:
                texts = [selection.getByIndex(i).getString() for i in range(selection.getCount())]
                result["selected_text"] = "".join(texts)
                result["range_count"] = selection.getCount()
            except Exception:
                pass
        elif doc_type == "calc":
            try:
                if hasattr(selection, "getRangeAddress"):
                    addr = selection.getRangeAddress()
                    result["range"] = {"sheet": addr.Sheet, "start_column": addr.StartColumn,
                                        "start_row": addr.StartRow, "end_column": addr.EndColumn, "end_row": addr.EndRow}
            except Exception:
                pass
        elif doc_type in ("impress", "draw"):
            try:
                if hasattr(selection, "getCount"):
                    result["shape_count"] = selection.getCount()
                    result["shape_names"] = [selection.getByIndex(i).Name for i in range(selection.getCount())]
            except Exception:
                pass
        return result

    def clear_selection(self, doc: Any) -> None:
        """Collapse/clear the current selection without modifying content."""
        controller = self._get_controller(doc)
        doc_type = self._get_document_type(doc)
        if doc_type == "writer":
            view_cursor = controller.getViewCursor()
            view_cursor.collapseToStart()
        elif doc_type == "calc":
            active_sheet = controller.getActiveSheet()
            controller.select(active_sheet.getCellByPosition(0, 0))
        elif doc_type in ("impress", "draw"):
            controller.select(())
        else:
            raise NotImplementedError(f"clear_selection is not implemented for document type '{doc_type}'.")

    def lock_document_updates(self, doc: Any) -> None:
        """Temporarily lock automatic view/model update via XModel.lockControllers()."""
        doc.lockControllers()

    def unlock_document_updates(self, doc: Any) -> None:
        """Release the update lock via XModel.unlockControllers() -- must be
        called exactly once per lock_document_updates() call; UNO tracks
        this as a nesting count, not a boolean."""
        doc.unlockControllers()

    # -- Styles and formatting -----------------------------------------

    # Family -> UNO service name, for creating a brand-new style instance
    # via doc.createInstance(). Only these 6 families are covered this
    # pass (reasonably well-established UNO service names); an
    # unrecognized family raises NotImplementedError rather than guessing.
    _STYLE_FAMILY_SERVICES = {
        "ParagraphStyles": "com.sun.star.style.ParagraphStyle",
        "CharacterStyles": "com.sun.star.style.CharacterStyle",
        "PageStyles": "com.sun.star.style.PageStyle",
        "FrameStyles": "com.sun.star.style.FrameStyle",
        "NumberingStyles": "com.sun.star.style.NumberingStyle",
        "CellStyles": "com.sun.star.style.CellStyle",
    }

    # Family -> the text-range property that actually applies a style of
    # that family. Only Writer's two most common families are covered
    # this pass (high-confidence UNO property names, live-verified);
    # apply_style for any other family raises UNSUPPORTED_CAPABILITY
    # rather than guessing at a property name that could silently apply
    # the wrong thing.
    _STYLE_FAMILY_APPLY_PROPERTY = {
        "ParagraphStyles": "ParaStyleName",
        "CharacterStyles": "CharStyleName",
    }

    def _get_style_family(self, doc: Any, family: str) -> Any:
        """Return the XNameContainer for one style family via XStyleFamiliesSupplier.

        Raises:
            KeyError: `family` isn't a family this document has.
        """
        families = doc.getStyleFamilies()
        if not families.hasByName(family):
            raise KeyError(f"No such style family '{family}'. Available: {sorted(families.getElementNames())}")
        return families.getByName(family)

    def list_style_families(self, doc: Any) -> Dict[str, Any]:
        return {"families": sorted(doc.getStyleFamilies().getElementNames())}

    def list_styles(self, doc: Any, family: str) -> Dict[str, Any]:
        family_container = self._get_style_family(doc, family)
        styles = []
        for i in range(family_container.getCount()):
            style = family_container.getByIndex(i)
            styles.append({
                "name": style.Name,
                "is_user_defined": style.isUserDefined() if hasattr(style, "isUserDefined") else None,
                "is_in_use": style.isInUse() if hasattr(style, "isInUse") else None,
            })
        return {"family": family, "styles": styles}

    def get_style(self, doc: Any, family: str, style_name: str) -> Dict[str, Any]:
        family_container = self._get_style_family(doc, family)
        if not family_container.hasByName(style_name):
            raise KeyError(f"No such style '{style_name}' in family '{family}'.")
        style = family_container.getByName(style_name)
        return {
            "name": style.Name,
            "parent_style": getattr(style, "ParentStyle", None) or None,
            "is_user_defined": style.isUserDefined() if hasattr(style, "isUserDefined") else None,
            "is_in_use": style.isInUse() if hasattr(style, "isInUse") else None,
        }

    def create_style(self, doc: Any, family: str, style_name: str, parent_style: Optional[str] = None,
                      properties: Optional[Dict[str, Any]] = None) -> List[str]:
        """Create a user style. Returns the list of `properties` keys actually applied."""
        family_container = self._get_style_family(doc, family)
        if family_container.hasByName(style_name):
            raise FileExistsError(f"Style '{style_name}' already exists in family '{family}'.")
        service_name = self._STYLE_FAMILY_SERVICES.get(family)
        if service_name is None:
            raise NotImplementedError(f"create_style is not implemented for family '{family}'.")
        new_style = doc.createInstance(service_name)
        family_container.insertByName(style_name, new_style)
        if parent_style:
            new_style.ParentStyle = parent_style
        applied = []
        for key, value in (properties or {}).items():
            try:
                new_style.setPropertyValue(key, value)
                applied.append(key)
            except Exception:
                pass
        return applied

    def clone_style(self, doc: Any, family: str, source_style: str, new_style_name: str) -> None:
        """Clone an existing style: create new_style_name in the same family
        with the same parent, then copy every directly-set (non-default,
        non-readonly) property value from the source."""
        family_container = self._get_style_family(doc, family)
        if not family_container.hasByName(source_style):
            raise KeyError(f"No such style '{source_style}' in family '{family}'.")
        if family_container.hasByName(new_style_name):
            raise FileExistsError(f"Style '{new_style_name}' already exists in family '{family}'.")
        service_name = self._STYLE_FAMILY_SERVICES.get(family)
        if service_name is None:
            raise NotImplementedError(f"clone_style is not implemented for family '{family}'.")

        source = family_container.getByName(source_style)
        clone = doc.createInstance(service_name)
        family_container.insertByName(new_style_name, clone)
        if getattr(source, "ParentStyle", None):
            clone.ParentStyle = source.ParentStyle

        info = source.getPropertySetInfo()
        for prop in info.getProperties():
            try:
                if source.getPropertyState(prop.Name) != uno.Enum("com.sun.star.beans.PropertyState", "DIRECT_VALUE"):
                    continue
                clone.setPropertyValue(prop.Name, source.getPropertyValue(prop.Name))
            except Exception:
                continue

    def update_style(self, doc: Any, family: str, style_name: str, properties: Dict[str, Any]) -> List[str]:
        """Update style properties. Returns the list of keys actually applied."""
        family_container = self._get_style_family(doc, family)
        if not family_container.hasByName(style_name):
            raise KeyError(f"No such style '{style_name}' in family '{family}'.")
        style = family_container.getByName(style_name)
        applied = []
        for key, value in properties.items():
            try:
                style.setPropertyValue(key, value)
                applied.append(key)
            except Exception:
                pass
        return applied

    def rename_style(self, doc: Any, family: str, old_name: str, new_name: str) -> None:
        family_container = self._get_style_family(doc, family)
        if not family_container.hasByName(old_name):
            raise KeyError(f"No such style '{old_name}' in family '{family}'.")
        if family_container.hasByName(new_name):
            raise FileExistsError(f"A style named '{new_name}' already exists in family '{family}'.")
        style = family_container.getByName(old_name)
        if not hasattr(style, "setName"):
            raise NotImplementedError(f"Styles in family '{family}' do not support renaming.")
        style.setName(new_name)

    def delete_style(self, doc: Any, family: str, style_name: str) -> None:
        family_container = self._get_style_family(doc, family)
        if not family_container.hasByName(style_name):
            raise KeyError(f"No such style '{style_name}' in family '{family}'.")
        style = family_container.getByName(style_name)
        if hasattr(style, "isUserDefined") and not style.isUserDefined():
            raise ValueError(f"'{style_name}' is a built-in style and cannot be deleted.")
        family_container.removeByName(style_name)

    def _resolve_text_target(self, doc: Any, target: Optional[Any]) -> Any:
        """Resolve `target` to a Writer text range.

        target=None -> the first range of the current selection.
        target={"start": int, "end": int} -> a 0-based character range,
        built the same way select_text_range() already does.

        This is the concrete resolution chosen for apply_style_live/
        get_direct_formatting_live/clear_direct_formatting_live/
        copy_formatting_live's previously-undecided `target` shape --
        Writer text ranges only this pass; other document types raise
        WRONG_DOCUMENT_TYPE via the caller's _get_document_type check.
        """
        if target is None:
            controller = self._get_controller(doc)
            selection = controller.getSelection()
            if selection is None or not hasattr(selection, "getCount") or selection.getCount() == 0:
                raise ValueError("No current selection and no target given.")
            return selection.getByIndex(0)
        if isinstance(target, dict) and "start" in target and "end" in target:
            start, end = target["start"], target["end"]
            if start < 0 or end < start:
                raise ValueError(f"Invalid target range: start={start}, end={end}")
            text = doc.getText()
            cursor = text.createTextCursor()
            cursor.gotoStart(False)
            if start > 0:
                cursor.goRight(start, False)
            length = end - start
            if length > 0:
                cursor.goRight(length, True)
            return cursor
        raise ValueError("target must be omitted (use current selection) or {'start': int, 'end': int}.")

    def apply_style(self, doc: Any, family: str, style_name: str, target: Optional[Any] = None) -> None:
        doc_type = self._get_document_type(doc)
        if doc_type != "writer":
            raise NotImplementedError(f"apply_style is only implemented for Writer documents this pass, not '{doc_type}'.")
        family_container = self._get_style_family(doc, family)
        if not family_container.hasByName(style_name):
            raise KeyError(f"No such style '{style_name}' in family '{family}'.")
        apply_property = self._STYLE_FAMILY_APPLY_PROPERTY.get(family)
        if apply_property is None:
            raise NotImplementedError(f"apply_style is not implemented for family '{family}'.")
        text_range = self._resolve_text_target(doc, target)
        text_range.setPropertyValue(apply_property, style_name)

    def get_direct_formatting(self, doc: Any, target: Optional[Any] = None) -> Dict[str, Any]:
        """Return every property whose PropertyState is DIRECT_VALUE on the
        target text range.

        Scope note: Writer text ranges implement both CharacterProperties
        and ParagraphProperties, so this can include structural/paragraph-
        level properties (e.g. ParaStyleName, PageStyleName) alongside
        genuine direct character-formatting overrides -- not filtered down
        to a curated "formatting-only" subset, just JSON-safe DIRECT_VALUE
        properties. Object-reference properties (e.g. a paragraph's own
        TextParagraph self-reference) are excluded via _is_json_safe
        rather than dumped as an opaque repr string.
        """
        doc_type = self._get_document_type(doc)
        if doc_type != "writer":
            raise NotImplementedError(f"get_direct_formatting is only implemented for Writer documents this pass, not '{doc_type}'.")
        text_range = self._resolve_text_target(doc, target)
        direct_value = uno.Enum("com.sun.star.beans.PropertyState", "DIRECT_VALUE")
        overrides = {}
        for prop in text_range.getPropertySetInfo().getProperties():
            try:
                if text_range.getPropertyState(prop.Name) != direct_value:
                    continue
                plain_value = self._uno_value_to_plain(text_range.getPropertyValue(prop.Name))
                if self._is_json_safe(plain_value):
                    overrides[prop.Name] = plain_value
            except Exception:
                continue
        return {"direct_formatting": overrides}

    def clear_direct_formatting(self, doc: Any, target: Optional[Any] = None) -> None:
        doc_type = self._get_document_type(doc)
        if doc_type != "writer":
            raise NotImplementedError(f"clear_direct_formatting is only implemented for Writer documents this pass, not '{doc_type}'.")
        text_range = self._resolve_text_target(doc, target)
        if not hasattr(text_range, "setAllPropertiesToDefault"):
            raise NotImplementedError("This target does not support clearing direct formatting (XMultiPropertyStates).")
        text_range.setAllPropertiesToDefault()

    def copy_formatting(self, doc: Any, source: Any, target: Any, include: Optional[List[str]] = None) -> List[str]:
        """Copy every directly-set (non-default) property from source to
        target. Returns the list of property names actually copied."""
        doc_type = self._get_document_type(doc)
        if doc_type != "writer":
            raise NotImplementedError(f"copy_formatting is only implemented for Writer documents this pass, not '{doc_type}'.")
        source_range = self._resolve_text_target(doc, source)
        target_range = self._resolve_text_target(doc, target)
        direct_value = uno.Enum("com.sun.star.beans.PropertyState", "DIRECT_VALUE")
        applied = []
        for prop in source_range.getPropertySetInfo().getProperties():
            if include and prop.Name not in include:
                continue
            try:
                if source_range.getPropertyState(prop.Name) != direct_value:
                    continue
                value = source_range.getPropertyValue(prop.Name)
                if not self._is_json_safe(self._uno_value_to_plain(value)):
                    continue  # skip object-reference properties (e.g. TextParagraph self-reference)
                target_range.setPropertyValue(prop.Name, value)
                applied.append(prop.Name)
            except Exception:
                continue
        return applied

    def refresh_document(self, doc: Any) -> None:
        """Refresh fields/links/data via XRefreshable, where the document type supports it."""
        if not hasattr(doc, "refresh"):
            raise NotImplementedError("This document does not support XRefreshable.refresh().")
        doc.refresh()

    def reload_document(self, doc: Any, discard_changes: bool = False) -> Any:
        """Reload a document from storage. Returns the NEW document
        component -- the old one is closed and its UNO object becomes
        invalid, so callers must re-point any document_id they had for it
        at the returned object (see tools.documents.DocumentRegistry.replace_document).

        Raises:
            ValueError: no stored location to reload from, or unsaved
                changes exist and discard_changes is False (headless --
                there is no UI to prompt for confirmation).
        """
        if not doc.hasLocation():
            raise ValueError("Document has no stored location to reload from.")
        if doc.isModified() and not discard_changes:
            raise ValueError("Document has unsaved changes; pass discard_changes=true to reload anyway.")
        url = doc.getURL()
        doc.close(False)
        new_doc = self.desktop.loadComponentFromURL(url, "_blank", 0, ())
        if new_doc is None:
            raise RuntimeError(f"LibreOffice returned no document reloading {url}")
        return new_doc

    def save_as_document(self, doc: Any, file_path: str, filter_name: Optional[str] = None,
                          filter_options: Optional[Dict[str, Any]] = None, overwrite: bool = False) -> None:
        """Explicit Save As: changes the document's own stored location, unlike save_copy_document()."""
        if not overwrite and os.path.exists(file_path):
            raise FileExistsError(f"{file_path} already exists; pass overwrite=true to replace it.")
        url = uno.systemPathToFileUrl(file_path)
        props = [PropertyValue("Overwrite", 0, overwrite, 0)]
        if filter_name:
            props.append(PropertyValue("FilterName", 0, filter_name, 0))
        if filter_options:
            props.append(PropertyValue(
                "FilterData", 0,
                tuple(PropertyValue(k, 0, v, 0) for k, v in filter_options.items()), 0))
        doc.storeAsURL(url, tuple(props))

    def save_copy_document(self, doc: Any, file_path: str, filter_name: Optional[str] = None,
                            overwrite: bool = False) -> None:
        """Store a copy without changing the document's own stored location."""
        if not overwrite and os.path.exists(file_path):
            raise FileExistsError(f"{file_path} already exists; pass overwrite=true to replace it.")
        url = uno.systemPathToFileUrl(file_path)
        props = [PropertyValue("Overwrite", 0, overwrite, 0)]
        if filter_name:
            props.append(PropertyValue("FilterName", 0, filter_name, 0))
        doc.storeToURL(url, tuple(props))

    def convert_document_file(self, input_path: str, output_path: str,
                               output_format: Optional[str] = None, options: Optional[Dict[str, Any]] = None) -> None:
        """Open-convert-save between formats without disturbing any already-open document.

        Loads input_path hidden, stores to output_path (inferring a filter
        from output_format if given, else from output_path's extension via
        _guess_filter_name), and always closes the temporary load -- this
        document is never tracked by DocumentRegistry.
        """
        if not os.path.isfile(input_path):
            raise FileNotFoundError(f"No such file: {input_path}")
        filter_name = self._guess_filter_name(output_format, output_path)
        source_url = uno.systemPathToFileUrl(input_path)
        temp_doc = self.desktop.loadComponentFromURL(source_url, "_blank", 0, (
            PropertyValue("Hidden", 0, True, 0),
        ))
        if temp_doc is None:
            raise RuntimeError(f"LibreOffice returned no document for {input_path}")
        try:
            target_url = uno.systemPathToFileUrl(output_path)
            props = [PropertyValue("Overwrite", 0, True, 0)]
            if filter_name:
                props.append(PropertyValue("FilterName", 0, filter_name, 0))
            if options:
                props.append(PropertyValue(
                    "FilterData", 0,
                    tuple(PropertyValue(k, 0, v, 0) for k, v in options.items()), 0))
            temp_doc.storeToURL(target_url, tuple(props))
        finally:
            temp_doc.close(False)

    # Deliberately small -- only the same formats export_document() already
    # supports, plus odt/ods/odp for round-tripping. Extend as more formats
    # are needed rather than guessing at unfamiliar filter names.
    _FILTER_NAME_MAP = {
        "pdf": "writer_pdf_Export", "docx": "MS Word 2007 XML", "doc": "MS Word 97",
        "odt": "writer8", "txt": "Text", "rtf": "Rich Text Format", "html": "HTML (StarWriter)",
        "ods": "calc8", "xlsx": "Calc MS Excel 2007 XML", "csv": "Text - txt - csv (StarCalc)",
        "odp": "impress8", "pptx": "Impress MS PowerPoint 2007 XML",
    }

    def _guess_filter_name(self, output_format: Optional[str], output_path: str) -> Optional[str]:
        key = (output_format or os.path.splitext(output_path)[1].lstrip(".")).lower()
        filter_name = self._FILTER_NAME_MAP.get(key)
        if filter_name is None:
            raise ValueError(
                f"Unsupported/unrecognized output format '{key}'. "
                f"Supported: {sorted(self._FILTER_NAME_MAP)}"
            )
        return filter_name

    def list_export_filters(self, doc: Any) -> Dict[str, Any]:
        """List UNO filters registered for this document's type.

        Scope limit: filters by DocumentService match only, not by an
        import/export capability flag (the UNO FilterFlags bitmask isn't
        exercised here to avoid guessing at an undocumented value) -- the
        returned list may include import-only filters alongside export
        ones. Good enough to show what's registered; not a strict
        "export capable" guarantee.
        """
        doc_type = self._get_document_type(doc)
        service_map = {
            "writer": "com.sun.star.text.TextDocument",
            "calc": "com.sun.star.sheet.SpreadsheetDocument",
            "impress": "com.sun.star.presentation.PresentationDocument",
            "draw": "com.sun.star.drawing.DrawingDocument",
        }
        document_service = service_map.get(doc_type)
        if document_service is None:
            return {"document_type": doc_type, "filters": [], "warning": f"No known service mapping for type '{doc_type}'"}

        filter_factory = self.smgr.createInstanceWithContext("com.sun.star.document.FilterFactory", self.ctx)
        names = []
        for name in filter_factory.getElementNames():
            try:
                # getByName() returns a tuple of PropertyValue structs, not
                # a mapping -- dict() on it directly raises TypeError
                # ("cannot convert dictionary update sequence element #0
                # to a sequence"); live-verified this the hard way.
                entry = {p.Name: p.Value for p in filter_factory.getByName(name)}
            except Exception:
                continue
            if entry.get("DocumentService") == document_service:
                names.append(name)
        return {"document_type": doc_type, "filters": sorted(names)}

    @staticmethod
    def _uno_value_to_plain(value: Any) -> Any:
        """Convert common non-JSON-safe UNO value types to a plain Python
        value. Handles uno.Enum (-> its string name, e.g. "PORTRAIT") and
        simple Width/Height structs like com.sun.star.awt.Size (-> a dict);
        live-verified that PropertyValue sequences like XPrintable's
        getPrinter() return both of these. Not a general UNO-struct
        converter -- anything else passes through unchanged and falls back
        to str() at the HTTP JSON-encoding boundary (ai_interface.py's
        json.dumps(default=str)), same as before this existed.
        """
        if isinstance(value, uno.Enum):
            return value.value
        if hasattr(value, "Width") and hasattr(value, "Height"):
            return {"width": value.Width, "height": value.Height}
        return value

    @staticmethod
    def _is_json_safe(value: Any) -> bool:
        """True if `value` is a plain type json.dumps can serialize without
        falling back to ai_interface.py's json.dumps(default=str) -- which
        would silently dump a UNO object reference's opaque repr string
        (live-verified this happening for a Writer paragraph's
        TextParagraph property, a self-reference to the paragraph object
        itself, when enumerating all properties on a text range).
        """
        if value is None or isinstance(value, (str, int, float, bool)):
            return True
        if isinstance(value, (list, tuple)):
            return all(UNOBridge._is_json_safe(v) for v in value)
        if isinstance(value, dict):
            return all(isinstance(k, str) and UNOBridge._is_json_safe(v) for k, v in value.items())
        return False

    def get_print_settings(self, doc: Any) -> Dict[str, Any]:
        printer_props = doc.getPrinter()
        return {p.Name: self._uno_value_to_plain(p.Value) for p in printer_props}

    def set_print_settings(self, doc: Any, settings: Dict[str, Any]) -> None:
        doc.setPrinter(tuple(PropertyValue(k, 0, v, 0) for k, v in settings.items()))

    def print_document(self, doc: Any, printer: Optional[str] = None, page_range: Optional[str] = None,
                        copies: int = 1, options: Optional[Dict[str, Any]] = None) -> None:
        """Print via XPrintable. Not live-verified against a physical/virtual
        printer (none available in this environment) -- unit-tested with
        fakes only; treat as higher-risk than the rest of this module until
        a senior engineer validates it against a real printer."""
        if printer:
            doc.setPrinter((PropertyValue("Name", 0, printer, 0),))
        props = [PropertyValue("CopyCount", 0, copies, 0), PropertyValue("Wait", 0, True, 0)]
        if page_range:
            props.append(PropertyValue("Pages", 0, page_range, 0))
        if options:
            for key, value in options.items():
                props.append(PropertyValue(key, 0, value, 0))
        doc.print(tuple(props))

    def get_text_content(self, doc: Any = None) -> Dict[str, Any]:
        """Get text content from a document"""
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc:
                return {"success": False, "error": "No document available"}

            # Check if it's a Writer document
            is_writer = _is_instance(doc, XTextDocument) or \
                        (hasattr(doc, 'supportsService') and doc.supportsService("com.sun.star.text.TextDocument")) or \
                        hasattr(doc, 'getText')

            if is_writer:
                text = doc.getText().getString()
                return {"success": True, "content": text, "length": len(text)}
            else:
                return {"success": False, "error": f"Text extraction not supported for {self._get_document_type(doc)}"}
                
        except Exception as e:
            logger.error(f"Failed to get text content: {e}")
            return {"success": False, "error": str(e)}
    
    def get_comments(self, doc: Any = None) -> Dict[str, Any]:
        """Get all comments/annotations from the document"""
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc:
                return {"success": False, "error": "No document available"}

            comments = []

            # Try to get text fields enumeration (comments are stored as text fields)
            if hasattr(doc, 'getTextFields'):
                text_fields = doc.getTextFields()
                enum = text_fields.createEnumeration()

                while enum.hasMoreElements():
                    field = enum.nextElement()
                    # Check if it's an annotation (comment)
                    if hasattr(field, 'supportsService') and field.supportsService("com.sun.star.text.TextField.Annotation"):
                        comment_data = {
                            # Added so update_comment_live/delete_comment_live/
                            # resolve_comment_live (writer_text.py) can address
                            # this exact comment -- see _comment_id_for()'s
                            # docstring for what this id is (and isn't).
                            "id": self._comment_id_for(field, len(comments)),
                            "author": field.Author if hasattr(field, 'Author') else "",
                            "content": field.Content if hasattr(field, 'Content') else "",
                            "date": str(field.Date) if hasattr(field, 'Date') else "",
                        }
                        # Try to get the anchor text (what the comment is attached to)
                        if hasattr(field, 'getAnchor'):
                            anchor = field.getAnchor()
                            if hasattr(anchor, 'getString'):
                                comment_data["anchor_text"] = anchor.getString()[:100]  # First 100 chars
                        comments.append(comment_data)

            return {"success": True, "comments": comments, "count": len(comments)}

        except Exception as e:
            logger.error(f"Failed to get comments: {e}")
            return {"success": False, "error": str(e)}

    def add_comment(self, text: str, author: str = "AI Assistant", doc: Any = None) -> Dict[str, Any]:
        """Add a comment at the current cursor position"""
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc:
                return {"success": False, "error": "No document available"}

            # Get the current cursor position
            controller = doc.getCurrentController()
            cursor = controller.getViewCursor()

            # Create annotation field
            annotation = doc.createInstance("com.sun.star.text.TextField.Annotation")
            annotation.Content = text
            annotation.Author = author

            # Insert at cursor position
            text_obj = doc.getText()
            text_obj.insertTextContent(cursor, annotation, False)

            logger.info(f"Added comment by {author}: {text[:50]}...")
            return {"success": True, "message": f"Comment added by {author}"}

        except Exception as e:
            logger.error(f"Failed to add comment: {e}")
            return {"success": False, "error": str(e)}

    # ============== Track Changes Tools ==============

    def get_track_changes_status(self, doc: Any = None) -> Dict[str, Any]:
        """
        Get Track Changes status for the document.

        Args:
            doc: Document to check (None for active document)

        Returns:
            Result dictionary with recording, showing, and pending_count
        """
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc:
                return {"success": False, "error": "No document available"}

            doc_type = self._get_document_type(doc)
            if doc_type != "writer":
                return {"success": False, "error": f"Track Changes not supported for {doc_type} documents"}

            # Get RecordChanges and ShowChanges properties
            recording = False
            showing = False
            pending_count = 0

            # Access document properties via XPropertySet
            if hasattr(doc, 'getPropertyValue'):
                try:
                    recording = doc.getPropertyValue("RecordChanges")
                except Exception:
                    pass
                try:
                    showing = doc.getPropertyValue("ShowChanges")
                except Exception:
                    pass

            # Count pending redlines using XRedlinesSupplier
            if hasattr(doc, 'getRedlines'):
                try:
                    redlines = doc.getRedlines()
                    if redlines:
                        pending_count = redlines.getCount()
                except Exception:
                    pass

            logger.info(f"Track Changes status: recording={recording}, showing={showing}, pending={pending_count}")
            return {
                "success": True,
                "recording": recording,
                "showing": showing,
                "pending_count": pending_count
            }

        except Exception as e:
            logger.error(f"Failed to get track changes status: {e}")
            return {"success": False, "error": str(e)}

    def set_track_changes(self, enabled: bool, show: bool = True, doc: Any = None) -> Dict[str, Any]:
        """
        Enable or disable Track Changes recording.

        Args:
            enabled: Whether to enable Track Changes recording
            show: Whether to show tracked changes (default: True)
            doc: Document to modify (None for active document)

        Returns:
            Result dictionary with new state
        """
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc:
                return {"success": False, "error": "No document available"}

            doc_type = self._get_document_type(doc)
            if doc_type != "writer":
                return {"success": False, "error": f"Track Changes not supported for {doc_type} documents"}

            # Set properties via XPropertySet
            if hasattr(doc, 'setPropertyValue'):
                try:
                    doc.setPropertyValue("RecordChanges", enabled)
                except Exception as e:
                    return {"success": False, "error": f"Cannot set RecordChanges: {e}"}
                try:
                    doc.setPropertyValue("ShowChanges", show)
                except Exception as e:
                    return {"success": False, "error": f"Cannot set ShowChanges: {e}"}
            else:
                return {"success": False, "error": "Document does not support property modification"}

            logger.info(f"Set Track Changes: recording={enabled}, showing={show}")
            return {
                "success": True,
                "recording": enabled,
                "showing": show
            }

        except Exception as e:
            logger.error(f"Failed to set track changes: {e}")
            return {"success": False, "error": str(e)}

    def get_tracked_changes(self, doc: Any = None) -> Dict[str, Any]:
        """
        Get list of all tracked changes in the document.

        Args:
            doc: Document to check (None for active document)

        Returns:
            Result dictionary with list of changes
        """
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc:
                return {"success": False, "error": "No document available"}

            doc_type = self._get_document_type(doc)
            if doc_type != "writer":
                return {"success": False, "error": f"Track Changes not supported for {doc_type} documents"}

            changes = []

            # Get redlines using XRedlinesSupplier
            if hasattr(doc, 'getRedlines'):
                redlines = doc.getRedlines()
                if redlines:
                    for i in range(redlines.getCount()):
                        try:
                            redline = redlines.getByIndex(i)

                            # Get redline properties
                            redline_type = ""
                            if hasattr(redline, 'RedlineType'):
                                redline_type = redline.RedlineType

                            text = ""
                            if hasattr(redline, 'getText'):
                                text_obj = redline.getText()
                                if text_obj and hasattr(text_obj, 'getString'):
                                    text = text_obj.getString()

                            author = ""
                            if hasattr(redline, 'RedlineAuthor'):
                                author = redline.RedlineAuthor

                            date_str = ""
                            if hasattr(redline, 'RedlineDateTime'):
                                dt = redline.RedlineDateTime
                                # Format as ISO string
                                date_str = f"{dt.Year:04d}-{dt.Month:02d}-{dt.Day:02d}T{dt.Hours:02d}:{dt.Minutes:02d}:{dt.Seconds:02d}"

                            description = ""
                            if hasattr(redline, 'RedlineComment'):
                                description = redline.RedlineComment

                            changes.append({
                                "index": i,
                                "type": redline_type.lower() if redline_type else "unknown",
                                "text": text[:500] if text else "",  # Limit text length
                                "author": author,
                                "date": date_str,
                                "description": description
                            })
                        except Exception as e:
                            logger.warning(f"Failed to read redline {i}: {e}")
                            continue

            logger.info(f"Found {len(changes)} tracked changes")
            return {
                "success": True,
                "changes": changes,
                "count": len(changes)
            }

        except Exception as e:
            logger.error(f"Failed to get tracked changes: {e}")
            return {"success": False, "error": str(e)}

    def accept_tracked_change(self, index: int, doc: Any = None) -> Dict[str, Any]:
        """
        Accept a specific tracked change by index.

        Args:
            index: Index of the change to accept (0-based)
            doc: Document to modify (None for active document)

        Returns:
            Result dictionary with accepted index
        """
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc:
                return {"success": False, "error": "No document available"}

            doc_type = self._get_document_type(doc)
            if doc_type != "writer":
                return {"success": False, "error": f"Track Changes not supported for {doc_type} documents"}

            if not hasattr(doc, 'getRedlines'):
                return {"success": False, "error": "Document does not support redlines"}

            redlines = doc.getRedlines()
            if not redlines:
                return {"success": False, "error": "No tracked changes in document"}

            count = redlines.getCount()
            if index < 0 or index >= count:
                return {"success": False, "error": f"Index {index} out of range. Valid range: 0-{count-1}"}

            # Get the redline and accept it
            redline = redlines.getByIndex(index)

            # Accept by getting the text range and accepting via the document
            if hasattr(redline, 'getAnchor'):
                anchor = redline.getAnchor()
                if hasattr(anchor, 'getString'):
                    # Use the document's text to accept the redline
                    text = doc.getText()
                    if hasattr(text, 'createTextCursor'):
                        cursor = text.createTextCursorByRange(anchor)
                        # Accept redline - in UNO API, accepting means the change becomes permanent
                        if hasattr(doc, 'acceptRedline'):
                            doc.acceptRedline(index)
                        else:
                            # Alternative: use dispatcher
                            return {"success": False, "error": "Document does not support acceptRedline method"}

            logger.info(f"Accepted tracked change at index {index}")
            return {
                "success": True,
                "accepted_index": index
            }

        except Exception as e:
            logger.error(f"Failed to accept tracked change: {e}")
            return {"success": False, "error": str(e)}

    def reject_tracked_change(self, index: int, doc: Any = None) -> Dict[str, Any]:
        """
        Reject a specific tracked change by index.

        Args:
            index: Index of the change to reject (0-based)
            doc: Document to modify (None for active document)

        Returns:
            Result dictionary with rejected index
        """
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc:
                return {"success": False, "error": "No document available"}

            doc_type = self._get_document_type(doc)
            if doc_type != "writer":
                return {"success": False, "error": f"Track Changes not supported for {doc_type} documents"}

            if not hasattr(doc, 'getRedlines'):
                return {"success": False, "error": "Document does not support redlines"}

            redlines = doc.getRedlines()
            if not redlines:
                return {"success": False, "error": "No tracked changes in document"}

            count = redlines.getCount()
            if index < 0 or index >= count:
                return {"success": False, "error": f"Index {index} out of range. Valid range: 0-{count-1}"}

            # Reject the redline
            if hasattr(doc, 'rejectRedline'):
                doc.rejectRedline(index)
            else:
                return {"success": False, "error": "Document does not support rejectRedline method"}

            logger.info(f"Rejected tracked change at index {index}")
            return {
                "success": True,
                "rejected_index": index
            }

        except Exception as e:
            logger.error(f"Failed to reject tracked change: {e}")
            return {"success": False, "error": str(e)}

    def accept_all_changes(self, doc: Any = None) -> Dict[str, Any]:
        """
        Accept all tracked changes in the document.

        Args:
            doc: Document to modify (None for active document)

        Returns:
            Result dictionary with count of accepted changes
        """
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc:
                return {"success": False, "error": "No document available"}

            doc_type = self._get_document_type(doc)
            if doc_type != "writer":
                return {"success": False, "error": f"Track Changes not supported for {doc_type} documents"}

            if not hasattr(doc, 'getRedlines'):
                return {"success": False, "error": "Document does not support redlines"}

            redlines = doc.getRedlines()
            if not redlines:
                return {"success": True, "accepted_count": 0}

            count = redlines.getCount()
            if count == 0:
                return {"success": True, "accepted_count": 0}

            # Accept in reverse order to avoid index shifting
            accepted = 0
            for i in range(count - 1, -1, -1):
                try:
                    if hasattr(doc, 'acceptRedline'):
                        doc.acceptRedline(i)
                        accepted += 1
                except Exception as e:
                    logger.warning(f"Failed to accept redline {i}: {e}")

            logger.info(f"Accepted {accepted} tracked changes")
            return {
                "success": True,
                "accepted_count": accepted
            }

        except Exception as e:
            logger.error(f"Failed to accept all changes: {e}")
            return {"success": False, "error": str(e)}

    def reject_all_changes(self, doc: Any = None) -> Dict[str, Any]:
        """
        Reject all tracked changes in the document.

        Args:
            doc: Document to modify (None for active document)

        Returns:
            Result dictionary with count of rejected changes
        """
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc:
                return {"success": False, "error": "No document available"}

            doc_type = self._get_document_type(doc)
            if doc_type != "writer":
                return {"success": False, "error": f"Track Changes not supported for {doc_type} documents"}

            if not hasattr(doc, 'getRedlines'):
                return {"success": False, "error": "Document does not support redlines"}

            redlines = doc.getRedlines()
            if not redlines:
                return {"success": True, "rejected_count": 0}

            count = redlines.getCount()
            if count == 0:
                return {"success": True, "rejected_count": 0}

            # Reject in reverse order to avoid index shifting
            rejected = 0
            for i in range(count - 1, -1, -1):
                try:
                    if hasattr(doc, 'rejectRedline'):
                        doc.rejectRedline(i)
                        rejected += 1
                except Exception as e:
                    logger.warning(f"Failed to reject redline {i}: {e}")

            logger.info(f"Rejected {rejected} tracked changes")
            return {
                "success": True,
                "rejected_count": rejected
            }

        except Exception as e:
            logger.error(f"Failed to reject all changes: {e}")
            return {"success": False, "error": str(e)}

    def _is_in_tracked_deletion(self, text_range: Any, doc: Any = None) -> bool:
        """
        Check if a text range is within a tracked deletion.

        Args:
            text_range: The text range to check
            doc: Document to check (None for active document)

        Returns:
            True if range is in a tracked deletion, False otherwise
        """
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc or not hasattr(doc, 'getRedlines'):
                return False

            redlines = doc.getRedlines()
            if not redlines:
                return False

            text = doc.getText()

            for i in range(redlines.getCount()):
                try:
                    redline = redlines.getByIndex(i)

                    # Only check deletion redlines
                    if hasattr(redline, 'RedlineType'):
                        redline_type = redline.RedlineType
                        if redline_type and redline_type.lower() == "delete":
                            # Get redline anchor/range
                            if hasattr(redline, 'getAnchor'):
                                redline_range = redline.getAnchor()

                                # Compare ranges
                                # Check if text_range start is within redline range
                                try:
                                    start_compare = text.compareRegionStarts(text_range, redline_range)
                                    end_compare = text.compareRegionEnds(text_range, redline_range)

                                    # If text_range is fully contained within redline_range
                                    # start_compare >= 0 means text_range starts at or after redline start
                                    # end_compare <= 0 means text_range ends at or before redline end
                                    if start_compare >= 0 and end_compare <= 0:
                                        return True
                                except Exception:
                                    pass
                except Exception:
                    continue

            return False

        except Exception as e:
            logger.warning(f"Error checking tracked deletion: {e}")
            return False

    # ============== Enhanced Editing Tools ==============

    def get_paragraph_count(self, doc: Any = None) -> Dict[str, Any]:
        """
        Get the total number of paragraphs in the document.

        Args:
            doc: Document to analyze (None for active document)

        Returns:
            Result dictionary with paragraph count
        """
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc:
                return {"success": False, "error": "No document available"}

            # Check if it's a Writer document
            doc_type = self._get_document_type(doc)
            if doc_type != "writer":
                return {"success": False, "error": f"Paragraph count not supported for {doc_type} documents"}

            # Get text and enumerate paragraphs
            text = doc.getText()
            enum = text.createEnumeration()

            count = 0
            while enum.hasMoreElements():
                para = enum.nextElement()
                # Check if it's a paragraph (not a table or other content)
                if hasattr(para, 'supportsService') and para.supportsService("com.sun.star.text.Paragraph"):
                    count += 1

            logger.info(f"Document has {count} paragraphs")
            return {"success": True, "count": count}

        except Exception as e:
            logger.error(f"Failed to get paragraph count: {e}")
            return {"success": False, "error": str(e)}

    def get_document_outline(self, doc: Any = None) -> Dict[str, Any]:
        """
        Get document outline (headings) with paragraph numbers and levels.

        Args:
            doc: Document to analyze (None for active document)

        Returns:
            Result dictionary with outline and paragraph count
        """
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc:
                return {"success": False, "error": "No document available"}

            doc_type = self._get_document_type(doc)
            if doc_type != "writer":
                return {"success": False, "error": f"Document outline not supported for {doc_type} documents"}

            text = doc.getText()
            enum = text.createEnumeration()

            outline = []
            paragraph_count = 0

            while enum.hasMoreElements():
                para = enum.nextElement()
                if hasattr(para, 'supportsService') and para.supportsService("com.sun.star.text.Paragraph"):
                    paragraph_count += 1

                    # Check if paragraph has a heading style
                    if hasattr(para, 'ParaStyleName'):
                        style_name = para.ParaStyleName
                        # Check for Heading 1-6 styles
                        if style_name and style_name.startswith("Heading"):
                            try:
                                level = int(style_name.replace("Heading ", "").replace("Heading", "1"))
                            except ValueError:
                                level = 1

                            # Get paragraph text
                            para_text = para.getString() if hasattr(para, 'getString') else ""

                            outline.append({
                                "paragraph": paragraph_count,
                                "level": level,
                                "text": para_text[:200]  # Limit text length
                            })

            logger.info(f"Document outline: {len(outline)} headings, {paragraph_count} paragraphs")
            return {
                "success": True,
                "outline": outline,
                "heading_count": len(outline),
                "paragraph_count": paragraph_count
            }

        except Exception as e:
            logger.error(f"Failed to get document outline: {e}")
            return {"success": False, "error": str(e)}

    def get_paragraph(self, n: int, doc: Any = None) -> Dict[str, Any]:
        """
        Get the content of a specific paragraph by number (1-indexed).

        Args:
            n: Paragraph number (1-indexed)
            doc: Document to read from (None for active document)

        Returns:
            Result dictionary with paragraph content
        """
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc:
                return {"success": False, "error": "No document available"}

            doc_type = self._get_document_type(doc)
            if doc_type != "writer":
                return {"success": False, "error": f"Paragraph access not supported for {doc_type} documents"}

            if n < 1:
                return {"success": False, "error": "Paragraph number must be >= 1"}

            text = doc.getText()
            enum = text.createEnumeration()

            current = 0
            while enum.hasMoreElements():
                para = enum.nextElement()
                if hasattr(para, 'supportsService') and para.supportsService("com.sun.star.text.Paragraph"):
                    current += 1
                    if current == n:
                        content = para.getString() if hasattr(para, 'getString') else ""

                        # Build result with original content
                        result = {
                            "success": True,
                            "paragraph_number": n,
                            "content": content
                        }

                        # Add visible_content if Track Changes is enabled
                        tc_status = self.get_track_changes_status(doc)
                        if tc_status.get("success") and tc_status.get("recording"):
                            # Filter out tracked deletions
                            visible_content = self._filter_tracked_deletions(para, doc)
                            result["visible_content"] = visible_content

                        logger.info(f"Retrieved paragraph {n}")
                        return result

            # Paragraph not found
            return {
                "success": False,
                "error": f"Paragraph {n} out of range. Valid range: 1-{current}"
            }

        except Exception as e:
            logger.error(f"Failed to get paragraph: {e}")
            return {"success": False, "error": str(e)}

    def _filter_tracked_deletions(self, para: Any, doc: Any) -> str:
        """
        Filter out tracked deletions from paragraph content.

        Args:
            para: Paragraph text element
            doc: Document containing the paragraph

        Returns:
            String with tracked deletions filtered out
        """
        try:
            if not hasattr(doc, 'getRedlines'):
                return para.getString() if hasattr(para, 'getString') else ""

            redlines = doc.getRedlines()
            if not redlines or redlines.getCount() == 0:
                return para.getString() if hasattr(para, 'getString') else ""

            # Get paragraph range
            para_start = para.getStart()
            para_end = para.getEnd()
            text = doc.getText()

            # Collect all deletion ranges within this paragraph
            deletion_ranges = []
            for i in range(redlines.getCount()):
                try:
                    redline = redlines.getByIndex(i)

                    # Only check deletion redlines
                    if hasattr(redline, 'RedlineType'):
                        redline_type = redline.RedlineType
                        if redline_type and redline_type.lower() == "delete":
                            if hasattr(redline, 'getAnchor'):
                                redline_range = redline.getAnchor()

                                # Check if deletion overlaps with this paragraph
                                try:
                                    # Use compareRegionStarts/Ends to check overlap
                                    # If deletion is within paragraph, add to list
                                    deletion_ranges.append(redline_range)
                                except Exception:
                                    pass
                except Exception:
                    continue

            # If no deletions, return original text
            if not deletion_ranges:
                return para.getString() if hasattr(para, 'getString') else ""

            # Build visible content by iterating through paragraph portions
            visible_text = []
            if hasattr(para, 'createEnumeration'):
                portion_enum = para.createEnumeration()
                while portion_enum.hasMoreElements():
                    portion = portion_enum.nextElement()

                    # Check if this portion is in a tracked deletion
                    is_deleted = False
                    for del_range in deletion_ranges:
                        try:
                            # Check if portion overlaps with deletion
                            if self._is_in_tracked_deletion(portion, doc):
                                is_deleted = True
                                break
                        except Exception:
                            pass

                    # Add portion text if not deleted
                    if not is_deleted and hasattr(portion, 'getString'):
                        visible_text.append(portion.getString())
            else:
                # Fallback to full paragraph text if can't enumerate portions
                return para.getString() if hasattr(para, 'getString') else ""

            return ''.join(visible_text)

        except Exception as e:
            logger.warning(f"Failed to filter tracked deletions: {e}")
            # Fallback to original content
            return para.getString() if hasattr(para, 'getString') else ""

    def get_paragraphs_range(self, start: int, end: int, doc: Any = None) -> Dict[str, Any]:
        """
        Get content of paragraphs in a range (inclusive, 1-indexed).

        Args:
            start: Starting paragraph number (1-indexed)
            end: Ending paragraph number (inclusive)
            doc: Document to read from (None for active document)

        Returns:
            Result dictionary with paragraphs content
        """
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc:
                return {"success": False, "error": "No document available"}

            doc_type = self._get_document_type(doc)
            if doc_type != "writer":
                return {"success": False, "error": f"Paragraph access not supported for {doc_type} documents"}

            if start < 1:
                return {"success": False, "error": "Start paragraph must be >= 1"}
            if end < start:
                return {"success": False, "error": "End paragraph must be >= start paragraph"}

            text = doc.getText()
            enum = text.createEnumeration()

            paragraphs = []
            current = 0
            total_paragraphs = 0

            while enum.hasMoreElements():
                para = enum.nextElement()
                if hasattr(para, 'supportsService') and para.supportsService("com.sun.star.text.Paragraph"):
                    current += 1
                    total_paragraphs = current

                    if start <= current <= end:
                        content = para.getString() if hasattr(para, 'getString') else ""
                        paragraphs.append({
                            "number": current,
                            "content": content
                        })

                    if current > end:
                        break

            if not paragraphs:
                return {
                    "success": False,
                    "error": f"Range {start}-{end} out of bounds. Document has {total_paragraphs} paragraphs"
                }

            logger.info(f"Retrieved paragraphs {start}-{end}")
            return {
                "success": True,
                "paragraphs": paragraphs,
                "count": len(paragraphs)
            }

        except Exception as e:
            logger.error(f"Failed to get paragraphs range: {e}")
            return {"success": False, "error": str(e)}

    # ============== Cursor Navigation Tools ==============

    def goto_paragraph(self, n: int, doc: Any = None) -> Dict[str, Any]:
        """
        Move the view cursor to the beginning of paragraph n.

        Args:
            n: Paragraph number (1-indexed)
            doc: Document to navigate (None for active document)

        Returns:
            Result dictionary with cursor position
        """
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc:
                return {"success": False, "error": "No document available"}

            doc_type = self._get_document_type(doc)
            if doc_type != "writer":
                return {"success": False, "error": f"Cursor navigation not supported for {doc_type} documents"}

            if n < 1:
                return {"success": False, "error": "Paragraph number must be >= 1"}

            text = doc.getText()
            enum = text.createEnumeration()

            current = 0
            target_para = None
            while enum.hasMoreElements():
                para = enum.nextElement()
                if hasattr(para, 'supportsService') and para.supportsService("com.sun.star.text.Paragraph"):
                    current += 1
                    if current == n:
                        target_para = para
                        break

            if target_para is None:
                return {"success": False, "error": f"Paragraph {n} out of range. Valid range: 1-{current}"}

            # Get the view cursor and move it to the paragraph start
            controller = doc.getCurrentController()
            view_cursor = controller.getViewCursor()

            # Get paragraph start position
            para_start = target_para.getStart()
            view_cursor.gotoRange(para_start, False)

            logger.info(f"Moved cursor to paragraph {n}")
            return {
                "success": True,
                "message": f"Cursor moved to paragraph {n}",
                "paragraph": n
            }

        except Exception as e:
            logger.error(f"Failed to goto paragraph: {e}")
            return {"success": False, "error": str(e)}

    def goto_position(self, char_pos: int, doc: Any = None) -> Dict[str, Any]:
        """
        Move the view cursor to a specific character position.

        Args:
            char_pos: Character position (0-indexed)
            doc: Document to navigate (None for active document)

        Returns:
            Result dictionary with actual position reached
        """
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc:
                return {"success": False, "error": "No document available"}

            doc_type = self._get_document_type(doc)
            if doc_type != "writer":
                return {"success": False, "error": f"Cursor navigation not supported for {doc_type} documents"}

            if char_pos < 0:
                return {"success": False, "error": "Character position must be >= 0"}

            text = doc.getText()
            text_cursor = text.createTextCursor()
            text_cursor.gotoStart(False)

            # Move to position (goRight returns False if it can't move that far)
            actual_moved = 0
            if char_pos > 0:
                moved = text_cursor.goRight(char_pos, False)
                # Count actual position
                text_cursor_check = text.createTextCursor()
                text_cursor_check.gotoStart(False)
                text_cursor_check.gotoRange(text_cursor, True)
                actual_moved = len(text_cursor_check.getString())

            # Move view cursor to this position
            controller = doc.getCurrentController()
            view_cursor = controller.getViewCursor()
            view_cursor.gotoRange(text_cursor, False)

            logger.info(f"Moved cursor to position {actual_moved}")
            return {
                "success": True,
                "message": f"Cursor moved to position {actual_moved}",
                "position": actual_moved,
                "requested_position": char_pos
            }

        except Exception as e:
            logger.error(f"Failed to goto position: {e}")
            return {"success": False, "error": str(e)}

    def get_cursor_position(self, doc: Any = None) -> Dict[str, Any]:
        """
        Get the current cursor character position and paragraph number.

        Args:
            doc: Document to check (None for active document)

        Returns:
            Result dictionary with position and paragraph info
        """
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc:
                return {"success": False, "error": "No document available"}

            doc_type = self._get_document_type(doc)
            if doc_type != "writer":
                return {"success": False, "error": f"Cursor position not supported for {doc_type} documents"}

            controller = doc.getCurrentController()
            view_cursor = controller.getViewCursor()

            # Get character position by measuring from start
            text = doc.getText()
            text_cursor = text.createTextCursor()
            text_cursor.gotoStart(False)
            text_cursor.gotoRange(view_cursor, True)
            char_position = len(text_cursor.getString())

            # Find paragraph number
            enum = text.createEnumeration()
            paragraph_num = 0
            char_count = 0

            while enum.hasMoreElements():
                para = enum.nextElement()
                if hasattr(para, 'supportsService') and para.supportsService("com.sun.star.text.Paragraph"):
                    paragraph_num += 1
                    para_text = para.getString() if hasattr(para, 'getString') else ""
                    char_count += len(para_text) + 1  # +1 for paragraph break

                    if char_count >= char_position:
                        break

            logger.info(f"Cursor at position {char_position}, paragraph {paragraph_num}")
            return {
                "success": True,
                "position": char_position,
                "paragraph": paragraph_num
            }

        except Exception as e:
            logger.error(f"Failed to get cursor position: {e}")
            return {"success": False, "error": str(e)}

    def get_context_around_cursor(self, chars: int = 100, doc: Any = None) -> Dict[str, Any]:
        """
        Get text context around the current cursor position.

        Args:
            chars: Number of characters to get before and after cursor
            doc: Document to read from (None for active document)

        Returns:
            Result dictionary with text before and after cursor
        """
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc:
                return {"success": False, "error": "No document available"}

            doc_type = self._get_document_type(doc)
            if doc_type != "writer":
                return {"success": False, "error": f"Cursor context not supported for {doc_type} documents"}

            controller = doc.getCurrentController()
            view_cursor = controller.getViewCursor()
            text = doc.getText()

            # Get text before cursor
            before_cursor = text.createTextCursor()
            before_cursor.gotoStart(False)
            before_cursor.gotoRange(view_cursor, True)
            full_before = before_cursor.getString()
            text_before = full_before[-chars:] if len(full_before) > chars else full_before

            # Get text after cursor
            after_cursor = text.createTextCursor()
            after_cursor.gotoRange(view_cursor, False)
            after_cursor.gotoEnd(True)
            full_after = after_cursor.getString()
            text_after = full_after[:chars] if len(full_after) > chars else full_after

            # Get current position
            char_position = len(full_before)

            logger.info(f"Got context around position {char_position}")
            return {
                "success": True,
                "before": text_before,
                "after": text_after,
                "position": char_position,
                "chars_requested": chars
            }

        except Exception as e:
            logger.error(f"Failed to get context around cursor: {e}")
            return {"success": False, "error": str(e)}

    # ============== Text Selection Tools ==============

    def select_paragraph(self, n: int, doc: Any = None) -> Dict[str, Any]:
        """
        Select entire paragraph n (1-indexed).

        Args:
            n: Paragraph number (1-indexed)
            doc: Document to work with (None for active document)

        Returns:
            Result dictionary with selected text content
        """
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc:
                return {"success": False, "error": "No document available"}

            doc_type = self._get_document_type(doc)
            if doc_type != "writer":
                return {"success": False, "error": f"Paragraph selection not supported for {doc_type} documents"}

            if n < 1:
                return {"success": False, "error": "Paragraph number must be >= 1"}

            # Find the paragraph
            text = doc.getText()
            enum = text.createEnumeration()

            current = 0
            target_para = None
            while enum.hasMoreElements():
                para = enum.nextElement()
                if hasattr(para, 'supportsService') and para.supportsService("com.sun.star.text.Paragraph"):
                    current += 1
                    if current == n:
                        target_para = para
                        break

            if target_para is None:
                return {"success": False, "error": f"Paragraph {n} out of range. Valid range: 1-{current}"}

            # Get the view cursor and select the paragraph
            controller = doc.getCurrentController()
            view_cursor = controller.getViewCursor()

            # Move to paragraph start
            para_start = target_para.getStart()
            view_cursor.gotoRange(para_start, False)

            # Extend selection to paragraph end
            para_end = target_para.getEnd()
            view_cursor.gotoRange(para_end, True)

            # Get selected text
            selected_text = target_para.getString() if hasattr(target_para, 'getString') else ""

            logger.info(f"Selected paragraph {n}")
            return {
                "success": True,
                "selected_text": selected_text,
                "paragraph": n
            }

        except Exception as e:
            logger.error(f"Failed to select paragraph: {e}")
            return {"success": False, "error": str(e)}

    def select_text_range(self, start: int, end: int, doc: Any = None) -> Dict[str, Any]:
        """
        Select text from start to end character positions (0-indexed).

        Args:
            start: Starting character position (0-indexed)
            end: Ending character position (exclusive)
            doc: Document to work with (None for active document)

        Returns:
            Result dictionary with selected text
        """
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc:
                return {"success": False, "error": "No document available"}

            doc_type = self._get_document_type(doc)
            if doc_type != "writer":
                return {"success": False, "error": f"Text range selection not supported for {doc_type} documents"}

            if start < 0:
                return {"success": False, "error": "Start position must be >= 0"}
            if end < start:
                return {"success": False, "error": "End position must be >= start position"}

            text = doc.getText()
            controller = doc.getCurrentController()
            view_cursor = controller.getViewCursor()

            # Create text cursor for selection
            text_cursor = text.createTextCursor()
            text_cursor.gotoStart(False)

            # Move to start position
            if start > 0:
                text_cursor.goRight(start, False)

            # Store start position
            start_range = text.createTextCursor()
            start_range.gotoRange(text_cursor, False)

            # Move to end position (selecting)
            length = end - start
            if length > 0:
                text_cursor.goRight(length, True)

            # Get selected text
            selected_text = text_cursor.getString()

            # Move view cursor to match selection
            view_cursor.gotoRange(start_range, False)
            view_cursor.gotoRange(text_cursor, True)

            logger.info(f"Selected text range {start}-{end}")
            return {
                "success": True,
                "selected_text": selected_text,
                "start": start,
                "end": end,
                "length": len(selected_text)
            }

        except Exception as e:
            logger.error(f"Failed to select text range: {e}")
            return {"success": False, "error": str(e)}

    def delete_selection(self, doc: Any = None) -> Dict[str, Any]:
        """
        Delete currently selected text.

        Args:
            doc: Document to work with (None for active document)

        Returns:
            Result dictionary with deleted text content
        """
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc:
                return {"success": False, "error": "No document available"}

            doc_type = self._get_document_type(doc)
            if doc_type != "writer":
                return {"success": False, "error": f"Delete selection not supported for {doc_type} documents"}

            # Get current selection
            controller = doc.getCurrentController()
            selection = controller.getSelection()

            if selection.getCount() == 0:
                return {"success": False, "error": "No text selected"}

            # Get the selected text range
            text_range = selection.getByIndex(0)

            # Get the text before deleting
            deleted_text = text_range.getString()

            # Delete by setting empty string
            text_range.setString("")

            logger.info(f"Deleted selection: {len(deleted_text)} characters")
            return {
                "success": True,
                "deleted_text": deleted_text,
                "length": len(deleted_text)
            }

        except Exception as e:
            logger.error(f"Failed to delete selection: {e}")
            return {"success": False, "error": str(e)}

    def replace_selection(self, text: str, doc: Any = None) -> Dict[str, Any]:
        """
        Replace currently selected text with new text.

        Args:
            text: New text to replace selection with
            doc: Document to work with (None for active document)

        Returns:
            Result dictionary with old and new text
        """
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc:
                return {"success": False, "error": "No document available"}

            doc_type = self._get_document_type(doc)
            if doc_type != "writer":
                return {"success": False, "error": f"Replace selection not supported for {doc_type} documents"}

            # Get current selection
            controller = doc.getCurrentController()
            selection = controller.getSelection()

            if selection.getCount() == 0:
                return {"success": False, "error": "No text selected"}

            # Get the selected text range
            text_range = selection.getByIndex(0)

            # Get the old text
            old_text = text_range.getString()

            # Replace with new text
            text_range.setString(text)

            logger.info(f"Replaced selection: {len(old_text)} -> {len(text)} characters")
            return {
                "success": True,
                "old_text": old_text,
                "new_text": text,
                "old_length": len(old_text),
                "new_length": len(text)
            }

        except Exception as e:
            logger.error(f"Failed to replace selection: {e}")
            return {"success": False, "error": str(e)}

    # ============== Search and Replace Tools ==============

    def find_text(self, query: str, doc: Any = None) -> Dict[str, Any]:
        """
        Find all occurrences of query string in the document.

        Args:
            query: String to search for
            doc: Document to search in (None for active document)

        Returns:
            Result dictionary with list of matches and their positions
        """
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc:
                return {"success": False, "error": "No document available"}

            doc_type = self._get_document_type(doc)
            if doc_type != "writer":
                return {"success": False, "error": f"Text search not supported for {doc_type} documents"}

            # Check if Track Changes is enabled
            track_changes_active = False
            if hasattr(doc, 'getPropertyValue'):
                try:
                    recording = doc.getPropertyValue("RecordChanges")
                    showing = doc.getPropertyValue("ShowChanges")
                    track_changes_active = recording or showing
                except Exception:
                    pass

            # Create search descriptor
            search = doc.createSearchDescriptor()
            search.SearchString = query

            # Find all occurrences
            found = doc.findAll(search)

            matches = []
            if found and found.getCount() > 0:
                text = doc.getText()

                for i in range(found.getCount()):
                    match_range = found.getByIndex(i)

                    # Filter out matches in tracked deletions when Track Changes is active
                    if track_changes_active and self._is_in_tracked_deletion(match_range, doc):
                        continue

                    # Calculate character position from start
                    text_cursor = text.createTextCursor()
                    text_cursor.gotoStart(False)
                    text_cursor.gotoRange(match_range.getStart(), True)
                    position = len(text_cursor.getString())

                    # Get matched text
                    matched_text = match_range.getString()

                    matches.append({
                        "position": position,
                        "text": matched_text
                    })

            logger.info(f"Found {len(matches)} occurrences of '{query}' (Track Changes: {track_changes_active})")
            return {
                "success": True,
                "matches": matches,
                "count": len(matches),
                "query": query,
                "track_changes_active": track_changes_active
            }

        except Exception as e:
            logger.error(f"Failed to find text: {e}")
            return {"success": False, "error": str(e)}

    def find_and_replace(self, old: str, new: str, doc: Any = None) -> Dict[str, Any]:
        """
        Find and replace the first occurrence of old with new.

        When Track Changes is enabled, only replaces visible text occurrences,
        skipping matches that are within tracked deletions.

        Args:
            old: String to find
            new: String to replace with
            doc: Document to modify (None for active document)

        Returns:
            Result dictionary with replacement status and position
        """
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc:
                return {"success": False, "error": "No document available"}

            doc_type = self._get_document_type(doc)
            if doc_type != "writer":
                return {"success": False, "error": f"Find and replace not supported for {doc_type} documents"}

            # Check if Track Changes is enabled
            track_changes_status = self.get_track_changes_status(doc)
            track_changes_active = track_changes_status.get("success") and track_changes_status.get("recording", False)

            # Create search descriptor
            search = doc.createSearchDescriptor()
            search.SearchString = old

            # Find first occurrence
            found = doc.findFirst(search)

            # If Track Changes is active, skip matches in tracked deletions
            if track_changes_active and found:
                while found and self._is_in_tracked_deletion(found, doc):
                    # Continue searching for next match
                    found = doc.findNext(found.getEnd(), search)

            if found:
                # Calculate position before replacement
                text = doc.getText()
                text_cursor = text.createTextCursor()
                text_cursor.gotoStart(False)
                text_cursor.gotoRange(found.getStart(), True)
                position = len(text_cursor.getString())

                # Replace the text
                found.setString(new)

                logger.info(f"Replaced first occurrence of '{old}' with '{new}' at position {position}")
                return {
                    "success": True,
                    "replaced": True,
                    "position": position,
                    "old": old,
                    "new": new
                }
            else:
                logger.info(f"No occurrence of '{old}' found")
                return {
                    "success": True,
                    "replaced": False,
                    "old": old,
                    "new": new
                }

        except Exception as e:
            logger.error(f"Failed to find and replace: {e}")
            return {"success": False, "error": str(e)}

    def find_and_replace_all(self, old: str, new: str, doc: Any = None) -> Dict[str, Any]:
        """
        Find and replace all occurrences of old with new.

        Track Changes aware: When Track Changes is enabled, this method iterates
        through matches manually to skip replacements in tracked deletions.
        When Track Changes is disabled, it uses native replaceAll for performance.

        Args:
            old: String to find
            new: String to replace with
            doc: Document to modify (None for active document)

        Returns:
            Result dictionary with count of replacements
        """
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc:
                return {"success": False, "error": "No document available"}

            doc_type = self._get_document_type(doc)
            if doc_type != "writer":
                return {"success": False, "error": f"Find and replace all not supported for {doc_type} documents"}

            # Check if Track Changes is enabled
            track_changes_active = False
            if hasattr(doc, 'getPropertyValue'):
                try:
                    track_changes_active = doc.getPropertyValue("RecordChanges")
                except Exception:
                    pass

            # If Track Changes is disabled, use native replaceAll for performance
            if not track_changes_active:
                replace = doc.createReplaceDescriptor()
                replace.SearchString = old
                replace.ReplaceString = new
                count = doc.replaceAll(replace)

                logger.info(f"Replaced {count} occurrences of '{old}' with '{new}' (Track Changes disabled)")
                return {
                    "success": True,
                    "count": count,
                    "old": old,
                    "new": new,
                    "track_changes_active": False
                }

            # Track Changes is enabled - must iterate manually to skip tracked deletions
            # Native replaceAll ignores Track Changes, so we use findFirst/findNext
            search = doc.createSearchDescriptor()
            search.SearchString = old

            count = 0
            found = doc.findFirst(search)

            while found:
                # Check if this match is in a tracked deletion
                if not self._is_in_tracked_deletion(found, doc):
                    # Replace this visible occurrence
                    found.setString(new)
                    count += 1

                # Find next occurrence
                # Note: We need to recreate the search after replacement
                # to avoid issues with modified text ranges
                search = doc.createSearchDescriptor()
                search.SearchString = old
                found = doc.findNext(found.getEnd(), search)

            logger.info(f"Replaced {count} visible occurrences of '{old}' with '{new}' (Track Changes enabled)")
            return {
                "success": True,
                "count": count,
                "old": old,
                "new": new,
                "track_changes_active": True
            }

        except Exception as e:
            logger.error(f"Failed to find and replace all: {e}")
            return {"success": False, "error": str(e)}

    def _get_document_type(self, doc: Any) -> str:
        """Determine document type"""
        # Try isinstance first if types are available
        if _is_instance(doc, XTextDocument):
            return "writer"
        elif _is_instance(doc, XSpreadsheetDocument):
            return "calc"
        elif _is_instance(doc, XPresentationDocument):
            return "impress"

        # Fallback: check supportsService (works even if types not imported)
        if hasattr(doc, 'supportsService'):
            if doc.supportsService("com.sun.star.text.TextDocument"):
                return "writer"
            elif doc.supportsService("com.sun.star.sheet.SpreadsheetDocument"):
                return "calc"
            elif doc.supportsService("com.sun.star.presentation.PresentationDocument"):
                return "impress"
            elif doc.supportsService("com.sun.star.drawing.DrawingDocument"):
                return "draw"

        # Fallback: check for getText method (Writer documents)
        if hasattr(doc, 'getText'):
            return "writer"

        return "unknown"
    
    def _has_selection(self, doc: Any) -> bool:
        """Check if document has selected content"""
        try:
            if hasattr(doc, 'getCurrentController'):
                controller = doc.getCurrentController()
                if hasattr(controller, 'getSelection'):
                    selection = controller.getSelection()
                    return selection.getCount() > 0
        except Exception:
            pass
        return False

    # -- Writer paragraph/text editing (tools/writer_text.py's 18 tools) --
    #
    # Unlike the block above (this file's original 32-tool surface), every
    # method here raises on failure rather than returning a
    # {"success": False, ...} dict -- matching the document_lifecycle.py/
    # styles.py convention tools/writer_text.py's callers expect
    # (_error_response() maps the exception type to a spec error code).
    #
    # _require_writer() below deliberately uses _get_document_type() (its
    # supportsService()-first, isinstance()-as-fallback check), NOT a bare
    # isinstance(doc, XTextDocument) -- see this module's format_text()
    # for the landmine this avoids repeating: it uses a literal isinstance()
    # check and fails against a document opened via certain paths (known,
    # pre-existing, deliberately left unfixed -- see writer_text.py's
    # module docstring and the styles.py pass's commit message).

    def _require_writer(self, doc: Any, operation: str) -> None:
        doc_type = self._get_document_type(doc)
        if doc_type != "writer":
            raise NotImplementedError(f"{operation} is only implemented for Writer documents, not '{doc_type}'.")

    def _count_paragraphs(self, doc: Any) -> int:
        text = doc.getText()
        enum = text.createEnumeration()
        count = 0
        while enum.hasMoreElements():
            para = enum.nextElement()
            if hasattr(para, "supportsService") and para.supportsService("com.sun.star.text.Paragraph"):
                count += 1
        return count

    def _get_paragraph_object(self, doc: Any, n: int) -> Any:
        """Return the nth (1-indexed) paragraph object via the same text
        enumeration get_paragraph()/goto_paragraph()/select_paragraph()
        already use.

        Raises:
            IndexError: n < 1, or n is past the last paragraph.
        """
        if n < 1:
            raise IndexError(f"Paragraph number must be >= 1, got {n}")
        text = doc.getText()
        enum = text.createEnumeration()
        current = 0
        while enum.hasMoreElements():
            para = enum.nextElement()
            if hasattr(para, "supportsService") and para.supportsService("com.sun.star.text.Paragraph"):
                current += 1
                if current == n:
                    return para
        raise IndexError(f"Paragraph {n} out of range. Document has {current} paragraph(s).")

    def _current_paragraph_index(self, doc: Any) -> int:
        """Return the 1-indexed paragraph number containing the view
        cursor -- the same char-count-then-scan algorithm get_cursor_position()
        already uses, factored out so insert_paragraph() can resolve "the
        current paragraph" when at_paragraph is omitted."""
        controller = self._get_controller(doc)
        view_cursor = controller.getViewCursor()
        text = doc.getText()
        text_cursor = text.createTextCursor()
        text_cursor.gotoStart(False)
        text_cursor.gotoRange(view_cursor, True)
        char_position = len(text_cursor.getString())
        enum = text.createEnumeration()
        paragraph_num = 0
        char_count = 0
        while enum.hasMoreElements():
            para = enum.nextElement()
            if hasattr(para, "supportsService") and para.supportsService("com.sun.star.text.Paragraph"):
                paragraph_num += 1
                char_count += len(para.getString()) + 1
                if char_count >= char_position:
                    break
        return paragraph_num or 1

    def insert_paragraph(self, doc: Any, text: str = "", at_paragraph: Optional[int] = None,
                          position: Optional[str] = None) -> Dict[str, Any]:
        """Insert a new paragraph before/after the current or a specified
        paragraph.

        Technique (standard UNO idiom for "type Enter" at a point): place a
        collapsed cursor at the target paragraph's start (position="before")
        or end (position="after"), then insertString()+insertControlCharacter()
        (or the reverse order for "after") so the paragraph break lands on
        the correct side of the new text.
        """
        self._require_writer(doc, "insert_paragraph")
        position = position or "after"
        if position not in ("before", "after"):
            raise ValueError(f"position must be 'before' or 'after', got {position!r}")
        anchor_n = at_paragraph if at_paragraph is not None else self._current_paragraph_index(doc)
        anchor_para = self._get_paragraph_object(doc, anchor_n)
        text_obj = doc.getText()
        if position == "before":
            cursor = text_obj.createTextCursorByRange(anchor_para.getStart())
            text_obj.insertString(cursor, text, False)
            text_obj.insertControlCharacter(cursor, PARAGRAPH_BREAK, False)
            new_paragraph_number = anchor_n
        else:
            cursor = text_obj.createTextCursorByRange(anchor_para.getEnd())
            text_obj.insertControlCharacter(cursor, PARAGRAPH_BREAK, False)
            text_obj.insertString(cursor, text, False)
            new_paragraph_number = anchor_n + 1
        return {"inserted_paragraph": new_paragraph_number, "text": text}

    def append_paragraph(self, doc: Any, text: str = "", style_name: Optional[str] = None) -> Dict[str, Any]:
        """Append a new paragraph to the end of the document. Always adds a
        new paragraph (never reuses an existing empty trailing one)."""
        self._require_writer(doc, "append_paragraph")
        text_obj = doc.getText()
        cursor = text_obj.createTextCursor()
        cursor.gotoEnd(False)
        text_obj.insertControlCharacter(cursor, PARAGRAPH_BREAK, False)
        text_obj.insertString(cursor, text, False)
        style_applied = False
        if style_name:
            family_container = self._get_style_family(doc, "ParagraphStyles")
            if not family_container.hasByName(style_name):
                raise KeyError(f"No such paragraph style '{style_name}'.")
            cursor.ParaStyleName = style_name
            style_applied = True
        return {"appended_paragraph": self._count_paragraphs(doc), "text": text, "style_applied": style_applied}

    def insert_heading(self, doc: Any, text: str, level: int = 1, at_paragraph: Optional[int] = None,
                        position: Optional[str] = None) -> Dict[str, Any]:
        self._require_writer(doc, "insert_heading")
        if level < 1:
            raise ValueError(f"level must be >= 1, got {level}")
        style_name = f"Heading {level}"
        family_container = self._get_style_family(doc, "ParagraphStyles")
        if not family_container.hasByName(style_name):
            raise KeyError(f"No such paragraph style '{style_name}' (level {level}).")
        result = self.insert_paragraph(doc, text=text, at_paragraph=at_paragraph, position=position)
        para = self._get_paragraph_object(doc, result["inserted_paragraph"])
        para.ParaStyleName = style_name
        result["style"] = style_name
        result["level"] = level
        return result

    def set_paragraph_text(self, doc: Any, n: int, text: str) -> Dict[str, Any]:
        """Replace paragraph n's text in place -- setString() on the same
        paragraph object preserves paragraph identity/style (no split/merge
        happens), unlike insert_paragraph/split_paragraph/merge_paragraphs."""
        self._require_writer(doc, "set_paragraph_text")
        para = self._get_paragraph_object(doc, n)
        para.setString(text)
        return {"paragraph": n, "text": text}

    def split_paragraph(self, doc: Any, n: int, offset: int) -> Dict[str, Any]:
        self._require_writer(doc, "split_paragraph")
        para = self._get_paragraph_object(doc, n)
        para_text = para.getString()
        if offset < 0 or offset > len(para_text):
            raise IndexError(f"offset {offset} out of range for paragraph {n} (length {len(para_text)})")
        text_obj = doc.getText()
        cursor = text_obj.createTextCursorByRange(para.getStart())
        if offset > 0:
            cursor.goRight(offset, False)
        text_obj.insertControlCharacter(cursor, PARAGRAPH_BREAK, False)
        return {"paragraph": n, "offset": offset, "first_text": para_text[:offset], "second_text": para_text[offset:]}

    def merge_paragraphs(self, doc: Any, first_n: int, count: int = 2, separator: str = " ") -> Dict[str, Any]:
        self._require_writer(doc, "merge_paragraphs")
        if count < 2:
            raise ValueError(f"count must be >= 2 to merge, got {count}")
        last_n = first_n + count - 1
        paras = [self._get_paragraph_object(doc, i) for i in range(first_n, last_n + 1)]
        texts = [p.getString() for p in paras]
        merged_text = separator.join(texts)
        text_obj = doc.getText()
        span = text_obj.createTextCursorByRange(paras[0].getStart())
        span.gotoRange(paras[-1].getEnd(), True)
        span.setString(merged_text)
        return {"merged_into": first_n, "text": merged_text, "paragraphs_removed": count - 1}

    def _delete_paragraph_range(self, doc: Any, start: int, end: int) -> None:
        """Delete paragraphs [start, end] (1-indexed, inclusive) entirely,
        consuming exactly one adjacent paragraph break so no stray empty
        paragraph is left behind -- prefers the trailing break (into the
        next surviving paragraph) and only falls back to the leading break
        when deleting the document's own last paragraph(s), since there is
        no trailing break to take in that case."""
        total = self._count_paragraphs(doc)
        text_obj = doc.getText()
        start_para = self._get_paragraph_object(doc, start)
        end_para = self._get_paragraph_object(doc, end)
        if end < total:
            range_start = start_para.getStart()
            range_end = self._get_paragraph_object(doc, end + 1).getStart()
        elif start > 1:
            range_start = self._get_paragraph_object(doc, start - 1).getEnd()
            range_end = end_para.getEnd()
        else:
            # Deleting every paragraph in the document -- Writer always
            # keeps at least one paragraph, so this empties it instead.
            range_start = start_para.getStart()
            range_end = end_para.getEnd()
        cursor = text_obj.createTextCursorByRange(range_start)
        cursor.gotoRange(range_end, True)
        cursor.setString("")

    def _insert_paragraph_block(self, doc: Any, entries: List[Any], destination: int) -> int:
        """Insert `entries` (a list of (text, para_style_name) pairs) as
        new, consecutive paragraphs so the first one lands at 1-indexed
        paragraph number `destination` in the resulting document.
        destination beyond the current paragraph count appends at the end
        instead of raising. Each paragraph's ParaStyleName is reapplied
        after insertion (best-effort -- an unrecognized/unsettable style
        name is silently skipped rather than failing the whole block, same
        "best effort" spirit as _apply_direct_properties). Returns the
        resolved starting paragraph number the first inserted paragraph
        actually landed at.

        Live-verified real bug this fixed: an earlier version of
        move_paragraphs/copy_paragraphs only carried getString() (plain
        text), silently dropping the source paragraph's style (e.g. moving
        a "Heading 1" paragraph landed as a plain-styled paragraph with the
        same text) -- see the commit message.
        """
        total = self._count_paragraphs(doc)
        if destination > total:
            anchor_n = total
            insert_position = "after"
        else:
            anchor_n = destination
            insert_position = "before"
        for offset, (text, para_style_name) in enumerate(entries):
            para_n = anchor_n + offset
            self.insert_paragraph(doc, text=text, at_paragraph=para_n, position=insert_position)
            landed_n = para_n if insert_position == "before" else para_n + 1
            if para_style_name:
                try:
                    self._get_paragraph_object(doc, landed_n).ParaStyleName = para_style_name
                except Exception:
                    pass
        return anchor_n + 1 if insert_position == "after" else anchor_n

    def move_paragraphs(self, doc: Any, start: int, end: int, destination: int) -> Dict[str, Any]:
        self._require_writer(doc, "move_paragraphs")
        if end < start:
            raise ValueError(f"end ({end}) must be >= start ({start})")
        total = self._count_paragraphs(doc)
        if start < 1 or end > total:
            raise IndexError(f"range {start}-{end} out of bounds (document has {total} paragraph(s))")
        if start <= destination <= end:
            raise ValueError(f"destination {destination} falls inside the block being moved ({start}-{end})")
        count = end - start + 1
        paras = [self._get_paragraph_object(doc, i) for i in range(start, end + 1)]
        entries = [(p.getString(), p.ParaStyleName) for p in paras]
        self._delete_paragraph_range(doc, start, end)
        resolved_destination = destination - count if destination > end else destination
        resolved_start = self._insert_paragraph_block(doc, entries, resolved_destination)
        return {"moved_count": count, "destination": resolved_start}

    def copy_paragraphs(self, doc: Any, start: int, end: int, destination: int) -> Dict[str, Any]:
        self._require_writer(doc, "copy_paragraphs")
        if end < start:
            raise ValueError(f"end ({end}) must be >= start ({start})")
        total = self._count_paragraphs(doc)
        if start < 1 or end > total:
            raise IndexError(f"range {start}-{end} out of bounds (document has {total} paragraph(s))")
        paras = [self._get_paragraph_object(doc, i) for i in range(start, end + 1)]
        entries = [(p.getString(), p.ParaStyleName) for p in paras]
        resolved_start = self._insert_paragraph_block(doc, entries, destination)
        return {"copied_count": len(entries), "destination": resolved_start}

    def _apply_direct_properties(self, text_range: Any, properties: Dict[str, Any]) -> List[str]:
        """Set each property directly on a Writer text range via
        setPropertyValue, skipping (not raising on) any name/value UNO
        rejects -- same "best-effort, report what applied" contract as
        update_style()/create_style() above. UNO does not distinguish
        paragraph-format from character-format properties at this level
        (both live on the same text range), so set_paragraph_format() and
        set_character_format() both delegate here."""
        applied = []
        for key, value in properties.items():
            try:
                text_range.setPropertyValue(key, value)
                applied.append(key)
            except Exception:
                continue
        return applied

    def set_paragraph_format(self, doc: Any, target: Optional[Any], properties: Dict[str, Any]) -> List[str]:
        self._require_writer(doc, "set_paragraph_format")
        text_range = self._resolve_text_target(doc, target)
        return self._apply_direct_properties(text_range, properties)

    def set_character_format(self, doc: Any, target: Optional[Any], properties: Dict[str, Any]) -> List[str]:
        self._require_writer(doc, "set_character_format")
        text_range = self._resolve_text_target(doc, target)
        return self._apply_direct_properties(text_range, properties)

    def get_text_range_format(self, doc: Any, start: int, end: int) -> Dict[str, Any]:
        """Return every JSON-safe effective character/paragraph property
        value on a 0-based Writer character range, plus which of those are
        direct overrides (PropertyState DIRECT_VALUE) rather than inherited
        from the paragraph/character style -- a superset of
        get_direct_formatting_live (styles.py), which only reports the
        DIRECT_VALUE subset."""
        self._require_writer(doc, "get_text_range_format")
        if start < 0 or end < start:
            raise ValueError(f"Invalid range: start={start}, end={end}")
        text_range = self._resolve_text_target(doc, {"start": start, "end": end})
        direct_value = uno.Enum("com.sun.star.beans.PropertyState", "DIRECT_VALUE")
        effective: Dict[str, Any] = {}
        direct_overrides = []
        for prop in text_range.getPropertySetInfo().getProperties():
            try:
                plain_value = self._uno_value_to_plain(text_range.getPropertyValue(prop.Name))
                if not self._is_json_safe(plain_value):
                    continue
                effective[prop.Name] = plain_value
                if text_range.getPropertyState(prop.Name) == direct_value:
                    direct_overrides.append(prop.Name)
            except Exception:
                continue
        return {"effective_formatting": effective, "direct_override_properties": sorted(direct_overrides)}

    def find_regex(self, doc: Any, pattern: str, case_sensitive: bool = False) -> Dict[str, Any]:
        """Find via XSearchable with SearchRegularExpression=True -- real
        LibreOffice/ICU regex support, not hand-rolled Python re + manual
        cursor walking (this gives matches with usable positions directly,
        same technique find_text() already uses for plain-text search)."""
        self._require_writer(doc, "find_regex")
        search = doc.createSearchDescriptor()
        search.SearchString = pattern
        search.SearchRegularExpression = True
        search.SearchCaseSensitive = case_sensitive
        found = doc.findAll(search)
        text = doc.getText()
        matches = []
        if found:
            for i in range(found.getCount()):
                match_range = found.getByIndex(i)
                text_cursor = text.createTextCursor()
                text_cursor.gotoStart(False)
                text_cursor.gotoRange(match_range.getStart(), True)
                position = len(text_cursor.getString())
                matched_text = match_range.getString()
                matches.append({"position": position, "text": matched_text, "length": len(matched_text)})
        return {"matches": matches, "count": len(matches), "pattern": pattern, "case_sensitive": case_sensitive}

    def replace_regex(self, doc: Any, pattern: str, replacement: str, all: bool = True) -> Dict[str, Any]:
        """Replace via XReplaceable with SearchRegularExpression=True (native
        regex, including $1-style backreferences in `replacement`)."""
        self._require_writer(doc, "replace_regex")
        if all:
            replace = doc.createReplaceDescriptor()
            replace.SearchString = pattern
            replace.ReplaceString = replacement
            replace.SearchRegularExpression = True
            count = doc.replaceAll(replace)
            return {"count": count, "pattern": pattern, "replacement": replacement, "all": True}
        search = doc.createSearchDescriptor()
        search.SearchString = pattern
        search.SearchRegularExpression = True
        found = doc.findFirst(search)
        if not found:
            return {"replaced": False, "pattern": pattern, "replacement": replacement, "all": False}
        text = doc.getText()
        text_cursor = text.createTextCursor()
        text_cursor.gotoStart(False)
        text_cursor.gotoRange(found.getStart(), True)
        position = len(text_cursor.getString())
        found.setString(replacement)
        return {"replaced": True, "position": position, "pattern": pattern, "replacement": replacement, "all": False}

    def find_by_style(self, doc: Any, family: str, style_name: str) -> Dict[str, Any]:
        """Find paragraphs (family="ParagraphStyles") or character-styled
        runs (family="CharacterStyles") using a named style -- the same
        _STYLE_FAMILY_APPLY_PROPERTY mapping apply_style()/replace_style()
        use, so this only recognizes the two families that mapping covers."""
        self._require_writer(doc, "find_by_style")
        apply_property = self._STYLE_FAMILY_APPLY_PROPERTY.get(family)
        if apply_property is None:
            raise NotImplementedError(f"find_by_style is not implemented for family '{family}'.")
        family_container = self._get_style_family(doc, family)
        if not family_container.hasByName(style_name):
            raise KeyError(f"No such style '{style_name}' in family '{family}'.")
        text = doc.getText()
        enum = text.createEnumeration()
        matches = []
        paragraph_num = 0
        while enum.hasMoreElements():
            para = enum.nextElement()
            if not (hasattr(para, "supportsService") and para.supportsService("com.sun.star.text.Paragraph")):
                continue
            paragraph_num += 1
            if family == "ParagraphStyles":
                if para.getPropertyValue(apply_property) == style_name:
                    matches.append({"paragraph": paragraph_num, "text": para.getString()})
            else:  # CharacterStyles
                portion_enum = para.createEnumeration()
                while portion_enum.hasMoreElements():
                    portion = portion_enum.nextElement()
                    if portion.getPropertyValue(apply_property) == style_name:
                        matches.append({"paragraph": paragraph_num, "text": portion.getString()})
        return {"family": family, "style_name": style_name, "matches": matches, "count": len(matches)}

    def replace_style(self, doc: Any, family: str, old_style: str, new_style: str) -> Dict[str, Any]:
        """Replace every paragraph/run using old_style with new_style."""
        self._require_writer(doc, "replace_style")
        apply_property = self._STYLE_FAMILY_APPLY_PROPERTY.get(family)
        if apply_property is None:
            raise NotImplementedError(f"replace_style is not implemented for family '{family}'.")
        family_container = self._get_style_family(doc, family)
        if not family_container.hasByName(old_style):
            raise KeyError(f"No such style '{old_style}' in family '{family}'.")
        if not family_container.hasByName(new_style):
            raise KeyError(f"No such style '{new_style}' in family '{family}'.")
        text = doc.getText()
        enum = text.createEnumeration()
        count = 0
        while enum.hasMoreElements():
            para = enum.nextElement()
            if not (hasattr(para, "supportsService") and para.supportsService("com.sun.star.text.Paragraph")):
                continue
            if family == "ParagraphStyles":
                if para.getPropertyValue(apply_property) == old_style:
                    para.setPropertyValue(apply_property, new_style)
                    count += 1
            else:  # CharacterStyles
                portion_enum = para.createEnumeration()
                while portion_enum.hasMoreElements():
                    portion = portion_enum.nextElement()
                    if portion.getPropertyValue(apply_property) == old_style:
                        portion.setPropertyValue(apply_property, new_style)
                        count += 1
        return {"family": family, "old_style": old_style, "new_style": new_style, "replaced_count": count}

    # -- Comments (update/delete/resolve) --------------------------------
    #
    # get_comments()/add_comment() above already enumerate/create Writer
    # comments as com.sun.star.text.TextField.Annotation text fields; these
    # three tools address the SAME fields the same way (via
    # doc.getTextFields()'s enumeration, filtered to that service), not a
    # parallel comment model. The only gap they close is identity: neither
    # get_comments() nor the Annotation field service guarantees a stable
    # id: _comment_id_for() below prefers a real UNO "Id" property when this
    # LibreOffice build exposes one on annotation fields (durable), and
    # falls back to the field's ordinal position in document order
    # (session-stable only -- shifts if an earlier comment is added or
    # removed) when it doesn't. Which case this build actually hits is
    # live-verified, see the commit message for this pass.

    def _enumerate_comments(self, doc: Any) -> List[Any]:
        """Return annotation TextField objects in document order -- the
        exact same enumeration get_comments() performs, factored out so
        update/delete/resolve_comment index into a matching order."""
        fields = []
        if hasattr(doc, "getTextFields"):
            text_fields = doc.getTextFields()
            enum = text_fields.createEnumeration()
            while enum.hasMoreElements():
                field = enum.nextElement()
                if hasattr(field, "supportsService") and field.supportsService("com.sun.star.text.TextField.Annotation"):
                    fields.append(field)
        return fields

    def _comment_id_for(self, field: Any, index: int) -> str:
        try:
            if field.getPropertySetInfo().hasPropertyByName("Id"):
                raw_id = field.getPropertyValue("Id")
                if raw_id:
                    return str(raw_id)
        except Exception:
            pass
        return str(index)

    def find_comment_by_id(self, doc: Any, comment_id: str) -> Any:
        """Raises KeyError if no comment has this id."""
        for index, field in enumerate(self._enumerate_comments(doc)):
            if self._comment_id_for(field, index) == comment_id:
                return field
        raise KeyError(f"No comment with id '{comment_id}'.")

    def update_comment(self, doc: Any, comment_id: str, text: Optional[str] = None,
                        author: Optional[str] = None) -> Dict[str, Any]:
        self._require_writer(doc, "update_comment")
        field = self.find_comment_by_id(doc, comment_id)
        applied = []
        if text is not None:
            field.Content = text
            applied.append("text")
        if author is not None:
            field.Author = author
            applied.append("author")
        return {"comment_id": comment_id, "applied": applied}

    def delete_comment(self, doc: Any, comment_id: str) -> None:
        self._require_writer(doc, "delete_comment")
        field = self.find_comment_by_id(doc, comment_id)
        doc.getText().removeTextContent(field)

    _RESOLVED_MARKER = "[RESOLVED] "

    def resolve_comment(self, doc: Any, comment_id: str, resolved: bool = True) -> Dict[str, Any]:
        """Mark a comment resolved via a real UNO "Resolved" property when
        this LibreOffice build's annotation fields expose one; otherwise
        emulate it with a "[RESOLVED] " Content marker (round-trips through
        get_comments_live's content field, but is not a native resolved
        state -- documented, not hidden, per this tool's own spec purpose:
        "where supported; otherwise emulate with metadata")."""
        self._require_writer(doc, "resolve_comment")
        field = self.find_comment_by_id(doc, comment_id)
        try:
            info = field.getPropertySetInfo()
            if info.hasPropertyByName("Resolved"):
                field.setPropertyValue("Resolved", resolved)
                return {"comment_id": comment_id, "resolved": resolved, "emulated": False}
        except Exception:
            pass
        content = field.Content or ""
        has_marker = content.startswith(self._RESOLVED_MARKER)
        if resolved and not has_marker:
            field.Content = self._RESOLVED_MARKER + content
        elif not resolved and has_marker:
            field.Content = content[len(self._RESOLVED_MARKER):]
        return {"comment_id": comment_id, "resolved": resolved, "emulated": True}

    # -- Common drawing objects (tools/drawing_objects.py's 31 tools) --
    #
    # Same raise-on-failure convention as the writer_text.py/styles.py
    # sections above (_error_response() in the tool layer maps exceptions
    # to spec error codes) -- not the {"success": False, ...} dict
    # convention the original 32 use.
    #
    # shape_id/object_id resolution (the ObjectRegistry from
    # docs/OBJECT_HANDLE_DESIGN.md) happens in tools/drawing_objects.py,
    # NOT here -- this bridge layer only ever deals in already-resolved
    # UNO shape objects, exactly like _resolve_text_target() hands
    # already-resolved text ranges to styles.py's methods. Methods below
    # that create a NEW shape (insert_shape/duplicate_shape/insert_image)
    # return the raw UNO shape object; the tool layer registers it to
    # mint its id.
    #
    # container resolution (sheet/page addressing) is live name-or-index
    # resolution, no registry, per docs/OBJECT_HANDLE_DESIGN.md's
    # category split -- _resolve_sheet_by_name_or_index()/
    # _resolve_page_by_name_or_index() below are exactly the
    # "_resolve_sheet()/_resolve_slide() helpers" that design doc left
    # for this pass.
    #
    # Scope limit, deliberate: combine_shapes/split_shape/bind_shapes/
    # unbind_shape (all P3) and insert_embedded_object/
    # activate_embedded_object (also P3) raise NotImplementedError
    # instead of a real implementation. combine/split/bind/unbind only
    # exist as .uno: dispatch commands (no direct UNO API equivalent);
    # live-tested this pass with a real selection + view -- .uno:Combine
    # executed and appeared to work, but crashed the headless soffice
    # process outright on the very next UNO call (a
    # DisposedException: "Binary URP bridge disposed during call"),
    # which would take down the extension's whole host process for every
    # connected MCP client, not just the caller. Not safe to ship without
    # a dedicated isolation/testing pass. insert_embedded_object/
    # activate_embedded_object are the same risk class (OLE
    # activation is also dispatch/verb-based) and were not exploration-
    # tested this pass given the crash above -- left unimplemented rather
    # than guessed at.

    def _require_shape_capable(self, doc: Any, operation: str) -> None:
        doc_type = self._get_document_type(doc)
        if doc_type not in ("writer", "calc", "impress", "draw"):
            raise NotImplementedError(f"{operation} is not supported for document type '{doc_type}'.")

    @staticmethod
    def _resolve_sheet_by_name_or_index(sheets: Any, sheet_ref: str) -> Any:
        if sheets.hasByName(sheet_ref):
            return sheets.getByName(sheet_ref)
        if sheet_ref.isdigit():
            index = int(sheet_ref)
            if 0 <= index < sheets.getCount():
                return sheets.getByIndex(index)
        raise KeyError(f"No such sheet '{sheet_ref}'.")

    @staticmethod
    def _resolve_page_by_name_or_index(pages: Any, page_ref: Any) -> Any:
        """page_ref may be an int (0-based index) or a str (page Name,
        with the same digit-string-falls-back-to-index convention
        _resolve_sheet_by_name_or_index uses)."""
        if isinstance(page_ref, bool):
            raise TypeError("page reference must be an int index or a str name, not bool.")
        if isinstance(page_ref, int):
            if 0 <= page_ref < pages.getCount():
                return pages.getByIndex(page_ref)
            raise IndexError(f"Page index {page_ref} out of range (document has {pages.getCount()} page(s)).")
        page_ref = str(page_ref)
        if pages.hasByName(page_ref):
            return pages.getByName(page_ref)
        if page_ref.isdigit():
            index = int(page_ref)
            if 0 <= index < pages.getCount():
                return pages.getByIndex(index)
        raise KeyError(f"No such page '{page_ref}'.")

    def _resolve_shape_container(self, doc: Any, container: Optional[Any] = None) -> Any:
        """Return the XDrawPage 'container' addresses: Writer's single
        document-wide draw page (container ignored -- there is only
        ever one), a specific Calc sheet's own draw page (container
        required, sheet name or digit-string index), or a specific
        Impress/Draw page (container optional, defaults to page 0;
        int index or name)."""
        self._require_shape_capable(doc, "drawing objects")
        doc_type = self._get_document_type(doc)
        if doc_type == "writer":
            return doc.getDrawPage()
        if doc_type == "calc":
            if container is None:
                raise ValueError("container (sheet name or index) is required for Calc documents.")
            sheet = self._resolve_sheet_by_name_or_index(doc.getSheets(), str(container))
            return sheet.getDrawPage()
        # impress, draw
        pages = doc.getDrawPages()
        if container is None:
            if pages.getCount() == 0:
                raise IndexError("Document has no pages.")
            return pages.getByIndex(0)
        return self._resolve_page_by_name_or_index(pages, container)

    _SHAPE_SERVICE_TYPE_NAMES = (
        ("com.sun.star.drawing.OLE2Shape", "ole"),
        ("com.sun.star.drawing.GraphicObjectShape", "image"),
        ("com.sun.star.drawing.GroupShape", "group"),
        ("com.sun.star.drawing.ConnectorShape", "connector"),
        ("com.sun.star.drawing.CustomShape", "custom"),
        ("com.sun.star.drawing.RectangleShape", "rectangle"),
        ("com.sun.star.drawing.EllipseShape", "ellipse"),
        ("com.sun.star.drawing.LineShape", "line"),
        ("com.sun.star.drawing.PolyPolygonShape", "polygon"),
        ("com.sun.star.drawing.PolyLineShape", "polyline"),
        ("com.sun.star.drawing.OpenBezierShape", "bezier"),
        ("com.sun.star.drawing.ClosedBezierShape", "bezier"),
        ("com.sun.star.drawing.TextShape", "text"),
    )

    @classmethod
    def _get_shape_type(cls, shape: Any) -> str:
        """Best-effort short type name for a shape via supportsService(),
        checked most-specific-first (e.g. an OLE2Shape's ShapeType string
        also often mentions generic drawing terms, so service checks are
        more reliable than string-matching ShapeType directly)."""
        for service_name, short_name in cls._SHAPE_SERVICE_TYPE_NAMES:
            if shape.supportsService(service_name):
                return short_name
        return "other"

    @staticmethod
    def _shape_geometry(shape: Any) -> Dict[str, Any]:
        position = shape.Position
        size = shape.Size
        geometry = {
            "x": position.X, "y": position.Y,
            "width": size.Width, "height": size.Height,
        }
        try:
            geometry["rotation"] = shape.RotateAngle
        except Exception:
            pass
        try:
            geometry["shear"] = shape.ShearAngle
        except Exception:
            pass
        return geometry

    @classmethod
    def _shape_summary(cls, shape: Any, shape_id: str) -> Dict[str, Any]:
        summary: Dict[str, Any] = {
            "shape_id": shape_id,
            "type": cls._get_shape_type(shape),
        }
        summary.update(cls._shape_geometry(shape))
        try:
            if hasattr(shape, "getString"):
                text = shape.getString()
                if text:
                    summary["text"] = text
        except Exception:
            pass
        return summary

    def list_shapes_in_container(self, doc: Any, container: Optional[Any] = None,
                                  type_filter: Optional[str] = None) -> List[Any]:
        """Return the raw UNO shape objects on 'container' (see
        _resolve_shape_container), optionally filtered to one
        _get_shape_type() short name. Registering each into an
        ObjectRegistry (to mint shape_ids) is the tool layer's job."""
        page = self._resolve_shape_container(doc, container)
        shapes = []
        for i in range(page.getCount()):
            shape = page.getByIndex(i)
            if type_filter is not None and self._get_shape_type(shape) != type_filter:
                continue
            shapes.append(shape)
        return shapes

    def get_shape_summary(self, shape: Any, shape_id: str) -> Dict[str, Any]:
        return self._shape_summary(shape, shape_id)

    def get_shape_details(self, shape: Any, shape_id: str) -> Dict[str, Any]:
        details: Dict[str, Any] = {
            "shape_id": shape_id,
            "type": self._get_shape_type(shape),
        }
        details.update(self._shape_geometry(shape))
        try:
            details["z_order"] = shape.ZOrder
        except Exception:
            pass
        try:
            if hasattr(shape, "getString"):
                details["text"] = shape.getString()
        except Exception:
            pass
        for attr, key in (("Title", "title"), ("Description", "description")):
            try:
                value = shape.getPropertyValue(attr)
                if value:
                    details[key] = value
            except Exception:
                pass
        style: Dict[str, Any] = {}
        for prop_name in ("FillColor", "FillStyle", "LineColor", "LineWidth", "LineStyle",
                           "Shadow", "FillTransparence", "LineTransparence"):
            try:
                value = self._uno_value_to_plain(shape.getPropertyValue(prop_name))
                if self._is_json_safe(value):
                    style[prop_name] = value
            except Exception:
                continue
        details["style"] = style
        return details

    _SHAPE_TYPE_SERVICES = {
        "rectangle": "com.sun.star.drawing.RectangleShape",
        "ellipse": "com.sun.star.drawing.EllipseShape",
        "line": "com.sun.star.drawing.LineShape",
        "polygon": "com.sun.star.drawing.PolyPolygonShape",
        "polyline": "com.sun.star.drawing.PolyLineShape",
        "bezier": "com.sun.star.drawing.OpenBezierShape",
        "text": "com.sun.star.drawing.TextShape",
        "custom": "com.sun.star.drawing.CustomShape",
    }

    def insert_shape(self, doc: Any, shape_type: str, position: Dict[str, Any], size: Dict[str, Any],
                      container: Optional[Any] = None, properties: Optional[Dict[str, Any]] = None) -> Any:
        service_name = self._SHAPE_TYPE_SERVICES.get(shape_type)
        if service_name is None:
            raise ValueError(f"Unknown shape_type '{shape_type}'. Supported: {sorted(self._SHAPE_TYPE_SERVICES)}")
        page = self._resolve_shape_container(doc, container)
        shape = doc.createInstance(service_name)
        page.add(shape)
        shape.Position = uno.createUnoStruct("com.sun.star.awt.Point", int(position.get("x", 0)), int(position.get("y", 0)))
        shape.Size = uno.createUnoStruct("com.sun.star.awt.Size", int(size.get("width", 1000)), int(size.get("height", 1000)))
        if properties:
            self._apply_direct_properties(shape, properties)
        return shape

    def delete_shape(self, doc: Any, shape: Any) -> None:
        page = shape.getParent()
        page.remove(shape)

    def duplicate_shape(self, doc: Any, shape: Any, offset: Optional[Dict[str, Any]] = None) -> Any:
        """UNO has no direct 'clone shape' API -- create a new shape of
        the same service and copy every settable property, live-verified
        this captures fill/line/text/geometry style (214 of ~229
        properties copied in testing; the rest are read-only derived
        properties UNO itself refuses to set, silently skipped, matching
        this file's established best-effort setPropertyValue convention)."""
        page = shape.getParent()
        # SupportedServiceNames[0] is always the concrete, most-specific
        # shape service (e.g. "com.sun.star.drawing.RectangleShape") --
        # live-verified for both RectangleShape and EllipseShape; the
        # generic "com.sun.star.drawing.Shape"/"...Text" interfaces this
        # sequence also contains always come later.
        concrete = shape.SupportedServiceNames[0]
        new_shape = doc.createInstance(concrete)
        page.add(new_shape)
        for prop in shape.getPropertySetInfo().getProperties():
            try:
                new_shape.setPropertyValue(prop.Name, shape.getPropertyValue(prop.Name))
            except Exception:
                continue
        if offset:
            pos = new_shape.Position
            new_shape.Position = uno.createUnoStruct(
                "com.sun.star.awt.Point",
                pos.X + int(offset.get("x", 0)),
                pos.Y + int(offset.get("y", 0)),
            )
        return new_shape

    def set_shape_geometry(self, shape: Any, geometry: Dict[str, Any]) -> List[str]:
        applied = []
        if "x" in geometry or "y" in geometry:
            pos = shape.Position
            shape.Position = uno.createUnoStruct(
                "com.sun.star.awt.Point",
                int(geometry.get("x", pos.X)), int(geometry.get("y", pos.Y)),
            )
            applied.extend(k for k in ("x", "y") if k in geometry)
        if "width" in geometry or "height" in geometry:
            size = shape.Size
            shape.Size = uno.createUnoStruct(
                "com.sun.star.awt.Size",
                int(geometry.get("width", size.Width)), int(geometry.get("height", size.Height)),
            )
            applied.extend(k for k in ("width", "height") if k in geometry)
        for key, attr in (("rotation", "RotateAngle"), ("shear", "ShearAngle")):
            if key in geometry:
                try:
                    shape.setPropertyValue(attr, int(geometry[key]))
                    applied.append(key)
                except Exception:
                    continue
        if "flip_horizontal" in geometry or "flip_vertical" in geometry:
            size = shape.Size
            new_width = -abs(size.Width) if geometry.get("flip_horizontal") else abs(size.Width)
            new_height = -abs(size.Height) if geometry.get("flip_vertical") else abs(size.Height)
            try:
                shape.Size = uno.createUnoStruct("com.sun.star.awt.Size", new_width, new_height)
                applied.extend(k for k in ("flip_horizontal", "flip_vertical") if k in geometry)
            except Exception:
                pass
        return applied

    def set_shape_style(self, shape: Any, properties: Dict[str, Any]) -> List[str]:
        return self._apply_direct_properties(shape, properties)

    def set_shape_text(self, shape: Any, text: str) -> None:
        if not hasattr(shape, "setString"):
            raise NotImplementedError("This shape type does not support text.")
        shape.setString(text)

    def format_shape_text(self, shape: Any, properties: Dict[str, Any], range: Optional[Any] = None) -> List[str]:
        if not hasattr(shape, "getText"):
            raise NotImplementedError("This shape type does not support text.")
        text = shape.getText()
        text_range = text  # whole-text default
        if range is not None:
            cursor = text.createTextCursor()
            cursor.gotoStart(False)
            cursor.goRight(int(range.get("start", 0)), False)
            cursor.goRight(int(range.get("end", 0)) - int(range.get("start", 0)), True)
            text_range = cursor
        return self._apply_direct_properties(text_range, properties)

    def set_shape_alt_text(self, shape: Any, title: Optional[str] = None, description: Optional[str] = None) -> List[str]:
        applied = []
        if title is not None:
            shape.setPropertyValue("Title", title)
            applied.append("title")
        if description is not None:
            shape.setPropertyValue("Description", description)
            applied.append("description")
        return applied

    def set_shape_z_order(self, shape: Any, action: Optional[str] = None, z_order: Optional[int] = None) -> int:
        page = shape.getParent()
        max_order = page.getCount() - 1
        if z_order is not None:
            shape.ZOrder = max(0, min(int(z_order), max_order))
        elif action == "front":
            shape.ZOrder = max_order
        elif action == "back":
            shape.ZOrder = 0
        elif action == "forward":
            shape.ZOrder = min(shape.ZOrder + 1, max_order)
        elif action == "backward":
            shape.ZOrder = max(shape.ZOrder - 1, 0)
        else:
            raise ValueError("Either action or z_order must be given.")
        return shape.ZOrder

    @staticmethod
    def _shape_bounds(shape: Any) -> Dict[str, int]:
        pos, size = shape.Position, shape.Size
        return {"left": pos.X, "top": pos.Y, "right": pos.X + size.Width, "bottom": pos.Y + size.Height,
                "center_x": pos.X + size.Width // 2, "center_y": pos.Y + size.Height // 2}

    def align_shapes(self, shapes: List[Any], alignment: str, reference_bounds: Optional[Dict[str, int]] = None) -> None:
        if not shapes:
            return
        all_bounds = [self._shape_bounds(s) for s in shapes]
        bounds = reference_bounds or {
            "left": min(b["left"] for b in all_bounds),
            "top": min(b["top"] for b in all_bounds),
            "right": max(b["right"] for b in all_bounds),
            "bottom": max(b["bottom"] for b in all_bounds),
        }
        bounds.setdefault("center_x", (bounds["left"] + bounds["right"]) // 2)
        bounds.setdefault("center_y", (bounds["top"] + bounds["bottom"]) // 2)
        for shape in shapes:
            pos, size = shape.Position, shape.Size
            new_x, new_y = pos.X, pos.Y
            if alignment == "left":
                new_x = bounds["left"]
            elif alignment == "right":
                new_x = bounds["right"] - size.Width
            elif alignment == "center":
                new_x = bounds["center_x"] - size.Width // 2
            elif alignment == "top":
                new_y = bounds["top"]
            elif alignment == "bottom":
                new_y = bounds["bottom"] - size.Height
            elif alignment == "middle":
                new_y = bounds["center_y"] - size.Height // 2
            else:
                raise ValueError(f"Unknown alignment '{alignment}'.")
            shape.Position = uno.createUnoStruct("com.sun.star.awt.Point", new_x, new_y)

    def distribute_shapes(self, shapes: List[Any], direction: str, mode: Optional[str] = None) -> None:
        if len(shapes) < 3:
            return  # nothing to distribute between fewer than 3 shapes
        axis = "center_x" if direction == "horizontal" else "center_y"
        ordered = sorted(shapes, key=lambda s: self._shape_bounds(s)[axis])
        first_center = self._shape_bounds(ordered[0])[axis]
        last_center = self._shape_bounds(ordered[-1])[axis]
        step = (last_center - first_center) / (len(ordered) - 1)
        for i, shape in enumerate(ordered[1:-1], start=1):
            target_center = first_center + step * i
            pos, size = shape.Position, shape.Size
            if direction == "horizontal":
                new_x = int(target_center - size.Width / 2)
                shape.Position = uno.createUnoStruct("com.sun.star.awt.Point", new_x, pos.Y)
            else:
                new_y = int(target_center - size.Height / 2)
                shape.Position = uno.createUnoStruct("com.sun.star.awt.Point", pos.X, new_y)

    def group_shapes(self, shapes: List[Any]) -> Any:
        if len(shapes) < 2:
            raise ValueError("group_shapes needs at least 2 shapes.")
        page = shapes[0].getParent()
        collection = self.smgr.createInstanceWithContext("com.sun.star.drawing.ShapeCollection", self.ctx)
        for shape in shapes:
            collection.add(shape)
        return page.group(collection)

    def ungroup_shape(self, shape: Any) -> None:
        page = shape.getParent()
        page.ungroup(shape)

    # combine_shapes/split_shape/bind_shapes/unbind_shape (P3) have no
    # bridge methods at all -- see this section's opening comment and
    # tools/drawing_objects.py's module docstring for why (.uno:Combine
    # live-tested this pass, crashed headless soffice on the very next
    # UNO call). Those 4 tools stay pure status="stub" NOT_IMPLEMENTED
    # responses, same as before this pass, rather than a bridge method
    # that only ever raises.

    def insert_connector(self, doc: Any, from_shape: Any, to_shape: Any, from_glue: Optional[str] = None,
                          to_glue: Optional[str] = None, connector_type: Optional[str] = None) -> Any:
        page = from_shape.getParent()
        connector = doc.createInstance("com.sun.star.drawing.ConnectorShape")
        page.add(connector)
        connector.StartShape = from_shape
        connector.EndShape = to_shape
        if from_glue is not None:
            connector.StartGluePointIndex = int(from_glue)
        if to_glue is not None:
            connector.EndGluePointIndex = int(to_glue)
        if connector_type is not None:
            try:
                connector.EdgeKind = uno.Enum("com.sun.star.drawing.ConnectorType", connector_type.upper())
            except Exception:
                pass
        return connector

    def list_glue_points(self, shape: Any) -> List[Dict[str, Any]]:
        glue_points = shape.getGluePoints()
        result = []
        for i in range(glue_points.getCount()):
            gp = glue_points.getByIndex(i)
            result.append({
                "glue_point_id": str(i),
                "x": gp.Position.X, "y": gp.Position.Y,
                "is_user_defined": bool(gp.IsUserDefined),
            })
        return result

    def add_glue_point(self, shape: Any, position: Dict[str, Any], direction: Optional[str] = None) -> str:
        glue_points = shape.getGluePoints()
        new_gp = uno.createUnoStruct("com.sun.star.drawing.GluePoint2")
        new_gp.Position = uno.createUnoStruct("com.sun.star.awt.Point", int(position.get("x", 0)), int(position.get("y", 0)))
        new_gp.Escape = uno.Enum("com.sun.star.drawing.EscapeDirection", (direction or "SMART").upper())
        new_gp.IsUserDefined = True
        index = glue_points.insert(new_gp)
        return str(index)

    def delete_glue_point(self, shape: Any, glue_point_id: str) -> None:
        glue_points = shape.getGluePoints()
        # Live-verified this container's real method name is
        # removeByIndex(), not remove() -- it doesn't exist (AttributeError).
        glue_points.removeByIndex(int(glue_point_id))

    def insert_image(self, doc: Any, file_path: str, container: Optional[Any] = None,
                      position: Optional[Dict[str, Any]] = None, size: Optional[Dict[str, Any]] = None,
                      anchor: Optional[str] = None, wrap: Optional[str] = None) -> Any:
        page = self._resolve_shape_container(doc, container)
        graphic_provider = self.smgr.createInstanceWithContext("com.sun.star.graphic.GraphicProvider", self.ctx)
        file_url = uno.systemPathToFileUrl(file_path) if "://" not in file_path else file_path
        graphic = graphic_provider.queryGraphic((PropertyValue("URL", 0, file_url, 0),))
        shape = doc.createInstance("com.sun.star.drawing.GraphicObjectShape")
        page.add(shape)
        shape.Graphic = graphic
        if position:
            shape.Position = uno.createUnoStruct("com.sun.star.awt.Point", int(position.get("x", 0)), int(position.get("y", 0)))
        if size:
            shape.Size = uno.createUnoStruct("com.sun.star.awt.Size", int(size.get("width", shape.Size.Width)), int(size.get("height", shape.Size.Height)))
        if anchor is not None and hasattr(shape, "AnchorType"):
            try:
                shape.AnchorType = uno.Enum("com.sun.star.text.TextContentAnchorType", anchor.upper())
            except Exception:
                pass
        if wrap is not None and hasattr(shape, "Surround"):
            try:
                shape.Surround = uno.Enum("com.sun.star.text.WrapTextMode", wrap.upper())
            except Exception:
                pass
        return shape

    def replace_image(self, shape: Any, file_path: str) -> None:
        if not hasattr(shape, "Graphic"):
            raise NotImplementedError("This shape is not an image (no Graphic property).")
        graphic_provider = self.smgr.createInstanceWithContext("com.sun.star.graphic.GraphicProvider", self.ctx)
        file_url = uno.systemPathToFileUrl(file_path) if "://" not in file_path else file_path
        graphic = graphic_provider.queryGraphic((PropertyValue("URL", 0, file_url, 0),))
        shape.Graphic = graphic

    def set_image_properties(self, shape: Any, properties: Dict[str, Any]) -> List[str]:
        if not hasattr(shape, "Graphic"):
            raise NotImplementedError("This shape is not an image (no Graphic property).")
        return self._apply_direct_properties(shape, properties)

    def export_shape(self, shape: Any, file_path: str, format: Optional[str] = None, dpi: Optional[int] = None) -> None:
        """dpi, when given, is converted to explicit PixelWidth/PixelHeight
        FilterData from the shape's own Size (1/100mm) -- live-verified
        this is the property pair GraphicExportFilter actually honors
        (a raw "dpi"-named property is not one of its FilterData keys);
        confirmed the exported PNG's real pixel dimensions via a
        readback through GraphicProvider, not just trusting the filter
        call's own success."""
        export_filter = self.smgr.createInstanceWithContext("com.sun.star.drawing.GraphicExportFilter", self.ctx)
        export_filter.setSourceDocument(shape)
        media_type = {
            "png": "image/png", "jpeg": "image/jpeg", "jpg": "image/jpeg", "svg": "image/svg+xml",
        }.get((format or "png").lower(), "image/png")
        props = [
            PropertyValue("URL", 0, uno.systemPathToFileUrl(file_path), 0),
            PropertyValue("MediaType", 0, media_type, 0),
        ]
        if dpi:
            size = shape.Size  # 1/100 mm
            pixel_width = round((size.Width / 100 / 25.4) * dpi)
            pixel_height = round((size.Height / 100 / 25.4) * dpi)
            filter_data = uno.Any("[]com.sun.star.beans.PropertyValue", (
                PropertyValue("PixelWidth", 0, max(pixel_width, 1), 0),
                PropertyValue("PixelHeight", 0, max(pixel_height, 1), 0),
            ))
            props.append(PropertyValue("FilterData", 0, filter_data, 0))
        export_filter.filter(tuple(props))

    def list_embedded_objects(self, doc: Any, container: Optional[Any] = None) -> List[Any]:
        return self.list_shapes_in_container(doc, container, type_filter="ole")

    # insert_embedded_object/activate_embedded_object (P3) have no bridge
    # methods, same reasoning as combine_shapes/split_shape above:
    # embedded-object creation covers a wide, uncertain range of OLE
    # types, and OLE activation is dispatch/verb-based -- the same risk
    # class .uno:Combine crashed headless soffice on this pass. Both stay
    # pure status="stub" NOT_IMPLEMENTED responses.

    def delete_embedded_object(self, doc: Any, shape: Any) -> None:
        self.delete_shape(doc, shape)

    # -- Calc sheets, cells, ranges, formulas (tools/calc_sheets.py's 42 tools) --
    #
    # Same raise-on-failure convention as writer_text.py/drawing_objects.py
    # above. Sheet resolution is the live name-or-index scheme
    # docs/OBJECT_HANDLE_DESIGN.md designed (no registry) --
    # _resolve_sheet_by_name_or_index() (already shared with
    # drawing_objects.py's container resolution) is reused directly;
    # _resolve_sheet() below adds the "omitted -> active sheet" fallback
    # this module's tools need on top of it.
    #
    # Cell/range addressing uses A1 notation directly via
    # XCellRangeAccess.getCellRangeByName() -- live-verified this accepts
    # both single cells ("B3") and ranges ("A1:C3") with no manual address
    # parsing needed; the object it returns implements both XCell and
    # XCellRange simultaneously for a single-cell reference.

    def _require_calc(self, doc: Any, operation: str) -> None:
        doc_type = self._get_document_type(doc)
        if doc_type != "calc":
            raise NotImplementedError(f"{operation} is only implemented for Calc documents, not '{doc_type}'.")

    def _resolve_sheet(self, doc: Any, sheet: Optional[str] = None) -> Any:
        self._require_calc(doc, "sheet resolution")
        if sheet is None:
            return doc.getCurrentController().getActiveSheet()
        return self._resolve_sheet_by_name_or_index(doc.getSheets(), sheet)

    @staticmethod
    def _column_row_to_a1(col: int, row: int) -> str:
        letters = ""
        c = col
        while True:
            letters = chr(ord('A') + c % 26) + letters
            c = c // 26 - 1
            if c < 0:
                break
        return f"{letters}{row + 1}"

    def list_sheets(self, doc: Any) -> List[Dict[str, Any]]:
        self._require_calc(doc, "list_sheets")
        sheets = doc.getSheets()
        result = []
        for i in range(sheets.getCount()):
            sheet = sheets.getByIndex(i)
            result.append({
                "index": i, "name": sheet.Name, "visible": bool(sheet.IsVisible),
                "protected": bool(sheet.isProtected()) if hasattr(sheet, "isProtected") else False,
            })
        return result

    def get_active_sheet(self, doc: Any) -> Dict[str, Any]:
        self._require_calc(doc, "get_active_sheet")
        sheet = doc.getCurrentController().getActiveSheet()
        # A sheet's own index isn't exposed directly -- read it off any
        # cell's address on that sheet (RangeAddress.Sheet), the standard
        # UNO idiom for this.
        index = sheet.getCellRangeByName("A1").RangeAddress.Sheet
        return {"index": index, "name": sheet.Name, "visible": bool(sheet.IsVisible)}

    def activate_sheet(self, doc: Any, sheet: str) -> None:
        self._require_calc(doc, "activate_sheet")
        sheet_obj = self._resolve_sheet_by_name_or_index(doc.getSheets(), sheet)
        doc.getCurrentController().setActiveSheet(sheet_obj)

    def insert_sheet(self, doc: Any, name: str, position: Optional[int] = None) -> None:
        self._require_calc(doc, "insert_sheet")
        sheets = doc.getSheets()
        index = position if position is not None else sheets.getCount()
        sheets.insertNewByName(name, index)

    def delete_sheet(self, doc: Any, sheet: str) -> None:
        self._require_calc(doc, "delete_sheet")
        sheets = doc.getSheets()
        sheet_obj = self._resolve_sheet_by_name_or_index(sheets, sheet)
        sheets.removeByName(sheet_obj.Name)

    def rename_sheet(self, doc: Any, sheet: str, new_name: str) -> None:
        self._require_calc(doc, "rename_sheet")
        sheet_obj = self._resolve_sheet_by_name_or_index(doc.getSheets(), sheet)
        sheet_obj.Name = new_name

    def move_sheet(self, doc: Any, sheet: str, destination_index: int) -> None:
        self._require_calc(doc, "move_sheet")
        sheets = doc.getSheets()
        sheet_obj = self._resolve_sheet_by_name_or_index(sheets, sheet)
        sheets.moveByName(sheet_obj.Name, destination_index)

    def copy_sheet(self, doc: Any, sheet: str, new_name: str, destination_index: Optional[int] = None) -> None:
        self._require_calc(doc, "copy_sheet")
        sheets = doc.getSheets()
        sheet_obj = self._resolve_sheet_by_name_or_index(sheets, sheet)
        index = destination_index if destination_index is not None else sheets.getCount()
        sheets.copyByName(sheet_obj.Name, new_name, index)

    def hide_sheet(self, doc: Any, sheet: str) -> None:
        self._require_calc(doc, "hide_sheet")
        self._resolve_sheet_by_name_or_index(doc.getSheets(), sheet).IsVisible = False

    def show_sheet(self, doc: Any, sheet: str) -> None:
        self._require_calc(doc, "show_sheet")
        self._resolve_sheet_by_name_or_index(doc.getSheets(), sheet).IsVisible = True

    def get_cell(self, doc: Any, cell: str, sheet: Optional[str] = None) -> Dict[str, Any]:
        self._require_calc(doc, "get_cell")
        cell_obj = self._resolve_sheet(doc, sheet).getCellRangeByName(cell)
        return {
            "cell": cell, "value": cell_obj.getValue(), "formula": cell_obj.getFormula(),
            "display": cell_obj.getString(), "error": cell_obj.getError(),
        }

    def set_cell(self, doc: Any, cell: str, sheet: Optional[str] = None,
                 value: Optional[Any] = None, formula: Optional[str] = None) -> Dict[str, Any]:
        self._require_calc(doc, "set_cell")
        cell_obj = self._resolve_sheet(doc, sheet).getCellRangeByName(cell)
        if formula is not None:
            cell_obj.setFormula(formula)
        elif value is not None:
            if isinstance(value, bool):
                cell_obj.setValue(1.0 if value else 0.0)
            elif isinstance(value, (int, float)):
                cell_obj.setValue(float(value))
            else:
                cell_obj.setString(str(value))
        else:
            cell_obj.setString("")
        return {"cell": cell, "display": cell_obj.getString()}

    def get_range(self, doc: Any, range: str, sheet: Optional[str] = None, mode: str = "values") -> Dict[str, Any]:
        self._require_calc(doc, "get_range")
        sheet_obj = self._resolve_sheet(doc, sheet)
        range_obj = sheet_obj.getCellRangeByName(range)
        result: Dict[str, Any] = {"range": range}
        if mode in ("values", "all"):
            result["values"] = [list(row) for row in range_obj.getDataArray()]
        if mode in ("formulas", "all"):
            result["formulas"] = [list(row) for row in range_obj.getFormulaArray()]
        if mode in ("display", "all"):
            # NOTE: `range` is shadowed by this method's own parameter --
            # builtins.range(...) here is deliberate, not a typo.
            addr = range_obj.RangeAddress
            display = []
            for r in builtins.range(addr.StartRow, addr.EndRow + 1):
                row = [sheet_obj.getCellByPosition(c, r).getString() for c in builtins.range(addr.StartColumn, addr.EndColumn + 1)]
                display.append(row)
            result["display"] = display
        return result

    def set_range(self, doc: Any, values: List[List[Any]], sheet: Optional[str] = None,
                   range: Optional[str] = None, start_cell: Optional[str] = None) -> Dict[str, Any]:
        self._require_calc(doc, "set_range")
        sheet_obj = self._resolve_sheet(doc, sheet)
        if range is not None:
            target = sheet_obj.getCellRangeByName(range)
        elif start_cell is not None:
            start_addr = sheet_obj.getCellRangeByName(start_cell).RangeAddress
            end_row = start_addr.StartRow + len(values) - 1
            end_col = start_addr.StartColumn + max((len(r) for r in values), default=1) - 1
            target = sheet_obj.getCellRangeByPosition(start_addr.StartColumn, start_addr.StartRow, end_col, end_row)
        else:
            raise ValueError("Either range or start_cell must be given.")
        # Stringify every value so Calc's own formula-parser auto-detects
        # numbers/text/formulas the same way typing into a cell would --
        # live-verified setDataArray() does NOT do this (a string like
        # "=1+1" is stored as literal text, not evaluated); setFormulaArray()
        # is the one that does real input-style parsing.
        string_rows = tuple(tuple("" if v is None else str(v) for v in row) for row in values)
        target.setFormulaArray(string_rows)
        return {"applied_rows": len(values)}

    _CLEAR_FLAG_PRESETS = {
        "contents": 1 | 2 | 4 | 16,      # VALUE|DATETIME|STRING|FORMULA
        "formats": 32 | 64 | 256 | 512,  # HARDATTR|STYLES|EDITATTR|FORMATTED
        "comments": 8,                   # ANNOTATION
        "objects": 128,                  # OBJECTS
        "all": 1023,
    }

    def clear_range(self, doc: Any, range: str, sheet: Optional[str] = None, what: str = "contents") -> None:
        self._require_calc(doc, "clear_range")
        flags = self._CLEAR_FLAG_PRESETS.get(what)
        if flags is None:
            raise ValueError(f"Unknown 'what' value '{what}'. Supported: {sorted(self._CLEAR_FLAG_PRESETS)}")
        self._resolve_sheet(doc, sheet).getCellRangeByName(range).clearContents(flags)

    def get_used_range(self, doc: Any, sheet: Optional[str] = None) -> Dict[str, Any]:
        self._require_calc(doc, "get_used_range")
        sheet_obj = self._resolve_sheet(doc, sheet)
        start_cursor = sheet_obj.createCursor()
        start_cursor.gotoStartOfUsedArea(False)
        start_addr = start_cursor.RangeAddress
        end_cursor = sheet_obj.createCursor()
        end_cursor.gotoEndOfUsedArea(False)
        end_addr = end_cursor.RangeAddress
        return {
            "start_column": start_addr.StartColumn, "start_row": start_addr.StartRow,
            "end_column": end_addr.EndColumn, "end_row": end_addr.EndRow,
        }

    def insert_rows(self, doc: Any, index: int, sheet: Optional[str] = None, count: int = 1) -> None:
        self._require_calc(doc, "insert_rows")
        self._resolve_sheet(doc, sheet).getRows().insertByIndex(index, count)

    def delete_rows(self, doc: Any, index: int, sheet: Optional[str] = None, count: int = 1) -> None:
        self._require_calc(doc, "delete_rows")
        self._resolve_sheet(doc, sheet).getRows().removeByIndex(index, count)

    def insert_columns(self, doc: Any, index: int, sheet: Optional[str] = None, count: int = 1) -> None:
        self._require_calc(doc, "insert_columns")
        self._resolve_sheet(doc, sheet).getColumns().insertByIndex(index, count)

    def delete_columns(self, doc: Any, index: int, sheet: Optional[str] = None, count: int = 1) -> None:
        self._require_calc(doc, "delete_columns")
        self._resolve_sheet(doc, sheet).getColumns().removeByIndex(index, count)

    _CELL_SHIFT_INSERT = {"right": "RIGHT", "down": "DOWN"}
    _CELL_SHIFT_DELETE = {"left": "LEFT", "up": "UP"}

    def insert_cells(self, doc: Any, range: str, shift: str, sheet: Optional[str] = None) -> None:
        self._require_calc(doc, "insert_cells")
        mode_name = self._CELL_SHIFT_INSERT.get(shift.lower())
        if mode_name is None:
            raise ValueError(f"shift must be one of {sorted(self._CELL_SHIFT_INSERT)}, got '{shift}'")
        sheet_obj = self._resolve_sheet(doc, sheet)
        range_addr = sheet_obj.getCellRangeByName(range).RangeAddress
        sheet_obj.insertCells(range_addr, uno.Enum("com.sun.star.sheet.CellInsertMode", mode_name))

    def delete_cells(self, doc: Any, range: str, shift: str, sheet: Optional[str] = None) -> None:
        self._require_calc(doc, "delete_cells")
        mode_name = self._CELL_SHIFT_DELETE.get(shift.lower())
        if mode_name is None:
            raise ValueError(f"shift must be one of {sorted(self._CELL_SHIFT_DELETE)}, got '{shift}'")
        sheet_obj = self._resolve_sheet(doc, sheet)
        range_addr = sheet_obj.getCellRangeByName(range).RangeAddress
        # Live-verified this container's real method name is removeRange(),
        # not removeCells() -- it doesn't exist (AttributeError) -- the
        # same class of "guessed name is wrong" mistake as
        # delete_glue_point_live's fix in the drawing_objects.py pass.
        sheet_obj.removeRange(range_addr, uno.Enum("com.sun.star.sheet.CellDeleteMode", mode_name))

    @staticmethod
    def _cell_address_from_range(range_obj: Any) -> Any:
        addr = range_obj.RangeAddress
        return uno.createUnoStruct("com.sun.star.table.CellAddress", addr.Sheet, addr.StartColumn, addr.StartRow)

    def copy_range(self, doc: Any, source_range: str, dest_cell: str, source_sheet: Optional[str] = None,
                    dest_sheet: Optional[str] = None, include: Optional[Dict[str, Any]] = None) -> None:
        self._require_calc(doc, "copy_range")
        src_sheet_obj = self._resolve_sheet(doc, source_sheet)
        dst_sheet_obj = self._resolve_sheet(doc, dest_sheet) if dest_sheet is not None else src_sheet_obj
        source_addr = src_sheet_obj.getCellRangeByName(source_range).RangeAddress
        dest_addr = self._cell_address_from_range(dst_sheet_obj.getCellRangeByName(dest_cell))
        dst_sheet_obj.copyRange(dest_addr, source_addr)

    def move_range(self, doc: Any, source_range: str, dest_cell: str,
                    source_sheet: Optional[str] = None, dest_sheet: Optional[str] = None) -> None:
        self._require_calc(doc, "move_range")
        src_sheet_obj = self._resolve_sheet(doc, source_sheet)
        dst_sheet_obj = self._resolve_sheet(doc, dest_sheet) if dest_sheet is not None else src_sheet_obj
        source_addr = src_sheet_obj.getCellRangeByName(source_range).RangeAddress
        dest_addr = self._cell_address_from_range(dst_sheet_obj.getCellRangeByName(dest_cell))
        dst_sheet_obj.moveRange(dest_addr, source_addr)

    _FILL_DIRECTIONS = {"down": "TO_BOTTOM", "up": "TO_TOP", "right": "TO_RIGHT", "left": "TO_LEFT"}
    _FILL_MODES = {"linear": "LINEAR", "growth": "GROWTH", "date": "DATE", "auto": "AUTO", "simple": "SIMPLE"}

    def fill_series(self, doc: Any, range: str, direction: str, mode: str, sheet: Optional[str] = None,
                     start: Optional[Any] = None, step: Optional[float] = None, end: Optional[Any] = None) -> None:
        self._require_calc(doc, "fill_series")
        direction_name = self._FILL_DIRECTIONS.get(direction.lower())
        if direction_name is None:
            raise ValueError(f"direction must be one of {sorted(self._FILL_DIRECTIONS)}, got '{direction}'")
        mode_name = self._FILL_MODES.get(mode.lower())
        if mode_name is None:
            raise ValueError(f"mode must be one of {sorted(self._FILL_MODES)}, got '{mode}'")
        sheet_obj = self._resolve_sheet(doc, sheet)
        range_obj = sheet_obj.getCellRangeByName(range)
        if start is not None:
            # fillSeries needs a seed value already present in the range's
            # first cell -- live-verified an empty first cell produces an
            # entirely empty result, not a series starting from 0.
            first_addr = range_obj.RangeAddress
            first_cell = sheet_obj.getCellByPosition(first_addr.StartColumn, first_addr.StartRow)
            if isinstance(start, (int, float)) and not isinstance(start, bool):
                first_cell.setValue(float(start))
            else:
                first_cell.setString(str(start))
        range_obj.fillSeries(
            uno.Enum("com.sun.star.sheet.FillDirection", direction_name),
            uno.Enum("com.sun.star.sheet.FillMode", mode_name),
            uno.Enum("com.sun.star.sheet.FillDateMode", "FILL_DATE_DAY"),
            float(step) if step is not None else 1.0,
            float(end) if end is not None else 1e20,
        )

    def autofill(self, doc: Any, source_range: str, destination_range: str, sheet: Optional[str] = None) -> None:
        self._require_calc(doc, "autofill")
        sheet_obj = self._resolve_sheet(doc, sheet)
        source_addr = sheet_obj.getCellRangeByName(source_range).RangeAddress
        dest_addr = sheet_obj.getCellRangeByName(destination_range).RangeAddress
        if dest_addr.StartColumn > source_addr.EndColumn:
            direction = "TO_RIGHT"
        elif dest_addr.EndColumn < source_addr.StartColumn:
            direction = "TO_LEFT"
        elif dest_addr.StartRow > source_addr.EndRow:
            direction = "TO_BOTTOM"
        else:
            direction = "TO_TOP"
        source_count = (source_addr.EndRow - source_addr.StartRow + 1) * (source_addr.EndColumn - source_addr.StartColumn + 1)
        # fillAuto's own range argument must span source+destination
        # together (live-verified against a simple down-fill case) --
        # not just the destination.
        full_range = sheet_obj.getCellRangeByPosition(
            min(source_addr.StartColumn, dest_addr.StartColumn), min(source_addr.StartRow, dest_addr.StartRow),
            max(source_addr.EndColumn, dest_addr.EndColumn), max(source_addr.EndRow, dest_addr.EndRow),
        )
        full_range.fillAuto(uno.Enum("com.sun.star.sheet.FillDirection", direction), source_count)

    def _resolve_number_format_key(self, doc: Any, format_string: str) -> int:
        formats = doc.getNumberFormats()
        locale = uno.createUnoStruct("com.sun.star.lang.Locale")
        key = formats.queryKey(format_string, locale, False)
        if key == -1:
            key = formats.addNew(format_string, locale)
        return key

    def set_range_format(self, doc: Any, range: str, properties: Dict[str, Any], sheet: Optional[str] = None) -> List[str]:
        self._require_calc(doc, "set_range_format")
        range_obj = self._resolve_sheet(doc, sheet).getCellRangeByName(range)
        applied = []
        for key, val in properties.items():
            try:
                if key == "NumberFormat" and isinstance(val, str):
                    range_obj.setPropertyValue("NumberFormat", self._resolve_number_format_key(doc, val))
                else:
                    range_obj.setPropertyValue(key, val)
                applied.append(key)
            except Exception:
                continue
        return applied

    _RANGE_FORMAT_PROPERTIES = (
        "CellBackColor", "CharColor", "CharWeight", "CharPosture", "CharHeight",
        "HoriJustify", "VertJustify", "IsTextWrapped", "NumberFormat", "IsCellProtected",
    )

    def get_range_format(self, doc: Any, range: str, sheet: Optional[str] = None) -> Dict[str, Any]:
        self._require_calc(doc, "get_range_format")
        range_obj = self._resolve_sheet(doc, sheet).getCellRangeByName(range)
        result: Dict[str, Any] = {}
        for prop_name in self._RANGE_FORMAT_PROPERTIES:
            try:
                value = self._uno_value_to_plain(range_obj.getPropertyValue(prop_name))
                if self._is_json_safe(value):
                    result[prop_name] = value
            except Exception:
                continue
        return result

    def merge_cells(self, doc: Any, range: str, sheet: Optional[str] = None, center: bool = False) -> None:
        self._require_calc(doc, "merge_cells")
        range_obj = self._resolve_sheet(doc, sheet).getCellRangeByName(range)
        range_obj.merge(True)
        if center:
            range_obj.HoriJustify = uno.Enum("com.sun.star.table.CellHoriJustify", "CENTER")
            range_obj.VertJustify = uno.Enum("com.sun.star.table.CellVertJustify", "CENTER")

    def unmerge_cells(self, doc: Any, range: str, sheet: Optional[str] = None) -> None:
        self._require_calc(doc, "unmerge_cells")
        self._resolve_sheet(doc, sheet).getCellRangeByName(range).merge(False)

    _LENGTH_UNIT_TO_MM100 = {"mm100": 1, "mm": 100, "cm": 1000, "in": 2540, "pt": 35.28}

    def set_row_height(self, doc: Any, rows: List[int], sheet: Optional[str] = None,
                        height: Optional[float] = None, unit: Optional[str] = None, optimal: bool = False) -> None:
        self._require_calc(doc, "set_row_height")
        row_container = self._resolve_sheet(doc, sheet).getRows()
        factor = self._LENGTH_UNIT_TO_MM100.get((unit or "mm100").lower(), 1)
        for idx in rows:
            row_obj = row_container.getByIndex(idx)
            if optimal:
                row_obj.OptimalHeight = True
            elif height is not None:
                row_obj.Height = int(height * factor)

    def set_column_width(self, doc: Any, columns: List[int], sheet: Optional[str] = None,
                          width: Optional[float] = None, unit: Optional[str] = None, optimal: bool = False) -> None:
        self._require_calc(doc, "set_column_width")
        col_container = self._resolve_sheet(doc, sheet).getColumns()
        factor = self._LENGTH_UNIT_TO_MM100.get((unit or "mm100").lower(), 1)
        for idx in columns:
            col_obj = col_container.getByIndex(idx)
            if optimal:
                col_obj.OptimalWidth = True
            elif width is not None:
                col_obj.Width = int(width * factor)

    def hide_rows(self, doc: Any, rows: List[int], sheet: Optional[str] = None) -> None:
        self._require_calc(doc, "hide_rows")
        row_container = self._resolve_sheet(doc, sheet).getRows()
        for idx in rows:
            row_container.getByIndex(idx).IsVisible = False

    def show_rows(self, doc: Any, rows: List[int], sheet: Optional[str] = None) -> None:
        self._require_calc(doc, "show_rows")
        row_container = self._resolve_sheet(doc, sheet).getRows()
        for idx in rows:
            row_container.getByIndex(idx).IsVisible = True

    def hide_columns(self, doc: Any, columns: List[int], sheet: Optional[str] = None) -> None:
        self._require_calc(doc, "hide_columns")
        col_container = self._resolve_sheet(doc, sheet).getColumns()
        for idx in columns:
            col_container.getByIndex(idx).IsVisible = False

    def show_columns(self, doc: Any, columns: List[int], sheet: Optional[str] = None) -> None:
        self._require_calc(doc, "show_columns")
        col_container = self._resolve_sheet(doc, sheet).getColumns()
        for idx in columns:
            col_container.getByIndex(idx).IsVisible = True

    def freeze_panes(self, doc: Any, cell: str, sheet: Optional[str] = None) -> None:
        """Live-verified this only takes effect with a real, visible
        controller/window -- same caveat undo_view_selection.py's
        Zoom-property work already documented for view-related state.
        This server's documents are opened with Hidden=False in normal
        operation, so this isn't a practical limitation, just a scope
        note for headless-only testing setups."""
        self._require_calc(doc, "freeze_panes")
        sheet_obj = self._resolve_sheet(doc, sheet)
        addr = sheet_obj.getCellRangeByName(cell).RangeAddress
        controller = doc.getCurrentController()
        controller.setActiveSheet(sheet_obj)
        controller.freezeAtPosition(addr.StartColumn, addr.StartRow)

    def unfreeze_panes(self, doc: Any, sheet: Optional[str] = None) -> None:
        self._require_calc(doc, "unfreeze_panes")
        controller = doc.getCurrentController()
        if sheet is not None:
            controller.setActiveSheet(self._resolve_sheet(doc, sheet))
        controller.freezeAtPosition(0, 0)

    def recalculate(self, doc: Any, hard: bool = False) -> None:
        self._require_calc(doc, "recalculate")
        if hard:
            doc.calculateAll()
        else:
            doc.calculate()

    def evaluate_formula(self, doc: Any, formula: str, sheet: Optional[str] = None) -> Dict[str, Any]:
        """Evaluate in workbook context without permanently writing: use
        the target sheet's own last cell (Calc's actual maximum extent,
        AMJ1048576) as scratch space -- so relative references in
        `formula` (e.g. "=A1+B2") resolve against the intended sheet, not
        some other sheet or workbook, while being about as unlikely to
        collide with real data as any single cell can be. Original
        content is saved and restored in a finally block regardless."""
        self._require_calc(doc, "evaluate_formula")
        sheet_obj = self._resolve_sheet(doc, sheet)
        scratch = sheet_obj.getCellByPosition(16383, 1048575)
        original_formula = scratch.getFormula()
        try:
            scratch.setFormula(formula)
            return {
                "formula": formula, "value": scratch.getValue(),
                "display": scratch.getString(), "error": scratch.getError(),
            }
        finally:
            scratch.setFormula(original_formula)

    def _range_address_to_a1(self, doc: Any, addr: Any) -> str:
        sheet_name = doc.getSheets().getByIndex(addr.Sheet).Name
        start = self._column_row_to_a1(addr.StartColumn, addr.StartRow)
        end = self._column_row_to_a1(addr.EndColumn, addr.EndRow)
        return f"{sheet_name}.{start}" if start == end else f"{sheet_name}.{start}:{end}"

    def get_formula_dependencies(self, doc: Any, range: str, sheet: Optional[str] = None,
                                  direction: str = "both") -> Dict[str, Any]:
        self._require_calc(doc, "get_formula_dependencies")
        range_obj = self._resolve_sheet(doc, sheet).getCellRangeByName(range)
        result: Dict[str, Any] = {"range": range}
        if direction in ("precedents", "both"):
            precedents = range_obj.queryPrecedents(False)
            result["precedents"] = [self._range_address_to_a1(doc, a) for a in precedents.RangeAddresses]
        if direction in ("dependents", "both"):
            dependents = range_obj.queryDependents(False)
            result["dependents"] = [self._range_address_to_a1(doc, a) for a in dependents.RangeAddresses]
        return result

    def get_formula_errors(self, doc: Any, sheet: Optional[str] = None, range: Optional[str] = None) -> List[Dict[str, Any]]:
        self._require_calc(doc, "get_formula_errors")
        sheet_obj = self._resolve_sheet(doc, sheet)
        if range is not None:
            addr = sheet_obj.getCellRangeByName(range).RangeAddress
        else:
            # Live-verified gotoEndOfUsedArea(False) alone on a fresh
            # cursor (starting at A1) collapses to a single cell -- the
            # end cell -- rather than expanding to cover A1-to-end;
            # gotoStartOfUsedArea() first, then gotoEndOfUsedArea(True)
            # (True = extend the existing selection) on the same cursor
            # is what actually spans the whole used area. Same fix
            # get_used_range() already applied via two separate cursors;
            # this method missed it originally.
            cursor = sheet_obj.createCursor()
            cursor.gotoStartOfUsedArea(False)
            cursor.gotoEndOfUsedArea(True)
            addr = cursor.RangeAddress
        # NOTE: `range` is shadowed by this method's own parameter --
        # builtins.range(...) here is deliberate, not a typo.
        errors = []
        for r in builtins.range(addr.StartRow, addr.EndRow + 1):
            for c in builtins.range(addr.StartColumn, addr.EndColumn + 1):
                cell = sheet_obj.getCellByPosition(c, r)
                err = cell.getError()
                if err != 0:
                    errors.append({"cell": self._column_row_to_a1(c, r), "error_code": err, "display": cell.getString()})
        return errors
