### Unreleased

- Added Enter and Numpad Enter activation for inline, reference-style, and automatic links and images.
- Added safe dispatch for web, email, phone, absolute local, `file://`, and reliably resolved relative targets.
- Added in-document navigation for heading fragments and round-trip footnote navigation.
- Added a unified target index used by K, G, F, and Enter, with fenced-code and inline-code exclusion.
- Added automated parser, resolver, safety, and simulated NVDA behavior tests.

### 0.2.7

- Simplified Markdown navigation internals to reduce duplicated code.
- Improved caret positioning consistency in Chrome and Edge web editors.
- Removed the old legacy navigation fallback now that the fast navigation path is the main implementation.

Note: If a text editor does not support the fast navigation path, Markdown navigation may no longer fall back to the older slower method.
