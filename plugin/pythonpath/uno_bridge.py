"""
LibreOffice MCP Extension - UNO Bridge Module

This module provides a bridge between MCP operations and LibreOffice UNO API,
enabling direct manipulation of LibreOffice documents.
"""

import uno
import unohelper
from com.sun.star.beans import PropertyValue
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
                except:
                    pass
                try:
                    showing = doc.getPropertyValue("ShowChanges")
                except:
                    pass

            # Count pending redlines using XRedlinesSupplier
            if hasattr(doc, 'getRedlines'):
                try:
                    redlines = doc.getRedlines()
                    if redlines:
                        pending_count = redlines.getCount()
                except:
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
                                except:
                                    pass
                except:
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
                                except:
                                    pass
                except:
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
                        except:
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
                except:
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
                except:
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
        except:
            pass
        return False
