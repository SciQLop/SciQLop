# Vendored web assets

Pinned copies fetched from jsDelivr (`curl -L`), no CDN loaded at runtime.

| Package | Version | File(s) | License | Source |
|---|---|---|---|---|
| markdown-it | 14.1.0 | `markdown-it.min.js` | MIT | https://cdn.jsdelivr.net/npm/markdown-it@14.1.0/dist/markdown-it.min.js |
| highlight.js (cdn-assets build, all languages) | 11.12.0 | `highlight.min.js` | BSD-3-Clause | https://cdn.jsdelivr.net/npm/@highlightjs/cdn-assets@11.12.0/highlight.min.js |
| KaTeX | 0.18.7 | `katex.min.js`, `katex.min.css`, `fonts/*.woff2` | MIT | https://cdn.jsdelivr.net/npm/katex@0.18.7/dist/ |

`katex.min.css` was edited after download to drop the `.ttf`/`.woff` `src`
entries in every `@font-face` rule, keeping only the vendored `.woff2` file
per family (no ttf/woff files are shipped).

`markdown-it-texmath` was evaluated but has no browser-ready UMD/minified
build on npm (only a CommonJS `texmath.js` using `module.exports`), so LaTeX
math is handled instead by a small pre-pass in `transcript.js` that finds
`$$...$$` (display) and `$...$` (inline) spans outside code spans/fences and
renders them with `katex.renderToString(..., {throwOnError: false})`.

Global names exposed by each UMD bundle: `window.markdownit`, `window.hljs`,
`window.katex`.
