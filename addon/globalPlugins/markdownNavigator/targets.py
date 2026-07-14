# -*- coding: UTF-8 -*-
# Markdown Navigator for NVDA - Markdown target indexing
# Copyright (C) 2026 Cary-rowen <manchen_0528@outlook.com>
# This file is covered by the GNU General Public License.

"""Parse actionable Markdown targets without depending on NVDA.

The add-on operates in editable source text rather than rendered HTML.  This
module builds a lightweight index of the source constructs that have a useful
activation behavior: links, images, autolinks, references, headings, and
footnotes.  Keeping the parser independent from NVDA also makes its behavior
straightforward to test.
"""

from __future__ import annotations

import bisect
import html
import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import unquote, urlsplit


class TargetKind(StrEnum):
	INLINE_LINK = "inlineLink"
	REFERENCE_LINK = "referenceLink"
	AUTOLINK = "autolink"
	EMAIL = "email"
	INLINE_IMAGE = "inlineImage"
	REFERENCE_IMAGE = "referenceImage"
	FOOTNOTE_REFERENCE = "footnoteReference"
	FOOTNOTE_DEFINITION = "footnoteDefinition"


LINK_TARGET_KINDS = frozenset(
	{
		TargetKind.INLINE_LINK,
		TargetKind.REFERENCE_LINK,
		TargetKind.AUTOLINK,
		TargetKind.EMAIL,
	},
)
IMAGE_TARGET_KINDS = frozenset(
	{
		TargetKind.INLINE_IMAGE,
		TargetKind.REFERENCE_IMAGE,
	},
)
FOOTNOTE_TARGET_KINDS = frozenset(
	{
		TargetKind.FOOTNOTE_REFERENCE,
		TargetKind.FOOTNOTE_DEFINITION,
	},
)
ACTIONABLE_TARGET_KINDS = LINK_TARGET_KINDS | IMAGE_TARGET_KINDS | FOOTNOTE_TARGET_KINDS


@dataclass(frozen=True, slots=True)
class MarkdownTarget:
	kind: TargetKind
	start: int
	end: int
	source: str
	label: str
	destination: str | None = None
	referenceLabel: str | None = None
	lineIndex: int = 0


@dataclass(frozen=True, slots=True)
class ReferenceDefinition:
	label: str
	destination: str
	start: int
	end: int
	lineIndex: int


@dataclass(frozen=True, slots=True)
class Heading:
	text: str
	slug: str
	start: int
	end: int
	lineIndex: int


_FENCE_RE = re.compile(r"^[ ]{0,3}(`{3,}|~{3,})(.*)$")
_REFERENCE_DEFINITION_RE = re.compile(
	r"^[ ]{0,3}\[((?:\\[^\r\n]|[^\]\\\r\n]){1,999})\]:[ \t]*(.*)$",
)
_FOOTNOTE_DEFINITION_RE = re.compile(
	r"^[ ]{0,3}\[\^((?:\\[^\r\n]|[^\]\\\r\n])+?)\]:[ \t]*(.*)$",
)
_ATX_HEADING_RE = re.compile(
	r"^[ ]{0,3}(#{1,6})(?:[ \t]+|$)(.*?)(?:[ \t]+#+[ \t]*)?$",
)
_SETEXT_UNDERLINE_RE = re.compile(r"^[ ]{0,3}(?:=+|-+)[ \t]*$")
_URI_AUTOLINK_RE = re.compile(r"[A-Za-z][A-Za-z0-9+.-]{1,31}:[^\x00-\x20<>]*")
_EMAIL_RE = re.compile(
	r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
	r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
	r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+",
)
_BARE_URL_RE = re.compile(r"(?i)(?:https?://|www\.)[^\s<>]+")
_MARKDOWN_BACKSLASH_ESCAPE_RE = re.compile(r"\\([!\"#$%&'()*+,\-./:;<=>?@\[\\\]^_`{|}~])")
_BARE_AUTOLINK_LEFT_BOUNDARY = frozenset("*_~(")
_BARE_URL_TRAILING_PUNCTUATION = frozenset("?!.,:*_~")


def _isEscaped(text: str, offset: int) -> bool:
	backslashes = 0
	offset -= 1
	while offset >= 0 and text[offset] == "\\":
		backslashes += 1
		offset -= 1
	return backslashes % 2 == 1


def _decodeMarkdownText(text: str) -> str:
	return html.unescape(_MARKDOWN_BACKSLASH_ESCAPE_RE.sub(r"\1", text))


def normalizeReferenceLabel(label: str) -> str:
	"""Apply CommonMark-style case and whitespace normalization to a label."""
	return " ".join(_decodeMarkdownText(label).split()).casefold()


def _skipCodeSpan(text: str, offset: int, end: int) -> int:
	runEnd = offset
	while runEnd < end and text[runEnd] == "`":
		runEnd += 1
	marker = text[offset:runEnd]
	closing = text.find(marker, runEnd, end)
	return closing + len(marker) if closing >= 0 else runEnd


def _findClosingBracket(text: str, openOffset: int, end: int) -> int | None:
	depth = 0
	offset = openOffset
	while offset < end:
		character = text[offset]
		if character == "\\":
			offset += 2
			continue
		if character == "`":
			offset = _skipCodeSpan(text, offset, end)
			continue
		if character == "[":
			depth += 1
		elif character == "]":
			depth -= 1
			if depth == 0:
				return offset
		offset += 1
	return None


def _parseDestination(text: str, offset: int, end: int) -> tuple[str, int] | None:
	if offset >= end:
		return None

	if text[offset] == "<":
		closing = offset + 1
		while closing < end:
			if text[closing] in "\r\n" or text[closing] == "<":
				return None
			if text[closing] == ">" and not _isEscaped(text, closing):
				destination = _decodeMarkdownText(text[offset + 1 : closing])
				return destination, closing + 1
			closing += 1
		return None

	start = offset
	parenthesesDepth = 0
	while offset < end:
		character = text[offset]
		if character == "\\" and offset + 1 < end:
			offset += 2
			continue
		if character in " \t\r\n" and parenthesesDepth == 0:
			break
		if character == "(":
			parenthesesDepth += 1
			if parenthesesDepth > 32:
				return None
		elif character == ")":
			if parenthesesDepth == 0:
				break
			parenthesesDepth -= 1
		offset += 1
	if offset == start or parenthesesDepth != 0:
		return None
	return _decodeMarkdownText(text[start:offset]), offset


def _skipWhitespace(text: str, offset: int, end: int) -> int:
	while offset < end and text[offset] in " \t":
		offset += 1
	return offset


def _parseTitle(text: str, offset: int, end: int) -> int | None:
	if offset >= end or text[offset] not in "\"'(":
		return None
	opening = text[offset]
	closingCharacter = ")" if opening == "(" else opening
	offset += 1
	while offset < end:
		if text[offset] == "\\" and offset + 1 < end:
			offset += 2
			continue
		if text[offset] == closingCharacter:
			return offset + 1
		if text[offset] in "\r\n":
			return None
		offset += 1
	return None


def _parseInlineDestination(text: str, openParen: int, end: int) -> tuple[str, int] | None:
	offset = _skipWhitespace(text, openParen + 1, end)
	if offset < end and text[offset] == ")":
		return "", offset + 1

	parsed = _parseDestination(text, offset, end)
	if parsed is None:
		return None
	destination, offset = parsed

	whitespaceStart = offset
	offset = _skipWhitespace(text, offset, end)
	if offset < end and text[offset] != ")":
		if offset == whitespaceStart:
			return None
		titleEnd = _parseTitle(text, offset, end)
		if titleEnd is None:
			return None
		offset = _skipWhitespace(text, titleEnd, end)
	if offset >= end or text[offset] != ")":
		return None
	return destination, offset + 1


def _parseDefinitionDestination(text: str) -> tuple[str, int] | None:
	offset = _skipWhitespace(text, 0, len(text))
	if offset >= len(text):
		return None
	parsed = _parseDestination(text, offset, len(text))
	if parsed is None:
		return None
	destination, destinationEnd = parsed
	offset = _skipWhitespace(text, destinationEnd, len(text))
	if offset < len(text):
		if offset == destinationEnd:
			return None
		titleEnd = _parseTitle(text, offset, len(text))
		if titleEnd is None or _skipWhitespace(text, titleEnd, len(text)) != len(text):
			return None
	return destination, destinationEnd


def _plainHeadingText(text: str) -> str:
	text = re.sub(r"!\[([^\]]*)\](?:\([^)]*\)|\[[^\]]*\])", r"\1", text)
	text = re.sub(r"\[([^\]]*)\](?:\([^)]*\)|\[[^\]]*\])", r"\1", text)
	text = re.sub(r"`+([^`]*)`+", r"\1", text)
	text = re.sub(r"<[^>]+>", "", text)
	text = text.replace("*", "").replace("_", "").replace("~", "")
	return " ".join(_decodeMarkdownText(text).strip().split())


def githubHeadingSlug(text: str) -> str:
	"""Generate a GitHub-style fragment from visible heading text."""
	plainText = _plainHeadingText(text).lower().strip()
	result: list[str] = []
	for character in plainText:
		if character == " ":
			result.append("-")
		elif character.isspace():
			continue
		elif character in "-_":
			result.append(character)
		elif unicodedata.category(character).startswith("P"):
			continue
		else:
			result.append(character)
	return "".join(result)


def _hasBareAutolinkBoundary(text: str, offset: int, segmentStart: int) -> bool:
	if offset <= segmentStart:
		return True
	previous = text[offset - 1]
	return previous.isspace() or previous in _BARE_AUTOLINK_LEFT_BOUNDARY


def _trimBareUrl(text: str) -> str:
	while text and text[-1] in _BARE_URL_TRAILING_PUNCTUATION:
		text = text[:-1]
	while text.endswith(")") and text.count(")") > text.count("("):
		text = text[:-1]
	return text


def _isValidBareUrl(text: str) -> bool:
	url = f"http://{text}" if text.lower().startswith("www.") else text
	parsed = urlsplit(url)
	if parsed.scheme.casefold() not in ("http", "https") or not parsed.hostname:
		return False
	if text.lower().startswith("www.") and "." not in parsed.hostname[4:]:
		return False
	return True


class MarkdownDocumentIndex:
	"""Index actionable elements and destinations in a Markdown document."""

	def __init__(self, text: str) -> None:
		self.text = text
		self.lines = text.splitlines(keepends=True)
		if not self.lines:
			self.lines = [""]
		elif text.endswith(("\n", "\r")):
			self.lines.append("")

		self.lineStarts: list[int] = []
		offset = 0
		for line in self.lines:
			self.lineStarts.append(offset)
			offset += len(line)

		self.referenceDefinitions: dict[str, ReferenceDefinition] = {}
		self.footnoteDefinitions: dict[str, MarkdownTarget] = {}
		self.headings: list[Heading] = []
		self.targets: list[MarkdownTarget] = []
		self._excludedLines: set[int] = set()
		self._referenceDefinitionLines: set[int] = set()
		self._footnoteContentStarts: dict[int, int] = {}

		self._collectBlockMetadata()
		self._collectHeadings()
		self._collectInlineTargets()
		self.targets.sort(key=lambda target: (target.start, target.end, target.kind))

	@staticmethod
	def _lineContent(line: str) -> str:
		return line.rstrip("\r\n")

	def _collectBlockMetadata(self) -> None:
		fenceCharacter: str | None = None
		fenceLength = 0

		for lineIndex, rawLine in enumerate(self.lines):
			line = self._lineContent(rawLine)
			if lineIndex in self._referenceDefinitionLines:
				continue
			fenceMatch = _FENCE_RE.match(line)
			if fenceCharacter is not None:
				self._excludedLines.add(lineIndex)
				if fenceMatch:
					marker = fenceMatch.group(1)
					if (
						marker[0] == fenceCharacter
						and len(marker) >= fenceLength
						and not fenceMatch.group(2).strip()
					):
						fenceCharacter = None
						fenceLength = 0
				continue

			if fenceMatch:
				marker = fenceMatch.group(1)
				fenceCharacter = marker[0]
				fenceLength = len(marker)
				self._excludedLines.add(lineIndex)
				continue

			footnoteMatch = _FOOTNOTE_DEFINITION_RE.match(line)
			if footnoteMatch:
				label = normalizeReferenceLabel(footnoteMatch.group(1))
				markerEnd = footnoteMatch.start(2)
				start = self.lineStarts[lineIndex] + footnoteMatch.start()
				end = self.lineStarts[lineIndex] + markerEnd
				target = MarkdownTarget(
					kind=TargetKind.FOOTNOTE_DEFINITION,
					start=start,
					end=end,
					source=line[footnoteMatch.start() : markerEnd],
					label=_decodeMarkdownText(footnoteMatch.group(1)),
					referenceLabel=label,
					lineIndex=lineIndex,
				)
				self.footnoteDefinitions.setdefault(label, target)
				self.targets.append(target)
				self._footnoteContentStarts[lineIndex] = markerEnd
				continue

			referenceMatch = _REFERENCE_DEFINITION_RE.match(line)
			if not referenceMatch:
				continue
			destinationText = referenceMatch.group(2)
			destinationLineIndex = lineIndex
			if not destinationText.strip() and lineIndex + 1 < len(self.lines):
				destinationLineIndex = lineIndex + 1
				destinationText = self._lineContent(self.lines[destinationLineIndex]).lstrip(" \t")
			parsed = _parseDefinitionDestination(destinationText)
			if parsed is None:
				continue
			destination, destinationEnd = parsed
			label = normalizeReferenceLabel(referenceMatch.group(1))
			start = self.lineStarts[lineIndex] + referenceMatch.start()
			if destinationLineIndex == lineIndex:
				end = self.lineStarts[lineIndex] + referenceMatch.start(2) + destinationEnd
			else:
				leadingWhitespace = len(self._lineContent(self.lines[destinationLineIndex])) - len(
					destinationText,
				)
				end = self.lineStarts[destinationLineIndex] + leadingWhitespace + destinationEnd
				self._referenceDefinitionLines.add(destinationLineIndex)
			self.referenceDefinitions.setdefault(
				label,
				ReferenceDefinition(
					label=label,
					destination=destination,
					start=start,
					end=end,
					lineIndex=lineIndex,
				),
			)
			self._referenceDefinitionLines.add(lineIndex)

	def _collectHeadings(self) -> None:
		slugCounts: dict[str, int] = {}
		setextUnderlineLines: set[int] = set()

		for lineIndex, rawLine in enumerate(self.lines):
			if lineIndex in self._excludedLines or lineIndex in self._referenceDefinitionLines:
				continue
			line = self._lineContent(rawLine)
			match = _ATX_HEADING_RE.match(line)
			if match:
				self._appendHeading(lineIndex, match.group(2), slugCounts)
				continue

			if lineIndex + 1 >= len(self.lines):
				continue
			nextLine = self._lineContent(self.lines[lineIndex + 1])
			if (
				line.strip()
				and lineIndex + 1 not in self._excludedLines
				and _SETEXT_UNDERLINE_RE.match(nextLine)
				and lineIndex not in self._referenceDefinitionLines
			):
				self._appendHeading(lineIndex, line.strip(), slugCounts)
				setextUnderlineLines.add(lineIndex + 1)

		self._excludedLines.update(setextUnderlineLines)

	def _appendHeading(self, lineIndex: int, headingSource: str, slugCounts: dict[str, int]) -> None:
		visibleText = _plainHeadingText(headingSource)
		baseSlug = githubHeadingSlug(headingSource)
		duplicateIndex = slugCounts.get(baseSlug, 0)
		slugCounts[baseSlug] = duplicateIndex + 1
		slug = baseSlug if duplicateIndex == 0 else f"{baseSlug}-{duplicateIndex}"
		line = self._lineContent(self.lines[lineIndex])
		self.headings.append(
			Heading(
				text=visibleText,
				slug=slug,
				start=self.lineStarts[lineIndex],
				end=self.lineStarts[lineIndex] + len(line),
				lineIndex=lineIndex,
			),
		)

	def _collectInlineTargets(self) -> None:
		for lineIndex, rawLine in enumerate(self.lines):
			if lineIndex in self._excludedLines or lineIndex in self._referenceDefinitionLines:
				continue
			line = self._lineContent(rawLine)
			segmentStart = self._footnoteContentStarts.get(lineIndex, 0)
			self._scanSegment(
				line=line,
				lineIndex=lineIndex,
				segmentStart=segmentStart,
				segmentEnd=len(line),
				allowLinks=True,
			)

	def _scanSegment(
		self,
		line: str,
		lineIndex: int,
		segmentStart: int,
		segmentEnd: int,
		allowLinks: bool,
	) -> None:
		offset = segmentStart
		lineStart = self.lineStarts[lineIndex]
		while offset < segmentEnd:
			character = line[offset]
			if character == "\\":
				offset += 2
				continue
			if character == "`":
				offset = _skipCodeSpan(line, offset, segmentEnd)
				continue

			if character == "!" and offset + 1 < segmentEnd and line[offset + 1] == "[":
				parsedImage = self._parseBracketTarget(
					line,
					lineIndex,
					offset,
					offset + 1,
					segmentEnd,
					isImage=True,
				)
				if parsedImage is not None:
					image, _, _ = parsedImage
					self.targets.append(image)
					offset = image.end - lineStart
					continue

			if allowLinks and character == "[":
				footnote = self._parseFootnoteReference(line, lineIndex, offset, segmentEnd)
				if footnote is not None:
					self.targets.append(footnote)
					offset = footnote.end - lineStart
					continue

				parsedLink = self._parseBracketTarget(
					line,
					lineIndex,
					offset,
					offset,
					segmentEnd,
					isImage=False,
				)
				if parsedLink is not None:
					link, labelStart, labelEnd = parsedLink
					self.targets.append(link)
					self._scanSegment(
						line,
						lineIndex,
						labelStart,
						labelEnd,
						allowLinks=False,
					)
					offset = link.end - lineStart
					continue

			if allowLinks and character == "<":
				autolink = self._parseAngleAutolink(line, lineIndex, offset, segmentEnd)
				if autolink is not None:
					self.targets.append(autolink)
					offset = autolink.end - lineStart
					continue

			if allowLinks and _hasBareAutolinkBoundary(line, offset, segmentStart):
				bareTarget = self._parseBareAutolink(line, lineIndex, offset, segmentEnd)
				if bareTarget is not None:
					self.targets.append(bareTarget)
					offset = bareTarget.end - lineStart
					continue

			offset += 1

	def _parseBracketTarget(
		self,
		line: str,
		lineIndex: int,
		markerStart: int,
		openBracket: int,
		segmentEnd: int,
		isImage: bool,
	) -> tuple[MarkdownTarget, int, int] | None:
		closingBracket = _findClosingBracket(line, openBracket, segmentEnd)
		if closingBracket is None:
			return None
		labelSource = line[openBracket + 1 : closingBracket]
		label = _decodeMarkdownText(labelSource)
		afterLabel = closingBracket + 1
		destination: str | None = None
		referenceLabel: str | None = None
		targetEnd = afterLabel
		isReference = False

		if afterLabel < segmentEnd and line[afterLabel] == "(":
			parsedDestination = _parseInlineDestination(line, afterLabel, segmentEnd)
			if parsedDestination is None:
				return None
			destination, targetEnd = parsedDestination
		elif afterLabel < segmentEnd and line[afterLabel] == "[":
			referenceEnd = _findClosingBracket(line, afterLabel, segmentEnd)
			if referenceEnd is None:
				return None
			referenceSource = line[afterLabel + 1 : referenceEnd]
			referenceLabel = normalizeReferenceLabel(referenceSource or labelSource)
			definition = self.referenceDefinitions.get(referenceLabel)
			if definition is None:
				return None
			destination = definition.destination
			targetEnd = referenceEnd + 1
			isReference = True
		else:
			referenceLabel = normalizeReferenceLabel(labelSource)
			definition = self.referenceDefinitions.get(referenceLabel)
			if definition is None:
				return None
			destination = definition.destination
			isReference = True

		kind = (
			TargetKind.REFERENCE_IMAGE
			if isImage and isReference
			else TargetKind.INLINE_IMAGE
			if isImage
			else TargetKind.REFERENCE_LINK
			if isReference
			else TargetKind.INLINE_LINK
		)
		lineStart = self.lineStarts[lineIndex]
		target = MarkdownTarget(
			kind=kind,
			start=lineStart + markerStart,
			end=lineStart + targetEnd,
			source=line[markerStart:targetEnd],
			label=label,
			destination=destination,
			referenceLabel=referenceLabel,
			lineIndex=lineIndex,
		)
		return target, openBracket + 1, closingBracket

	def _parseFootnoteReference(
		self,
		line: str,
		lineIndex: int,
		offset: int,
		segmentEnd: int,
	) -> MarkdownTarget | None:
		if not line.startswith("[^", offset):
			return None
		closing = _findClosingBracket(line, offset, segmentEnd)
		if closing is None:
			return None
		labelSource = line[offset + 2 : closing]
		if not labelSource:
			return None
		lineStart = self.lineStarts[lineIndex]
		return MarkdownTarget(
			kind=TargetKind.FOOTNOTE_REFERENCE,
			start=lineStart + offset,
			end=lineStart + closing + 1,
			source=line[offset : closing + 1],
			label=_decodeMarkdownText(labelSource),
			referenceLabel=normalizeReferenceLabel(labelSource),
			lineIndex=lineIndex,
		)

	def _parseAngleAutolink(
		self,
		line: str,
		lineIndex: int,
		offset: int,
		segmentEnd: int,
	) -> MarkdownTarget | None:
		closing = line.find(">", offset + 1, segmentEnd)
		if closing < 0:
			return None
		content = line[offset + 1 : closing]
		if not content or any(character.isspace() or ord(character) < 0x20 for character in content):
			return None

		kind: TargetKind
		destination: str
		if _URI_AUTOLINK_RE.fullmatch(content):
			kind = TargetKind.AUTOLINK
			destination = html.unescape(content)
		elif _EMAIL_RE.fullmatch(content):
			kind = TargetKind.EMAIL
			destination = f"mailto:{content}"
		else:
			return None

		lineStart = self.lineStarts[lineIndex]
		return MarkdownTarget(
			kind=kind,
			start=lineStart + offset,
			end=lineStart + closing + 1,
			source=line[offset : closing + 1],
			label=content,
			destination=destination,
			lineIndex=lineIndex,
		)

	def _parseBareAutolink(
		self,
		line: str,
		lineIndex: int,
		offset: int,
		segmentEnd: int,
	) -> MarkdownTarget | None:
		urlMatch = _BARE_URL_RE.match(line, offset, segmentEnd)
		if urlMatch:
			source = _trimBareUrl(urlMatch.group())
			if source and _isValidBareUrl(source):
				destination = f"http://{source}" if source.lower().startswith("www.") else source
				lineStart = self.lineStarts[lineIndex]
				return MarkdownTarget(
					kind=TargetKind.AUTOLINK,
					start=lineStart + offset,
					end=lineStart + offset + len(source),
					source=source,
					label=source,
					destination=destination,
					lineIndex=lineIndex,
				)

		emailMatch = _EMAIL_RE.match(line, offset, segmentEnd)
		if emailMatch:
			source = emailMatch.group()
			after = offset + len(source)
			if after < segmentEnd and (line[after].isalnum() or line[after] in "_-"):
				return None
			lineStart = self.lineStarts[lineIndex]
			return MarkdownTarget(
				kind=TargetKind.EMAIL,
				start=lineStart + offset,
				end=lineStart + after,
				source=source,
				label=source,
				destination=f"mailto:{source}",
				lineIndex=lineIndex,
			)
		return None

	def lineIndexAtOffset(self, offset: int) -> int:
		return max(0, bisect.bisect_right(self.lineStarts, offset) - 1)

	def targetsOfKinds(self, kinds: frozenset[TargetKind]) -> list[MarkdownTarget]:
		return [target for target in self.targets if target.kind in kinds]

	def targetAtOffset(self, offset: int) -> MarkdownTarget | None:
		candidates = [
			target
			for target in self.targets
			if target.kind in ACTIONABLE_TARGET_KINDS and target.start <= offset < target.end
		]
		if not candidates:
			return None

		exact = [target for target in candidates if target.start == offset]
		if exact:
			return min(exact, key=lambda target: target.end - target.start)

		# Inside a linked image, the outer link is the rendered activation target.
		return min(
			candidates,
			key=lambda target: (
				0 if target.kind in LINK_TARGET_KINDS else 1,
				-(target.end - target.start),
			),
		)

	def findHeading(self, fragment: str) -> Heading | None:
		decoded = html.unescape(unquote(fragment.lstrip("#"))).strip()
		if not decoded:
			return None
		folded = decoded.casefold()
		for heading in self.headings:
			if heading.slug.casefold() == folded:
				return heading
		normalizedText = " ".join(decoded.split()).casefold()
		for heading in self.headings:
			if " ".join(heading.text.split()).casefold() == normalizedText:
				return heading
		return None

	def footnoteDefinition(self, label: str) -> MarkdownTarget | None:
		return self.footnoteDefinitions.get(normalizeReferenceLabel(label))

	def footnoteReferences(self, label: str) -> list[MarkdownTarget]:
		normalized = normalizeReferenceLabel(label)
		return [
			target
			for target in self.targets
			if target.kind == TargetKind.FOOTNOTE_REFERENCE and target.referenceLabel == normalized
		]
