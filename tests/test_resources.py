import unittest

from tests.module_loader import loadAddonModule


resources = loadAddonModule("markdownNavigator_test_resources", "resources.py")


class DestinationResolutionTests(unittest.TestCase):
	def assertResolution(self, destination, base, action, value, fragment=""):
		resolved = resources.resolveDestination(destination, base)
		self.assertEqual(resolved.action, action)
		self.assertEqual(resolved.value, value)
		self.assertEqual(resolved.fragment, fragment)

	def test_web_mail_and_phone_destinations(self):
		self.assertResolution(
			"https://example.com/a",
			None,
			resources.DestinationAction.WEB,
			"https://example.com/a",
		)
		self.assertResolution(
			"ftp://example.com/file.zip",
			None,
			resources.DestinationAction.WEB,
			"ftp://example.com/file.zip",
		)
		self.assertResolution(
			"mailto:person@example.com",
			None,
			resources.DestinationAction.SHELL,
			"mailto:person@example.com",
		)
		self.assertResolution(
			"tel:+123456789",
			None,
			resources.DestinationAction.SHELL,
			"tel:+123456789",
		)

	def test_internal_fragment(self):
		self.assertResolution(
			"#%E5%AE%89%E8%A3%85",
			None,
			resources.DestinationAction.INTERNAL_FRAGMENT,
			"安装",
			fragment="安装",
		)

	def test_absolute_and_file_uri_paths(self):
		self.assertResolution(
			r"C:\Docs\photo.png",
			None,
			resources.DestinationAction.LOCAL_FILE,
			r"C:\Docs\photo.png",
		)
		self.assertResolution(
			"file:///C:/Docs/photo%20one.png",
			None,
			resources.DestinationAction.LOCAL_FILE,
			r"C:\Docs\photo one.png",
		)
		self.assertResolution(
			"file://server/share/photo.png",
			None,
			resources.DestinationAction.LOCAL_FILE,
			r"\\server\share\photo.png",
		)

	def test_relative_local_path_uses_document_directory(self):
		self.assertResolution(
			"images/photo%20one.png",
			r"C:\Docs\readme.md",
			resources.DestinationAction.LOCAL_FILE,
			r"C:\Docs\images\photo one.png",
		)

	def test_relative_web_target_uses_document_url(self):
		self.assertResolution(
			"guide/intro.md#start",
			"https://example.com/docs/readme.md",
			resources.DestinationAction.WEB,
			"https://example.com/docs/guide/intro.md#start",
			fragment="start",
		)

	def test_relative_path_without_document_location_is_not_guessed(self):
		self.assertResolution(
			"images/photo.png",
			None,
			resources.DestinationAction.UNRESOLVED_RELATIVE,
			"images/photo.png",
		)

	def test_same_local_document_fragment_stays_inside_document(self):
		self.assertResolution(
			"guide.md#install",
			r"C:\Docs\guide.md",
			resources.DestinationAction.INTERNAL_FRAGMENT,
			"install",
			fragment="install",
		)

	def test_unsafe_and_unknown_schemes_are_not_dispatched(self):
		self.assertResolution(
			"javascript:alert(1)",
			None,
			resources.DestinationAction.UNSUPPORTED,
			"javascript:alert(1)",
		)
		self.assertResolution(
			"data:text/plain,hello",
			None,
			resources.DestinationAction.UNSUPPORTED,
			"data:text/plain,hello",
		)

	def test_potentially_executable_local_files_are_blocked(self):
		for extension in (".exe", ".cmd", ".ps1", ".py", ".lnk", ".url"):
			with self.subTest(extension=extension):
				self.assertTrue(resources.isDangerousLocalPath(f"C:\\Downloads\\target{extension}"))
		self.assertTrue(resources.isDangerousLocalPath(r"C:\Downloads\setup.exe. "))
		self.assertTrue(resources.isDangerousLocalPath(r"C:\Downloads\safe.txt:payload.exe"))
		self.assertFalse(resources.isDangerousLocalPath(r"C:\Photos\photo.png"))
		self.assertFalse(resources.isDangerousLocalPath(r"C:\Docs\report.pdf"))

	def test_document_location_is_extracted_only_from_explicit_metadata(self):
		self.assertEqual(
			resources.findDocumentLocation([r"C:\Docs\readme.md"]),
			r"C:\Docs\readme.md",
		)
		self.assertEqual(
			resources.findDocumentLocation([r"C:\Docs\readme.md - Notepad"]),
			r"C:\Docs\readme.md",
		)
		self.assertEqual(
			resources.findDocumentLocation(["https://example.com/docs/readme.md - Browser"]),
			"https://example.com/docs/readme.md",
		)
		self.assertIsNone(resources.findDocumentLocation(["readme.md - Visual Studio Code"]))


if __name__ == "__main__":
	unittest.main()
