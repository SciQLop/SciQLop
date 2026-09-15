/* Renders the transcript model pushed by TranscriptBridge (web_view.py).
 * Python owns render-worthy state (the coalescing timer, the expanded set),
 * this file only turns the latest model into DOM and reports user gestures
 * (toggle, link clicks) back to Python. */
(function () {
    "use strict";

    const BOTTOM_SLACK_PX = 4;
    const container = document.getElementById("transcript");

    const md = window.markdownit({
        html: false,
        linkify: true,
        breaks: false,
        highlight: highlightCode,
    });

    function highlightCode(code, lang) {
        if (lang && window.hljs.getLanguage(lang)) {
            try {
                return (
                    '<pre class="hljs"><code>' +
                    window.hljs.highlight(code, { language: lang, ignoreIllegals: true }).value +
                    "</code></pre>"
                );
            } catch (e) {
                /* fall through to the escaped default below */
            }
        }
        return '<pre class="hljs"><code>' + md.utils.escapeHtml(code) + "</code></pre>";
    }

    // --- LaTeX math: markdown-it-texmath has no browser-ready build on npm,
    // so $$...$$ (display) and $...$ (inline) are pulled out of the raw
    // markdown before rendering (skipping fenced/backtick code) and swapped
    // back in as KaTeX HTML afterwards. Placeholders use control characters
    // that cannot occur in real prose and are never markdown-significant, so
    // they survive inline parsing untouched. ---
    const MATH_MARK_START = "MATH";
    const MATH_MARK_END = "";
    const CODE_SPLIT_RE = /(```[\s\S]*?```|`[^`\n]+`)/g;
    const DISPLAY_MATH_RE = /\$\$([^$]+?)\$\$/g;
    const INLINE_MATH_RE = /\$([^\s$](?:[^$]*[^\s$])?)\$/g;

    function extractMath(text) {
        const blocks = [];
        function stash(display) {
            return function (_match, latex) {
                const id = blocks.length;
                blocks.push({ latex: latex, display: display });
                return MATH_MARK_START + id + MATH_MARK_END;
            };
        }
        const rebuilt = text
            .split(CODE_SPLIT_RE)
            .map(function (segment, i) {
                if (i % 2 === 1) return segment; // a captured code span/fence
                return segment
                    .replace(DISPLAY_MATH_RE, stash(true))
                    .replace(INLINE_MATH_RE, stash(false));
            })
            .join("");
        return { text: rebuilt, blocks: blocks };
    }

    function injectMath(html, blocks) {
        const markRe = new RegExp(MATH_MARK_START + "(\\d+)" + MATH_MARK_END, "g");
        return html.replace(markRe, function (_match, idxStr) {
            const block = blocks[parseInt(idxStr, 10)];
            if (!block) return "";
            try {
                return window.katex.renderToString(block.latex, {
                    throwOnError: false,
                    displayMode: block.display,
                });
            } catch (e) {
                return md.utils.escapeHtml(block.latex);
            }
        });
    }

    function renderMarkdown(markdown) {
        const extracted = extractMath(markdown);
        return injectMath(md.render(extracted.text), extracted.blocks);
    }

    function escapeHtml(text) {
        return text.replace(/[&<>"']/g, function (c) {
            return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
        });
    }

    function toolStepHtml(step) {
        let line = "▸ " + escapeHtml(step.name);
        if (step.input) {
            line += ' · <span class="tool-input">' + escapeHtml(step.input) + "</span>";
        }
        let html = '<p class="tool-step">' + line + "</p>";
        if (step.result) {
            html += '<p class="tool-result">↳ ' + escapeHtml(step.result) + "</p>";
        }
        return html;
    }

    function toolsPartHtml(part) {
        const arrow = part.expanded ? "▾" : "▸";
        let head;
        if (part.running && part.steps.length) {
            const last = part.steps[part.steps.length - 1];
            head = "● " + escapeHtml(last.name) + "… (" + part.steps.length + ")";
        } else {
            const n = part.steps.length;
            head = "🔧 " + n + " step" + (n !== 1 ? "s" : "");
        }
        let html =
            '<details class="tools" data-id="' +
            part.id +
            '"' +
            (part.expanded ? " open" : "") +
            "><summary>" +
            head +
            " " +
            arrow +
            "</summary>";
        if (part.expanded) {
            html += '<div class="tools-body">' + part.steps.map(toolStepHtml).join("") + "</div>";
        }
        html += "</details>";
        return html;
    }

    function partHtml(part) {
        switch (part.type) {
            case "text":
                return '<div class="text">' + renderMarkdown(part.markdown) + "</div>";
            case "thinking":
                return (
                    '<p class="thinking">' + escapeHtml(part.text).replace(/\n/g, "<br/>") + "</p>"
                );
            case "image":
                return '<p class="image"><img src="' + part.data_url + '"></p>';
            case "tools":
                return toolsPartHtml(part);
            default:
                return "";
        }
    }

    function messageHtml(message) {
        return (
            '<h4 class="role role-' +
            message.role +
            '">' +
            escapeHtml(message.label) +
            "</h4>" +
            message.parts.map(partHtml).join("")
        );
    }

    // --- Scroll policy: identical intent to TranscriptView (view.py) --
    // follow the bottom only while the reader is within BOTTOM_SLACK_PX of
    // it, otherwise keep their place across re-renders, and re-apply after
    // layout keeps changing (image decode, font/highlight CSS) so late
    // layout cannot strand the view mid-way.
    let followBottom = true;
    let restoreScrollY = null;
    let programmaticScroll = false;

    function atBottom() {
        const doc = document.documentElement;
        return doc.scrollHeight - window.scrollY - window.innerHeight <= BOTTOM_SLACK_PX;
    }

    function settleScroll() {
        programmaticScroll = true;
        if (followBottom) {
            window.scrollTo(0, document.documentElement.scrollHeight);
        } else if (restoreScrollY !== null) {
            window.scrollTo(0, restoreScrollY);
        }
        requestAnimationFrame(function () {
            programmaticScroll = false;
        });
    }

    window.addEventListener("scroll", function () {
        if (programmaticScroll) return;
        followBottom = atBottom();
    });

    if (window.ResizeObserver) {
        new ResizeObserver(settleScroll).observe(document.body);
    }

    container.addEventListener(
        "toggle",
        function (event) {
            const details = event.target;
            if (backend && details && details.dataset && details.dataset.id) {
                backend.toggle(details.dataset.id);
            }
        },
        true // 'toggle' does not bubble; capture it on the way down instead.
    );

    container.addEventListener("click", function (event) {
        const link = event.target.closest("a");
        if (link) {
            event.preventDefault();
            if (backend) backend.open_link(link.getAttribute("href") || "");
        }
    });

    let backend = null;

    function render(json) {
        const model = JSON.parse(json);
        if (!followBottom) restoreScrollY = window.scrollY;
        container.innerHTML = model.map(messageHtml).join("");
        settleScroll();
        setTimeout(settleScroll, 0);
    }

    new QWebChannel(qt.webChannelTransport, function (channel) {
        backend = channel.objects.backend;
        backend.transcript_changed.connect(render);
        backend.current_state().then(render);
    });
})();
