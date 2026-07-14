import builtins
import _ctypes
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest import mock


_PACKAGE_DIRECTORY = Path(__file__).parents[1] / "addon" / "globalPlugins" / "markdownNavigator"
_PACKAGE_NAME = "markdownNavigator_test_runtime"
_messages = []
_spoken = []
_moves = []


def _addModule(name, **attributes):
	module = types.ModuleType(name)
	module.__dict__.update(attributes)
	sys.modules[name] = module
	return module


def _loadModule(name, path):
	spec = importlib.util.spec_from_file_location(name, path)
	if spec is None or spec.loader is None:
		raise RuntimeError(f"Could not load {path}")
	module = importlib.util.module_from_spec(spec)
	sys.modules[name] = module
	spec.loader.exec_module(module)
	return module


builtins._ = lambda message: message
_addModule("addonHandler", initTranslation=lambda: None)
_addModule("controlTypes", OutputReason=types.SimpleNamespace(CARET="caret"))
_addModule(
	"textInfos",
	TextInfo=object,
	POSITION_CARET="caret",
	UNIT_CHARACTER="character",
	UNIT_LINE="line",
)
_addModule("ui", message=_messages.append)
_addModule(
	"config",
	conf={"virtualBuffers": {"trapNonCommandGestures": True, "passThroughAudioIndication": False}},
)
_addModule("nvwave", playWaveFile=lambda path: None)
_addModule("globalVars", appDir=".")
_addModule("winsound", MessageBeep=lambda: None)
_addModule("winUser", GA_ROOT=2, getWindowText=lambda handle: "", getAncestor=lambda handle, flag: handle)
_addModule(
	"speech",
	speak=lambda sequence: _spoken.append(("speak", sequence)),
	speakTextInfo=lambda *args, **kwargs: _spoken.append(("textInfo", args, kwargs)),
)
_addModule(
	"logHandler",
	log=types.SimpleNamespace(
		debugWarning=lambda *args, **kwargs: None,
		warning=lambda *args, **kwargs: None,
		debug=lambda *args, **kwargs: None,
		error=lambda *args, **kwargs: None,
	),
)


class _ScriptableObject:
	def getScript(self, gesture):
		return None


_addModule("baseObject", ScriptableObject=_ScriptableObject)


def _script(**metadata):
	def decorate(function):
		function.scriptMetadata = metadata
		return function

	return decorate


_addModule("scriptHandler", script=_script)
_addModule("NVDAObjects")
_addModule("NVDAObjects.IAccessible", IA2TextTextInfo=type("IA2TextTextInfo", (), {}))


if not hasattr(_ctypes, "COMError"):
	_ctypes.COMError = type("COMError", (Exception,), {})

package = _addModule(_PACKAGE_NAME)
package.__path__ = [str(_PACKAGE_DIRECTORY)]
patterns = _loadModule(f"{_PACKAGE_NAME}.patterns", _PACKAGE_DIRECTORY / "patterns.py")
resources = _loadModule(f"{_PACKAGE_NAME}.resources", _PACKAGE_DIRECTORY / "resources.py")
targets = _loadModule(f"{_PACKAGE_NAME}.targets", _PACKAGE_DIRECTORY / "targets.py")


class _FakeTextInfo:
	def __init__(self, lineIndex):
		self.lineIndex = lineIndex


class _RuntimeContext:
	text = ""
	caretOffset = 0


class _FakeDocumentManager:
	def __init__(self, obj):
		self.documentText = _RuntimeContext.text
		self.initialCaretOffset = _RuntimeContext.caretOffset
		self._index = targets.MarkdownDocumentIndex(self.documentText)

	def __enter__(self):
		return self

	def __exit__(self, *args):
		return None

	def getText(self, lineIndex=None):
		if lineIndex is None:
			lineIndex = self._index.lineIndexAtOffset(self.initialCaretOffset)
		return self._index.lines[lineIndex]

	def getLineOffset(self, lineIndex=None):
		if lineIndex is None:
			lineIndex = self._index.lineIndexAtOffset(self.initialCaretOffset)
		return self._index.lineStarts[lineIndex]

	def getTextInfo(self, lineIndex=None):
		if lineIndex is None:
			lineIndex = self._index.lineIndexAtOffset(self.initialCaretOffset)
		return _FakeTextInfo(lineIndex)

	def updateCaret(self, lineIndex=None):
		if lineIndex is None:
			lineIndex = self._index.lineIndexAtOffset(self.initialCaretOffset)
		_moves.append(("updateCaret", lineIndex))
		return _FakeTextInfo(lineIndex)


_addModule(f"{_PACKAGE_NAME}.document", FastDocumentManager=_FakeDocumentManager)
navigator = _loadModule(f"{_PACKAGE_NAME}.navigator", _PACKAGE_DIRECTORY / "navigator.py")
navigator.FastDocumentManager = _FakeDocumentManager


class _FakeGesture:
	def __init__(self):
		self.sendCount = 0

	def send(self):
		self.sendCount += 1


class MarkdownNavigatorBehaviorTests(unittest.TestCase):
	def setUp(self):
		_messages.clear()
		_spoken.clear()
		_moves.clear()
		self.overlay = navigator.MarkdownEditorOverlay()
		self.overlay.appModule = types.SimpleNamespace(appName="notepad")
		self.overlay.markdownBrowseMode = True
		self.overlay._getDocumentLocation = lambda: None
		self.overlay._moveToCharacterRange = (
			lambda textInfo, text, charOffset, isWeb, charLength=0: _moves.append(
				("range", textInfo.lineIndex, charOffset, charLength),
			)
		)

	def setDocument(self, text, caretOffset):
		_RuntimeContext.text = text
		_RuntimeContext.caretOffset = caretOffset

	def test_enter_opens_inline_web_link(self):
		text = "See [OpenAI](https://openai.com)."
		self.setDocument(text, text.index("[OpenAI]"))
		with mock.patch.object(navigator.webbrowser, "open", return_value=True) as openBrowser:
			self.assertTrue(self.overlay._activateMarkdownTargetAtCaret())
		openBrowser.assert_called_once_with("https://openai.com")

	def test_enter_opens_absolute_image_with_default_file_handler(self):
		text = r"![photo](C:\Photos\photo.png)"
		self.setDocument(text, 0)
		with (
			mock.patch.object(navigator.os.path, "exists", return_value=True),
			mock.patch.object(navigator.os, "startfile", create=True) as startFile,
		):
			self.assertTrue(self.overlay._activateMarkdownTargetAtCaret())
		startFile.assert_called_once_with(r"C:\Photos\photo.png")

	def test_unresolvable_relative_image_is_consumed_and_reported(self):
		text = "![photo](images/photo.png)"
		self.setDocument(text, 0)
		self.assertTrue(self.overlay._activateMarkdownTargetAtCaret())
		self.assertEqual(
			_messages,
			["Cannot resolve the relative target because the document location is unavailable"],
		)

	def test_internal_fragment_moves_to_heading(self):
		text = "[Install](#install)\n\n# Install\n"
		self.setDocument(text, 0)
		self.assertTrue(self.overlay._activateMarkdownTargetAtCaret())
		self.assertIn(("range", 2, 0, 0), _moves)

	def test_footnote_enter_jumps_to_definition_and_back(self):
		text = "Text[^one].\n\n[^one]: Footnote.\n"
		referenceOffset = text.index("[^one]")
		definitionOffset = text.rindex("[^one]")
		self.setDocument(text, referenceOffset)
		self.assertTrue(self.overlay._activateMarkdownTargetAtCaret())
		self.assertIn(("range", 2, 0, len("[^one]: ")), _moves)

		_moves.clear()
		self.setDocument(text, definitionOffset)
		self.assertTrue(self.overlay._activateMarkdownTargetAtCaret())
		self.assertIn(("range", 0, referenceOffset, len("[^one]")), _moves)

	def test_dangerous_local_file_is_blocked(self):
		text = r"[run](C:\Downloads\setup.exe)"
		self.setDocument(text, 0)
		with mock.patch.object(navigator.os.path, "exists", return_value=True):
			self.assertTrue(self.overlay._activateMarkdownTargetAtCaret())
		self.assertEqual(_messages, ["Opening this file type is blocked for safety"])

	def test_non_target_and_disabled_mode_pass_enter_through(self):
		self.setDocument("plain text", 0)
		gesture = _FakeGesture()
		self.overlay.script_activateMarkdownTarget(gesture)
		self.assertEqual(gesture.sendCount, 1)

		self.overlay.markdownBrowseMode = False
		self.setDocument("[link](https://example.com)", 0)
		gesture = _FakeGesture()
		self.overlay.script_activateMarkdownTarget(gesture)
		self.assertEqual(gesture.sendCount, 1)

	def test_navigation_uses_unified_link_image_and_footnote_index(self):
		text = "start [ref][id] ![photo](photo.png) <https://example.com> note[^n]\n[id]: /doc\n[^n]: end"
		self.setDocument(text, 0)
		gesture = _FakeGesture()
		self.overlay.script_nextLink(gesture)
		self.assertEqual(_moves[-1][0], "range")
		self.assertEqual(_moves[-1][2], text.index("[ref]"))

		_moves.clear()
		self.overlay.script_nextImage(gesture)
		self.assertEqual(_moves[-1][2], text.index("![photo]"))

		_moves.clear()
		self.overlay.script_nextFootnote(gesture)
		self.assertEqual(_moves[-1][2], text.index("[^n]"))

	def test_both_enter_keys_are_registered(self):
		metadata = self.overlay.script_activateMarkdownTarget.scriptMetadata
		self.assertEqual(metadata["gestures"], ["kb:enter", "kb:numpadEnter"])


if __name__ == "__main__":
	unittest.main()
