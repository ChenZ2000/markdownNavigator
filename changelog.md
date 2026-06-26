### 0.2.7

- Simplified Markdown navigation internals to reduce duplicated code.
- Improved caret positioning consistency in Chrome and Edge web editors.
- Removed the old legacy navigation fallback now that the fast navigation path is the main implementation.

Note: If a text editor does not support the fast navigation path, Markdown navigation may no longer fall back to the older slower method.
