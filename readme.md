# NVDA Markdown Navigator

Markdown Navigator is an NVDA add-on designed to enhance the experience of editing and reading Markdown content. It allows you to use single-key navigation features, similar to NVDA's Browse Mode, within editable text areas (such as Notepad, VS Code, web-based editors, etc.).

It enables you to quickly jump to headings, lists, tables, code blocks, and various inline formatting without frequently pressing the arrow keys.

## Key Features

*   **Efficient Navigation**: Implements fast algorithms that allow for instant jumping even in large documents with tens of thousands of lines.
*   **Structured Browsing**: Supports navigation by headings, lists, tables, blockquotes, code blocks, and more.
*   **Inline Elements**: Supports jumping to bold, italic, links, images, and inline code.
*   **Target Activation**: Opens web, email, image, and local-file targets, and follows headings and footnotes within the document.
*   **Table Cell Navigation**: Provides shortcuts consistent with NVDA for moving between cells in Markdown tables.

## Usage

### Toggle Browse Mode
By default, single-key navigation is disabled. You need to manually enable Markdown Browse Mode.

*   **Shortcut**: `NVDA + Shift + Space` (Spacebar)
*   **Effect**: Turns the add-on's functionality on or off. NVDA will announce "Markdown Browse Mode On/Off". This feature also follows NVDA's "Audio indications for focus and browse modes" setting in the Browse Mode settings.

### Shortcut List (When Browse Mode is Enabled)

Once the mode is enabled, you can use the following single-letter keys.
*   Press the **Letter Key** to jump to the next element.
*   Press **Shift + Letter Key** to jump to the previous element.

| Key | Element Type | Description |
| :--- | :--- | :--- |
| **H** | Heading | Any level heading (`#` to `######`) |
| **1-6** | Heading 1-6 | Specific heading level |
| **T** | Table | Start of a table |
| **L** | List | Start of a list block |
| **I** | List Item | Specific list item (`-`, `*`, `1.`) |
| **Q** | Blockquote | Quote block (`>`) |
| **C** | Code | Code block (```` ``` ````) or inline code (`` ` ``) |
| **S** | Separator | Horizontal rule (`---`, `***`) |
| **X** | Checkbox | Task list item (`- [ ]`, `- [x]`) |
| **K** | Link | Inline links, reference links, autolinks, URLs, and email addresses |
| **Enter** | Activate Target | Open the link or image at the caret, or follow an internal heading or footnote |
| **G** | Graphic | Inline and reference-style images |
| **B** | Bold | Bold text (`**` or `__`) |
| **E** | Emphasis | Italic/Emphasis text (`*` or `_`) |
| **D** | Delete | Strikethrough text (`~~`) |
| **F** | Footnote | Footnote reference `[^1]` |
| **,** | End of Block | Jump to the end of the current block element |
| **Shift+,**| Start of Block | Jump to the start of the current block element |
| **M** | Math | LaTeX math expression (`$...$` or `$$...$$`) |

### Activating Links, Images, and Document Targets

With Markdown Browse Mode enabled, press **Enter** or **Numpad Enter** on a supported target:

*   Inline and reference-style links and images are supported, including `[text](url)`, `[text][id]`, `![alt](image)`, and `![alt][id]`.
*   Angle-bracket autolinks, GFM-style bare `http://`, `https://`, and `www.` URLs, and email addresses are supported.
*   `http`, `https`, and `ftp` targets open in the default browser. `mailto` and `tel` targets use the system's registered handler.
*   Absolute local paths and `file://` targets open with the Windows default associated application.
*   Relative paths are resolved from the current Markdown file when its location is reliably available. The add-on reports that the path cannot be resolved rather than guessing when the editor does not expose a document location.
*   Links beginning with `#` move to the matching ATX or Setext heading. GitHub-style heading fragments, Unicode headings, and duplicate heading suffixes such as `-1` are supported.
*   Enter on a footnote reference moves to its definition. Enter on the definition returns to the originating reference, or to the first matching reference when no return position is stored.
*   In a linked image such as `[![alt](image.png)](target)`, navigating with **K** and pressing Enter opens the outer link; navigating with **G** and pressing Enter opens the image source.

For safety, executable and script file types are not launched, and unsupported schemes such as `javascript:` and `data:` are rejected.

### Table Cell Navigation

When the cursor is inside a Markdown table and Browse Mode is enabled, you can use the following shortcuts to move between cells:

*   **Ctrl + Alt + Left Arrow**: Previous cell
*   **Ctrl + Alt + Right Arrow**: Next cell
*   **Ctrl + Alt + Up Arrow**: Cell above
*   **Ctrl + Alt + Down Arrow**: Cell below

## Notes

*   This add-on is specifically developed for Markdown editing scenarios. If you are reading an HTML page rendered by a browser, please use NVDA's built-in Browse Mode.
*   If pressing the keys above types characters instead of navigating, please check if you have enabled Browse Mode by pressing `NVDA + Shift + Space`.
*   In VS Code, due to the editor rendering content on demand (virtualization), this add-on's browse mode may not work as expected for content that is not currently visible/rendered.

Copyright (C) 2026 Cary-rowen <manchen_0528@outlook.com>
