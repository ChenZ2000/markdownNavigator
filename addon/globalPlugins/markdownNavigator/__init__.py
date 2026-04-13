# -*- coding: UTF-8 -*-
# Markdown Navigator for NVDA
# Copyright (C) 2026 Cary-rowen <manchen_0528@outlook.com>
# This file is covered by the GNU General Public License.

import globalPluginHandler
import controlTypes
import winUser

from .navigator import MarkdownEditorOverlay

_SUPPORTED_EDITOR_WINDOW_CLASSES = frozenset(
	{
		"Scintilla",
		"RichEditD2DPT",
		"AkelEditW",
	}
)


def _shouldApplyMarkdownOverlay(obj) -> bool:
	"""Return whether Markdown navigation should be added to the control."""
	windowClassName = getattr(obj, "windowClassName", "")
	windowStyle = getattr(obj, "windowStyle", 0)
	states = getattr(obj, "states", set())
	role = getattr(obj, "role", None)
	if role == controlTypes.Role.PASSWORDEDIT or controlTypes.State.PROTECTED in states:
		return False
	if windowClassName in _SUPPORTED_EDITOR_WINDOW_CLASSES:
		return True
	return role == controlTypes.Role.EDITABLETEXT and (
		bool(windowStyle & winUser.ES_MULTILINE) or controlTypes.State.MULTILINE in states
	)


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	"""Inject Markdown navigation overlays into supported editor controls."""

	def chooseNVDAObjectOverlayClasses(self, obj, clsList):
		"""Add the Markdown overlay to controls that can contain Markdown documents."""
		if _shouldApplyMarkdownOverlay(obj):
			clsList.insert(0, MarkdownEditorOverlay)
