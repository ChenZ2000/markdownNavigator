# -*- coding: UTF-8 -*-
# Markdown Navigator for NVDA - destination resolution
# Copyright (C) 2026 Cary-rowen <manchen_0528@outlook.com>
# This file is covered by the GNU General Public License.

"""Resolve Markdown destinations into safe, explicit activation actions."""

from __future__ import annotations

import html
import ntpath
import re
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import unquote, urljoin, urlsplit


class DestinationAction(StrEnum):
	WEB = "web"
	SHELL = "shell"
	LOCAL_FILE = "localFile"
	INTERNAL_FRAGMENT = "internalFragment"
	UNRESOLVED_RELATIVE = "unresolvedRelative"
	UNSUPPORTED = "unsupported"
	EMPTY = "empty"


@dataclass(frozen=True, slots=True)
class ResolvedDestination:
	action: DestinationAction
	value: str
	fragment: str = ""
	scheme: str = ""


_WEB_SCHEMES = frozenset({"http", "https", "ftp"})
_SHELL_SCHEMES = frozenset({"mailto", "tel"})
_DANGEROUS_LOCAL_EXTENSIONS = frozenset(
	{
		".appref-ms",
		".bat",
		".cmd",
		".com",
		".cpl",
		".exe",
		".hta",
		".inf",
		".ins",
		".iso",
		".isp",
		".jar",
		".js",
		".jse",
		".lnk",
		".msc",
		".msi",
		".msp",
		".mst",
		".pif",
		".ps1",
		".ps1xml",
		".ps2",
		".ps2xml",
		".psc1",
		".psc2",
		".psd1",
		".psm1",
		".py",
		".pyw",
		".reg",
		".scr",
		".sct",
		".url",
		".vb",
		".vbe",
		".vbs",
		".ws",
		".wsc",
		".wsf",
		".wsh",
	},
)
_DOCUMENT_PATH_RE = re.compile(
	r"(?i)([A-Z]:[\\/][^<>|\"\r\n]*?\.(?:md|markdown|mdown|mkd|txt))"
	r"(?=$|\s+(?:[-—|]))",
)
_FILE_URI_RE = re.compile(r"(?i)(file://[^\s<>\"]+)")
_WEB_URI_RE = re.compile(r"(?i)(https?://[^\s<>\"]+)")


def _splitFragment(destination: str) -> tuple[str, str]:
	path, separator, fragment = destination.partition("#")
	return path, fragment if separator else ""


def _isDriveAbsolute(path: str) -> bool:
	drive, tail = ntpath.splitdrive(path)
	return bool(drive and tail.startswith(("\\", "/")))


def _isUncPath(path: str) -> bool:
	return path.startswith(("\\\\", "//"))


def _fileUriToWindowsPath(uri: str) -> tuple[str, str] | None:
	parsed = urlsplit(uri)
	if parsed.scheme.casefold() != "file":
		return None
	path = unquote(parsed.path)
	if parsed.netloc and parsed.netloc.casefold() != "localhost":
		path = f"\\\\{parsed.netloc}{path.replace('/', '\\')}"
	else:
		if re.match(r"^/[A-Za-z]:/", path):
			path = path[1:]
		path = path.replace("/", "\\")
	return ntpath.normpath(path), unquote(parsed.fragment)


def _localDocumentPath(documentLocation: str | None) -> str | None:
	if not documentLocation:
		return None
	location = html.unescape(documentLocation.strip().strip("\"'"))
	filePath = _fileUriToWindowsPath(location)
	if filePath is not None:
		return filePath[0]
	path, _ = _splitFragment(unquote(location))
	path = path.replace("/", "\\")
	if _isDriveAbsolute(path) or _isUncPath(path):
		return ntpath.normpath(path)
	return None


def _sameLocalPath(first: str, second: str) -> bool:
	return ntpath.normcase(ntpath.normpath(first)) == ntpath.normcase(ntpath.normpath(second))


def resolveDestination(destination: str, documentLocation: str | None = None) -> ResolvedDestination:
	"""Classify a decoded Markdown destination and resolve relative locations."""
	destination = html.unescape(destination.strip())
	if not destination:
		return ResolvedDestination(DestinationAction.EMPTY, "")
	if destination.startswith("#"):
		return ResolvedDestination(
			DestinationAction.INTERNAL_FRAGMENT,
			unquote(destination[1:]),
			fragment=unquote(destination[1:]),
		)

	# Windows paths must be identified before URI parsing so a drive letter is
	# not mistaken for a URI scheme.
	pathPart, fragment = _splitFragment(unquote(destination))
	windowsPath = pathPart.replace("/", "\\")
	documentPath = _localDocumentPath(documentLocation)
	if _isDriveAbsolute(windowsPath) or _isUncPath(windowsPath):
		localPath = ntpath.normpath(windowsPath)
		if documentPath and fragment and _sameLocalPath(localPath, documentPath):
			return ResolvedDestination(
				DestinationAction.INTERNAL_FRAGMENT,
				fragment,
				fragment=fragment,
			)
		return ResolvedDestination(
			DestinationAction.LOCAL_FILE,
			localPath,
			fragment=fragment,
			scheme="file",
		)

	parsed = urlsplit(destination)
	scheme = parsed.scheme.casefold()
	if scheme in _WEB_SCHEMES:
		return ResolvedDestination(
			DestinationAction.WEB,
			destination,
			fragment=parsed.fragment,
			scheme=scheme,
		)
	if scheme in _SHELL_SCHEMES:
		return ResolvedDestination(DestinationAction.SHELL, destination, scheme=scheme)
	if scheme == "file":
		filePath = _fileUriToWindowsPath(destination)
		if filePath is None:
			return ResolvedDestination(DestinationAction.UNSUPPORTED, destination, scheme=scheme)
		localPath, fileFragment = filePath
		if documentPath and fileFragment and _sameLocalPath(localPath, documentPath):
			return ResolvedDestination(
				DestinationAction.INTERNAL_FRAGMENT,
				fileFragment,
				fragment=fileFragment,
			)
		return ResolvedDestination(
			DestinationAction.LOCAL_FILE,
			localPath,
			fragment=fileFragment,
			scheme=scheme,
		)
	if scheme:
		return ResolvedDestination(DestinationAction.UNSUPPORTED, destination, scheme=scheme)

	if documentLocation:
		baseScheme = urlsplit(documentLocation).scheme.casefold()
		if baseScheme in _WEB_SCHEMES:
			resolvedUrl = urljoin(documentLocation, destination)
			resolvedScheme = urlsplit(resolvedUrl).scheme.casefold()
			return ResolvedDestination(
				DestinationAction.WEB,
				resolvedUrl,
				fragment=urlsplit(resolvedUrl).fragment,
				scheme=resolvedScheme,
			)

	if documentPath is None:
		return ResolvedDestination(DestinationAction.UNRESOLVED_RELATIVE, destination, fragment=fragment)

	if windowsPath.startswith("\\"):
		drive = ntpath.splitdrive(documentPath)[0]
		if not drive:
			return ResolvedDestination(DestinationAction.UNRESOLVED_RELATIVE, destination, fragment=fragment)
		localPath = ntpath.normpath(f"{drive}{windowsPath}")
	else:
		localPath = ntpath.normpath(ntpath.join(ntpath.dirname(documentPath), windowsPath))
	if fragment and _sameLocalPath(localPath, documentPath):
		return ResolvedDestination(
			DestinationAction.INTERNAL_FRAGMENT,
			fragment,
			fragment=fragment,
		)
	return ResolvedDestination(
		DestinationAction.LOCAL_FILE,
		localPath,
		fragment=fragment,
		scheme="file",
	)


def isDangerousLocalPath(path: str) -> bool:
	drive, tail = ntpath.splitdrive(path)
	if ":" in tail:
		return True
	normalizedPath = f"{drive}{tail.rstrip(' .')}"
	return ntpath.splitext(normalizedPath)[1].casefold() in _DANGEROUS_LOCAL_EXTENSIONS


def findDocumentLocation(candidates: list[str]) -> str | None:
	"""Find an explicit local path or web/file URL in accessible metadata."""
	for candidate in candidates:
		if not isinstance(candidate, str):
			continue
		candidate = candidate.strip()
		if not candidate:
			continue
		unquoted = candidate.strip("\"'")
		for pattern in (_FILE_URI_RE, _WEB_URI_RE, _DOCUMENT_PATH_RE):
			match = pattern.search(candidate)
			if match:
				return match.group(1)
		if _isDriveAbsolute(unquoted.replace("/", "\\")) or _isUncPath(unquoted):
			return ntpath.normpath(unquoted.replace("/", "\\"))
	return None
