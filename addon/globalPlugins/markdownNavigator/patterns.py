# -*- coding: UTF-8 -*-
# Markdown Navigator for NVDA - Regex Patterns
# Copyright (C) 2026 Cary-rowen <manchen_0528@outlook.com>
# This file is covered by the GNU General Public License.

import html
import re

# Regex Definitions
RE_HEADING = re.compile(r"^\s*#{1,6}\s")
RE_LIST_ITEM = re.compile(r"^\s*([\*\-\+]|\d+\.)\s")
RE_BLOCKQUOTE = re.compile(r"^\s*>\s")
RE_TABLE = re.compile(r"^\s*\|")
RE_CODE_BLOCK = re.compile(r"^\s*`{3,}")
RE_INLINE_CODE = re.compile(r"(?<!`)`[^`\n]+`(?!`)")
# Negative lookbehind (?<!!) ensures we don't match images ![...].
# The destination pattern supports angle brackets, an optional title, escaped
# characters, and a single level of balanced parentheses (commonly found in URLs).
RE_LINK = re.compile(
	r"(?<!!)\[(?:\\[^\r\n]|[^\]\\\r\n])*\]\([ \t]*"
	r"(?P<destination>"
	r"<(?:\\[^\r\n]|[^>\\\r\n])+>"
	r"|"
	r"(?:\\[^\r\n]|[^()\s\\]|\((?:\\[^\r\n]|[^()\\\r\n])*\))+"
	r")"
	r"(?:[ \t]+(?:"
	r"\"(?:\\[^\r\n]|[^\"\\\r\n])*\""
	r"|"
	r"'(?:\\[^\r\n]|[^'\\\r\n])*'"
	r"|"
	r"\((?:\\[^\r\n]|[^)\\\r\n])*\)"
	r"))?"
	r"[ \t]*\)",
)
RE_IMAGE = re.compile(r"!\[.+?\]\(.+?\)")
RE_SEPARATOR = re.compile(r"^\s*([-*_])\s*\1\s*\1[\-\*_\s]*$")
RE_CHECKBOX = re.compile(r"^\s*([\*\-\+]|\d+\.)\s*\[[ xX]\]")
RE_BOLD = re.compile(r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1")
RE_ITALIC = re.compile(r"(?<!\*)\*(?=[^\s*])(.+?)(?<=[^\s*])\*(?!\*)|(?<!_)_(?=[^\s_])(.+?)(?<=[^\s_])_(?!_)")
RE_STRIKETHROUGH = re.compile(r"(~~)(?=\S)(.+?)(?<=\S)\1")
RE_FOOTNOTE = re.compile(r"\[\^.+?\](:)?")
RE_LATEX_MATH = re.compile(r"\$\$[\s\S]*?\$\$|(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)")
RE_TABLE_CELL_SEPARATOR = re.compile(r"(?<!\\)\|")
RE_MARKDOWN_BACKSLASH_ESCAPE = re.compile(r"\\([!\"#$%&'()*+,\-./:;<=>?@\[\\\]^_`{|}~])")


def getLinkDestinationAtOffset(text: str, offset: int) -> str | None:
	"""Return the destination of the Markdown link containing ``offset``.

	The offset is a Python character offset relative to ``text``. Markdown
	backslash escapes and HTML character references in the destination are
	decoded so the result can be handed directly to the default browser.
	"""
	if offset < 0:
		return None

	for match in RE_LINK.finditer(text):
		if match.start() <= offset < match.end():
			destination = match.group("destination").strip()
			if destination.startswith("<") and destination.endswith(">"):
				destination = destination[1:-1]
			destination = RE_MARKDOWN_BACKSLASH_ESCAPE.sub(r"\1", destination)
			return html.unescape(destination)
	return None


def getHeadingRegex(level):
	return re.compile(r"^\s*#{%d}\s" % level)


def parseTableRow(text):
	"""Parse a Markdown table row into cell offset dictionaries."""
	cells = []
	matches = list(RE_TABLE_CELL_SEPARATOR.finditer(text))
	if not matches:
		return []
	for i in range(len(matches) - 1):
		start_pipe = matches[i]
		end_pipe = matches[i + 1]
		cell_start = start_pipe.end()
		cell_end = end_pipe.start()
		cell_text = text[cell_start:cell_end]
		stripped = cell_text.strip()
		content_start = cell_start + cell_text.find(stripped) if stripped else cell_start
		cells.append(
			{
				"start": cell_start,
				"end": cell_end,
				"content_start": content_start,
				"text": stripped,
			},
		)
	return cells
