import unittest

from tests.module_loader import loadAddonModule


targets = loadAddonModule("markdownNavigator_test_targets", "targets.py")


class MarkdownDocumentIndexTests(unittest.TestCase):
	def test_inline_links_and_images_decode_destinations(self):
		text = (
			'[site](https://example.com/a_(b) "Title") '
			'![photo](<images/photo one.png> "Photo") '
			"[entity](https://example.com/?a=1&amp;b=2)"
		)
		index = targets.MarkdownDocumentIndex(text)

		links = index.targetsOfKinds(targets.LINK_TARGET_KINDS)
		images = index.targetsOfKinds(targets.IMAGE_TARGET_KINDS)
		self.assertEqual(
			[link.destination for link in links],
			["https://example.com/a_(b)", "https://example.com/?a=1&b=2"],
		)
		self.assertEqual([image.destination for image in images], ["images/photo one.png"])

	def test_linked_image_has_deterministic_activation_priority(self):
		text = "[![alt](photo.png)](https://example.com)"
		index = targets.MarkdownDocumentIndex(text)

		self.assertEqual(index.targetAtOffset(0).kind, targets.TargetKind.INLINE_LINK)
		self.assertEqual(index.targetAtOffset(1).kind, targets.TargetKind.INLINE_IMAGE)
		self.assertEqual(index.targetAtOffset(text.index("alt")).kind, targets.TargetKind.INLINE_LINK)

	def test_reference_links_and_images_resolve_all_standard_forms(self):
		text = """[Full][Target] [Collapsed][] [Shortcut] ![Photo][image] ![Collapsed image][]

[target]: https://example.com/full
[collapsed]: https://example.com/collapsed "Title"
[shortcut]: #section
[image]: <images/photo one.png>
[collapsed image]: images/collapsed.png
"""
		index = targets.MarkdownDocumentIndex(text)

		self.assertEqual(
			[target.destination for target in index.targetsOfKinds(targets.LINK_TARGET_KINDS)],
			[
				"https://example.com/full",
				"https://example.com/collapsed",
				"#section",
			],
		)
		self.assertEqual(
			[target.destination for target in index.targetsOfKinds(targets.IMAGE_TARGET_KINDS)],
			["images/photo one.png", "images/collapsed.png"],
		)

	def test_reference_labels_are_case_insensitive_and_whitespace_normalized(self):
		text = "[link][  Mixed   CASE ]\n\n[mixed case]: https://example.com"
		index = targets.MarkdownDocumentIndex(text)
		links = index.targetsOfKinds(targets.LINK_TARGET_KINDS)
		self.assertEqual(len(links), 1)
		self.assertEqual(links[0].destination, "https://example.com")

	def test_unresolved_reference_is_not_exposed_as_a_link(self):
		index = targets.MarkdownDocumentIndex("[missing][definition] and [shortcut]")
		self.assertEqual(index.targetsOfKinds(targets.LINK_TARGET_KINDS), [])

	def test_invalid_reference_definition_trailing_text_is_rejected(self):
		text = "[link][id]\n\n[id]: https://example.com invalid trailing text"
		index = targets.MarkdownDocumentIndex(text)
		self.assertFalse(
			any(target.kind == targets.TargetKind.REFERENCE_LINK for target in index.targets),
		)

	def test_reference_destination_can_follow_colon_on_next_line(self):
		text = "[link][id]\n\n[id]:\n   <https://example.com/next-line>"
		index = targets.MarkdownDocumentIndex(text)
		links = index.targetsOfKinds(targets.LINK_TARGET_KINDS)
		self.assertEqual(len(links), 1)
		self.assertEqual(links[0].destination, "https://example.com/next-line")

	def test_angle_and_gfm_extended_autolinks(self):
		text = (
			"<https://example.com/a> <person@example.com> "
			"https://openai.com/test_(one). www.example.org/path, person.two@example.org."
		)
		index = targets.MarkdownDocumentIndex(text)
		links = index.targetsOfKinds(targets.LINK_TARGET_KINDS)

		self.assertEqual(
			[target.destination for target in links],
			[
				"https://example.com/a",
				"mailto:person@example.com",
				"https://openai.com/test_(one)",
				"http://www.example.org/path",
				"mailto:person.two@example.org",
			],
		)

	def test_incomplete_bare_urls_are_not_exposed(self):
		index = targets.MarkdownDocumentIndex("https:// www. followed by ordinary text")
		self.assertEqual(index.targetsOfKinds(targets.LINK_TARGET_KINDS), [])

	def test_inline_and_fenced_code_are_not_indexed(self):
		text = """`[inline](https://inline.example)`
```markdown
[fenced](https://fenced.example)
![fenced](photo.png)
```
[real](https://real.example)
"""
		index = targets.MarkdownDocumentIndex(text)
		self.assertEqual(
			[target.destination for target in index.targetsOfKinds(targets.LINK_TARGET_KINDS)],
			["https://real.example"],
		)
		self.assertEqual(index.targetsOfKinds(targets.IMAGE_TARGET_KINDS), [])

	def test_footnote_references_and_definitions_are_indexed_separately(self):
		text = "First[^Note] and again[^note].\n\n[^note]: Footnote body."
		index = targets.MarkdownDocumentIndex(text)

		footnotes = index.targetsOfKinds(targets.FOOTNOTE_TARGET_KINDS)
		self.assertEqual(
			[target.kind for target in footnotes],
			[
				targets.TargetKind.FOOTNOTE_REFERENCE,
				targets.TargetKind.FOOTNOTE_REFERENCE,
				targets.TargetKind.FOOTNOTE_DEFINITION,
			],
		)
		self.assertIsNotNone(index.footnoteDefinition("NOTE"))
		self.assertEqual(len(index.footnoteReferences("note")), 2)

	def test_github_heading_fragments_and_duplicates(self):
		text = """# Sample Section
## This'll be a _Helpful_ Section About the Greek Letter Θ!
## 重复标题
## 重复标题
Setext Heading
---------------
"""
		index = targets.MarkdownDocumentIndex(text)

		self.assertEqual(
			[heading.slug for heading in index.headings],
			[
				"sample-section",
				"thisll-be-a-helpful-section-about-the-greek-letter-θ",
				"重复标题",
				"重复标题-1",
				"setext-heading",
			],
		)
		self.assertEqual(index.findHeading("#sample-section").text, "Sample Section")
		self.assertEqual(index.findHeading("%E9%87%8D%E5%A4%8D%E6%A0%87%E9%A2%98-1").lineIndex, 3)
		self.assertEqual(index.findHeading("Setext Heading").lineIndex, 4)

	def test_line_index_lookup_handles_multiple_newline_styles(self):
		text = "first\r\nsecond\nthird\rfourth"
		index = targets.MarkdownDocumentIndex(text)
		self.assertEqual(index.lineIndexAtOffset(text.index("second")), 1)
		self.assertEqual(index.lineIndexAtOffset(text.index("third")), 2)
		self.assertEqual(index.lineIndexAtOffset(text.index("fourth")), 3)


if __name__ == "__main__":
	unittest.main()
