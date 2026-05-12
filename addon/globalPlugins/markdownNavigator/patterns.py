# -*- coding: UTF-8 -*-
# Markdown Navigator for NVDA - Regex Patterns
# Copyright (C) 2026 Cary-rowen <manchen_0528@outlook.com>
# This file is covered by the GNU General Public License.

import re

# Regex Definitions
RE_HEADING = re.compile(r"^\s*#{1,6}\s")
RE_LIST_ITEM = re.compile(r"^\s*([\*\-\+]|\d+\.)\s")
RE_BLOCKQUOTE = re.compile(r"^\s*>\s")
RE_TABLE = re.compile(r"^\s*\|")
RE_CODE_BLOCK = re.compile(r"^\s*`{3,}")
RE_INLINE_CODE = re.compile(r"(?<!`)`[^`\n]+`(?!`)")
# Non-greedy matching for inline elements
# Negative lookbehind (?<!!) ensures we don't match images ![...]
RE_LINK = re.compile(r"(?<!!)\[.+?\]\(.+?\)")
RE_IMAGE = re.compile(r"!\[.+?\]\(.+?\)")
RE_SEPARATOR = re.compile(r"^\s*([-*_])\s*\1\s*\1[\-\*_\s]*$")
RE_CHECKBOX = re.compile(r"^\s*([\*\-\+]|\d+\.)\s*\[[ xX]\]")
RE_BOLD = re.compile(r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1")
RE_ITALIC = re.compile(r"(?<!\*)\*(?=[^\s*])(.+?)(?<=[^\s*])\*(?!\*)|(?<!_)_(?=[^\s_])(.+?)(?<=[^\s_])_(?!_)")
RE_STRIKETHROUGH = re.compile(r"(~~)(?=\S)(.+?)(?<=\S)\1")
RE_FOOTNOTE = re.compile(r"\[\^.+?\](:)?")
RE_LATEX_MATH = re.compile(r"\$\$[\s\S]*?\$\$|(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)")
RE_TABLE_CELL_SEPARATOR = re.compile(r"(?<!\\)\|")


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
