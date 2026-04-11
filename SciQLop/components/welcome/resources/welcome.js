let backend = null;
let selectedCard = null;
let _currentDetailsWs = null;
let _currentDetailsIsActive = false;
var _installedExamples = {};

// --- Initialization ---

function init() {
    new QWebChannel(qt.webChannelTransport, function(channel) {
        backend = channel.objects.backend;
        loadHero();
        loadQuickstart();
        loadWorkspaces();
        loadExamples();
        loadTemplates();
        loadNews();
        loadFeatured();

        backend.workspace_list_changed.connect(function() {
            loadWorkspaces();
            loadHero();
        });
        backend.quickstart_changed.connect(loadQuickstart);
        backend.templates_changed.connect(loadTemplates);
        backend.latest_release_ready.connect(showLatestRelease);
        backend.featured_packages_ready.connect(onFeaturedReady);
        backend.dependency_install_finished.connect(onDependencyInstallFinished);
        backend.fetch_latest_release();
        backend.fetch_featured_packages();

        document.getElementById("browse-all-link").addEventListener("click", function(e) {
            e.preventDefault();
            backend.open_appstore();
        });
    });
}

// --- Hero ---

function loadHero() {
    backend.get_hero_workspace(function(json_str) {
        const hero = document.getElementById("hero");
        const ws = JSON.parse(json_str);
        if (!ws) {
            hero.classList.add("hidden");
            hero.innerHTML = '';
            return;
        }
        hero.classList.remove("hidden");
        var heroImgHtml = ws.image
            ? '<img class="hero-thumbnail" src="file://' + ws.image + '">'
            : '<div class="hero-thumbnail hero-thumbnail-placeholder">\uD83D\uDCC1</div>';
        hero.innerHTML =
            heroImgHtml +
            '<div class="hero-info">' +
                '<span class="hero-name">\u26A1 Resume: ' + escapeHtml(ws.name) + '</span>' +
                '<span class="hero-sub">' + relativeTime(ws.last_used) + '</span>' +
            '</div>' +
            '<button id="hero-open">Open</button>';
        document.getElementById("hero-open").addEventListener("click", function() {
            tryOpenWorkspace(ws.directory);
        });
    });
}

// --- Data loading ---

function loadQuickstart() {
    backend.list_quickstart_shortcuts(function(json_str) {
        const shortcuts = JSON.parse(json_str);
        const container = document.getElementById("quickstart-cards");
        container.innerHTML = "";
        shortcuts.forEach(function(s) {
            const card = document.createElement("div");
            card.className = "shortcut-card";
            if (s.icon) {
                const img = document.createElement("img");
                img.src = s.icon;
                img.style.width = "48px";
                img.style.height = "48px";
                card.appendChild(img);
            }
            const label = document.createElement("span");
            label.className = "shortcut-name";
            label.textContent = s.name;
            card.appendChild(label);
            if (s.description) {
                const desc = document.createElement("span");
                desc.className = "shortcut-desc";
                desc.textContent = s.description;
                card.appendChild(desc);
            }
            card.addEventListener("click", function() {
                backend.run_quickstart(s.name);
            });
            container.appendChild(card);
        });
    });
}

var _initialLoad = true;

function loadWorkspaces() {
    backend.get_active_workspace_dir(function(activeJson) {
        var activeDir = JSON.parse(activeJson);
        backend.list_workspaces(function(json_str) {
            const workspaces = JSON.parse(json_str);
            const container = document.getElementById("workspace-cards");
            container.innerHTML = "";

            container.appendChild(createNewWorkspaceCard());

            workspaces.forEach(function(ws) {
                container.appendChild(createWorkspaceCard(ws, activeDir));
            });

            if (_initialLoad) {
                _initialLoad = false;
                adaptLayoutToUserState(workspaces.length > 0);
            }
        });
    });
}

function _refreshInstalledExamples(callback) {
    backend.get_active_workspace_dir(function(activeJson) {
        var wsDir = JSON.parse(activeJson);
        if (!wsDir) {
            _installedExamples = {};
            if (callback) callback();
            return;
        }
        backend.get_installed_examples(wsDir, function(json_str) {
            var list = JSON.parse(json_str);
            _installedExamples = {};
            list.forEach(function(e) { _installedExamples[e.name] = e.version; });
            if (callback) callback();
        });
    });
}

function loadExamples() {
    _refreshInstalledExamples(function() {
        backend.list_examples(function(json_str) {
            const examples = JSON.parse(json_str);
            const container = document.getElementById("example-cards");
            container.innerHTML = "";
            examples.forEach(function(ex) {
                container.appendChild(createExampleCard(ex));
            });
        });
    });
}

function loadTemplates() {
    backend.list_templates(function(json_str) {
        var templates = JSON.parse(json_str);
        var container = document.getElementById("template-cards");
        container.innerHTML = "";
        templates.forEach(function(t) {
            var card = document.createElement("div");
            card.className = "card";
            card.dataset.name = t.name.toLowerCase();
            var imgHtml = t.image
                ? '<img class="card-preview" src="file://' + t.image + '">'
                : '';
            card.innerHTML = imgHtml +
                '<div class="card-header">' +
                    '<span class="card-name">' + escapeHtml(t.name) + '</span>' +
                '</div>' +
                '<p class="card-desc">' + escapeHtml(t.description || "Panel template") + '</p>';
            card.addEventListener("click", function() {
                backend.load_template(t.stem);
            });
            card.addEventListener("contextmenu", function(e) {
                e.preventDefault();
                showTemplateContextMenu(e, t.stem, t.name);
            });
            container.appendChild(card);
        });
        // "Import..." card at the end
        var importCard = document.createElement("div");
        importCard.className = "card card-action";
        importCard.innerHTML = '<span class="card-action-label">Import\u2026</span>';
        importCard.addEventListener("click", function() {
            backend.import_template();
        });
        container.appendChild(importCard);
    });
}

function loadNews() {
    backend.list_news(function(json_str) {
        const news = JSON.parse(json_str);
        const banner = document.getElementById("news-banner");
        const container = document.getElementById("news-list");
        container.innerHTML = "";
        if (!news || news.length === 0) {
            banner.classList.add("hidden");
            return;
        }
        news.forEach(function(item) {
            const row = document.createElement("div");
            row.className = "news-item";
            row.innerHTML =
                '<span class="news-icon">' + item.icon + '</span>' +
                '<span class="news-text">' + escapeHtml(item.title) + '</span>' +
                '<span class="news-date">' + escapeHtml(item.date || "") + '</span>';
            container.appendChild(row);
        });
        banner.classList.remove("hidden");
        document.getElementById("news-dismiss").addEventListener("click", function() {
            banner.classList.add("hidden");
        });
    });
}

function loadFeatured() {
    // initial load handled by fetch_featured_packages + onFeaturedReady signal
}

function onFeaturedReady(json_str) {
    var packages = JSON.parse(json_str);
    var container = document.getElementById("featured-cards");
    container.innerHTML = "";
    packages.forEach(function(pkg) {
        container.appendChild(createFeaturedCard(pkg));
    });
}

function compareVersions(a, b) {
    var pa = a.replace(/^v/, "").split(".").map(Number);
    var pb = b.replace(/^v/, "").split(".").map(Number);
    for (var i = 0; i < Math.max(pa.length, pb.length); i++) {
        var na = pa[i] || 0;
        var nb = pb[i] || 0;
        if (na !== nb) return na - nb;
    }
    return 0;
}

function showLatestRelease(json_str) {
    var container = document.getElementById("latest-release");
    var release = JSON.parse(json_str);
    if (!release) {
        container.classList.add("hidden");
        return;
    }

    backend.get_current_version(function(currentVersion) {
        var isNewer = compareVersions(release.tag, currentVersion) > 0;
        container.classList.remove("hidden");
        container.className = isNewer ? "release-update" : "release-current";
        container.innerHTML = isNewer
            ? '<span class="release-label">\u2B06\uFE0F Update available!</span>' +
              '<a class="release-link" href="' + escapeAttr(release.url) + '">' +
                  escapeHtml(release.name || release.tag) +
              '</a>' +
              '<span class="release-current-version">Current: ' + escapeHtml(currentVersion) + '</span>'
            : '<span class="release-label">\u2705 Up to date</span>' +
              '<span class="release-version">' + escapeHtml(currentVersion) + '</span>';

        var link = container.querySelector(".release-link");
        if (link) {
            link.addEventListener("click", function(e) {
                e.preventDefault();
                backend.open_url(release.url);
            });
        }
    });
}

// --- Card creation ---

function createNewWorkspaceCard() {
    const card = document.createElement("div");
    card.className = "card new-workspace";
    card.innerHTML =
        '<div class="card-image-wrapper"><div class="card-image placeholder">+</div></div>' +
        '<div class="card-body"><span class="card-name">New workspace</span></div>';
    card.addEventListener("click", function() {
        backend.create_workspace();
    });
    return card;
}

function createWorkspaceCard(ws, activeDir) {
    const card = document.createElement("div");
    card.className = "card";
    card.dataset.name = ws.name.toLowerCase();
    card.dataset.directory = ws.directory;

    let imageHtml;
    if (ws.image) {
        imageHtml = '<img class="card-image" src="file://' + ws.image + '">';
    } else {
        imageHtml = '<div class="card-image placeholder">\uD83D\uDCC1</div>';
    }

    const isActive = activeDir && ws.directory === activeDir;
    let badges = "";
    if (isActive) badges += '<span class="card-badge badge-active">Active</span>';
    if (ws.is_default) badges += '<span class="card-badge">Default</span>';

    var accentColor = nameToColor(ws.name);
    card.style.borderLeftColor = accentColor;
    card.classList.add("card-accented");

    card.innerHTML =
        '<div class="card-image-wrapper">' + imageHtml + '</div>' +
        '<div class="card-body">' +
            badges +
            '<span class="card-name">' + escapeHtml(ws.name) + '</span>' +
            '<span class="card-sub">' + relativeTime(ws.last_used) + '</span>' +
        '</div>';

    card.addEventListener("click", function(e) {
        selectCard(card);
        showWorkspaceDetails(ws, isActive);
    });
    card.addEventListener("dblclick", function() {
        tryOpenWorkspace(ws.directory);
    });
    return card;
}

function createExampleCard(ex) {
    const card = document.createElement("div");
    card.className = "card";
    card.dataset.name = ex.name.toLowerCase();
    card.dataset.tags = (ex.tags || []).join(" ").toLowerCase();

    let imageHtml;
    if (ex.image) {
        imageHtml = '<img class="card-image" src="file://' + ex.image + '">';
    } else {
        imageHtml = '<div class="card-image placeholder">\uD83D\uDCD6</div>';
    }

    const tagsHtml = (ex.tags || []).length > 0
        ? '<div class="card-tags">Tags: ' + escapeHtml(ex.tags.join(", ")) + '</div>'
        : '';

    var isInstalled = ex.name in _installedExamples;
    var installedVersion = isInstalled ? _installedExamples[ex.name] : null;
    var hasUpdate = isInstalled && ex.version && installedVersion !== ex.version;
    var badgeHtml = hasUpdate
        ? '<span class="card-installed-badge" style="background:#e67e22">update</span>'
        : isInstalled
        ? '<span class="card-installed-badge">installed</span>'
        : '';

    card.innerHTML =
        '<div class="card-image-wrapper">' + imageHtml + '</div>' +
        '<div class="card-body">' +
            '<div class="card-name-row">' +
                '<span class="card-name">' + escapeHtml(ex.name) + '</span>' +
                badgeHtml +
            '</div>' +
            tagsHtml +
        '</div>';

    card.addEventListener("click", function() {
        selectCard(card);
        showExampleDetails(ex);
    });
    card.addEventListener("dblclick", function() {
        openExample(ex.directory);
    });
    return card;
}

var FEATURED_TYPE_ICONS = {plugin: "\uD83D\uDD0C", workspace: "\uD83D\uDCC1", template: "\uD83D\uDCC4", example: "\uD83D\uDCD6"};

function createFeaturedCard(pkg) {
    var card = document.createElement("div");
    card.className = "card";
    card.dataset.name = pkg.name.toLowerCase();
    card.dataset.tags = (pkg.tags || []).join(" ").toLowerCase();

    var type = pkg.type || "plugin";
    var icon = FEATURED_TYPE_ICONS[type] || "\uD83D\uDCE6";
    var versions = pkg.versions || [];
    var latest = versions.length > 0 ? versions[versions.length - 1] : null;
    var versionStr = latest ? "v" + latest.version : "";
    var starsStr = pkg.stars != null ? "\u2B50 " + pkg.stars : "";

    card.innerHTML =
        '<div class="card-image-wrapper"><div class="card-image placeholder">' + icon + '</div></div>' +
        '<div class="card-body">' +
            '<span class="card-badge">' + escapeHtml(type) + '</span>' +
            '<span class="card-name">' + escapeHtml(pkg.name) + '</span>' +
            '<div class="card-stars">' + escapeHtml(pkg.author) +
                (versionStr ? ' \u00B7 ' + escapeHtml(versionStr) : '') +
                (starsStr ? ' \u00B7 ' + starsStr : '') +
            '</div>' +
        '</div>';

    card.addEventListener("click", function() {
        selectCard(card);
        showFeaturedDetails(pkg);
    });
    return card;
}

// --- Details panel ---

function onDependencyInstallFinished(resultJson) {
    var result = JSON.parse(resultJson);
    if (_currentDetailsWs && _currentDetailsWs.directory === result.dir) {
        if (result.ok) {
            _currentDetailsWs.requires = (_currentDetailsWs.requires || []).concat(result.deps);
        }
        showWorkspaceDetails(_currentDetailsWs, _currentDetailsIsActive);
    }
}

function showWorkspaceDetails(ws, isActive) {
    _currentDetailsWs = ws;
    _currentDetailsIsActive = isActive;
    const panel = document.getElementById("details-panel");
    document.getElementById("details-title").textContent = "Workspace details";

    const metaEditable = !ws.is_default;
    const content = document.getElementById("details-content");

    var nameHtml = metaEditable
        ? '<input id="ws-name-input" type="text" value="' + escapeAttr(ws.name) + '">'
        : '<span>' + escapeHtml(ws.name) + '</span>';

    var descHtml = metaEditable
        ? '<textarea id="ws-desc-input" rows="2">' + escapeHtml(ws.description || "") + '</textarea>'
        : '<span>' + escapeHtml(ws.description || "") + '</span>';

    var pkgHtml = buildPackageList(ws, isActive, true);

    content.innerHTML =
        '<div class="details-field"><label>Name</label>' + nameHtml + '</div>' +
        '<div class="details-field"><label>Last used</label><span>' + escapeHtml(ws.last_used) + '</span></div>' +
        '<div class="details-field"><label>Last modified</label><span>' + escapeHtml(ws.last_modified) + '</span></div>' +
        '<div class="details-field"><label>Description</label>' + descHtml + '</div>' +
        '<div class="details-section"><label>Packages</label>' + pkgHtml + '</div>' +
        '<div class="details-actions">' +
            (isActive ? '' : '<button class="primary" onclick="tryOpenWorkspace(\'' + escapeAttr(ws.directory) + '\')">Open workspace</button>') +
            '<div class="details-actions-row">' +
                '<button class="secondary" onclick="backend.duplicate_workspace(\'' + escapeAttr(ws.directory) + '\')">Clone</button>' +
                (ws.is_default || isActive ? '' :
                    '<button class="secondary danger" onclick="confirmDelete(\'' + escapeAttr(ws.directory) + '\', \'' + escapeAttr(ws.name) + '\')">Delete</button>') +
            '</div>' +
        '</div>';

    if (metaEditable) {
        bindFieldEditor("ws-name-input", ws.directory, "name", ws, isActive);
        bindFieldEditor("ws-desc-input", ws.directory, "description", ws, isActive);
    }

    panel.classList.remove("hidden");
    panel.classList.add("visible");
}

function bindFieldEditor(inputId, directory, field, ws, isActive) {
    var el = document.getElementById(inputId);
    if (!el) return;
    var save = function() {
        var value = el.value.trim();
        if (value !== ws[field]) {
            ws[field] = value;
            backend.update_workspace_field(directory,
                JSON.stringify({field: field, value: value}));
        }
    };
    el.addEventListener("blur", save);
    el.addEventListener("keydown", function(e) {
        if (e.key === "Enter" && el.tagName === "INPUT") {
            e.preventDefault();
            el.blur();
        }
    });
}

function buildPackageList(ws, isActive, editable) {
    var requires = ws.requires || [];
    var html = '<ul class="pkg-list">';
    requires.forEach(function(dep) {
        html += '<li><span class="pkg-name">' + escapeHtml(dep) + '</span>';
        if (editable) {
            html += '<button class="pkg-remove" data-dep="' + escapeAttr(dep) +
                '" data-dir="' + escapeAttr(ws.directory) + '">&times;</button>';
        }
        html += '</li>';
    });
    if (requires.length === 0) {
        html += '<li class="pkg-empty">No packages</li>';
    }
    html += '</ul>';
    if (editable) {
        html += '<div class="pkg-add-row">' +
            '<input id="pkg-add-input" type="text" placeholder="package name...">' +
            '<button id="pkg-add-btn">Add</button></div>';
    }

    setTimeout(function() {
        document.querySelectorAll(".pkg-remove").forEach(function(btn) {
            btn.addEventListener("click", function() {
                var dep = btn.dataset.dep;
                var dir = btn.dataset.dir;
                backend.remove_dependency_from_workspace(dir, dep);
                ws.requires = ws.requires.filter(function(d) { return d !== dep; });
                showWorkspaceDetails(ws, isActive);
            });
        });
        var addBtn = document.getElementById("pkg-add-btn");
        var addInput = document.getElementById("pkg-add-input");
        if (addBtn && addInput) {
            var doAdd = function() {
                var dep = addInput.value.trim();
                if (!dep) return;
                backend.add_dependencies_to_workspace(
                    ws.directory, JSON.stringify([dep]));
            };
            addBtn.addEventListener("click", doAdd);
            addInput.addEventListener("keydown", function(e) {
                if (e.key === "Enter") { e.preventDefault(); doAdd(); }
            });
        }
    }, 0);

    return html;
}

function showExampleDetails(ex) {
    const panel = document.getElementById("details-panel");
    document.getElementById("details-title").textContent = "Example details";

    var isInstalled = ex.name in _installedExamples;
    var installedVersion = isInstalled ? _installedExamples[ex.name] : null;
    var hasUpdate = isInstalled && ex.version && installedVersion !== ex.version;

    var buttonLabel = hasUpdate ? "Update example" : isInstalled ? "Reinstall example" : "Add to workspace";
    var buttonClass = hasUpdate ? "primary" : "";
    var statusHtml = isInstalled
        ? '<div class="details-field"><label>Status</label><span>' +
            (hasUpdate ? 'Installed (update available)' : 'Installed') +
          '</span></div>'
        : '';

    const content = document.getElementById("details-content");
    content.innerHTML =
        '<div class="details-field"><label>Name</label><span>' + escapeHtml(ex.name) + '</span></div>' +
        '<div class="details-field"><label>Description</label><span>' + escapeHtml(ex.description || "") + '</span></div>' +
        (ex.version ? '<div class="details-field"><label>Version</label><span>' + escapeHtml(ex.version) + '</span></div>' : '') +
        statusHtml +
        '<div class="details-actions">' +
            '<button class="' + buttonClass + '" onclick="openExample(\'' + escapeAttr(ex.directory) + '\')">' + buttonLabel + '</button>' +
        '</div>';

    panel.classList.remove("hidden");
    panel.classList.add("visible");
}

function showFeaturedDetails(pkg) {
    var panel = document.getElementById("details-panel");
    var type = pkg.type || "plugin";
    document.getElementById("details-title").textContent = type.charAt(0).toUpperCase() + type.slice(1) + " details";

    var versions = pkg.versions || [];
    var latest = versions.length > 0 ? versions[versions.length - 1] : null;
    var versionStr = latest ? latest.version : "\u2014";
    var starsHtml = pkg.stars != null ? "\u2B50 " + pkg.stars : "\u2014";

    var tagsHtml = (pkg.tags || []).map(function(t) {
        return '<span class="card-badge">' + escapeHtml(t) + '</span>';
    }).join(" ");

    var content = document.getElementById("details-content");
    content.innerHTML =
        '<div class="details-field"><label>Name</label><span>' + escapeHtml(pkg.name) + '</span></div>' +
        '<div class="details-field"><label>Type</label><span><span class="card-badge">' + escapeHtml(type) + '</span></span></div>' +
        '<div class="details-field"><label>Author</label><span>' + escapeHtml(pkg.author) + '</span></div>' +
        '<div class="details-field"><label>License</label><span>' + escapeHtml(pkg.license || "\u2014") + '</span></div>' +
        (latest ? '<div class="details-field"><label>Version</label><span>' + escapeHtml(versionStr) + '</span></div>' : '') +
        '<div class="details-field"><label>Description</label><span>' + escapeHtml(pkg.description || "") + '</span></div>' +
        '<div class="details-field"><label>Tags</label><span>' + tagsHtml + '</span></div>' +
        '<div class="details-field"><label>Stars</label><span>' + starsHtml + '</span></div>' +
        '<div class="details-actions">' +
            '<button onclick="backend.open_appstore()">View in Store</button>' +
        '</div>';

    panel.classList.remove("hidden");
    panel.classList.add("visible");
}

function hideDetails() {
    const panel = document.getElementById("details-panel");
    panel.classList.remove("visible");
    panel.classList.add("hidden");
    if (selectedCard) {
        selectedCard.classList.remove("selected");
        selectedCard = null;
    }
}

function confirmDelete(directory, name) {
    if (confirm("Delete workspace '" + name + "'?")) {
        backend.delete_workspace(directory);
        hideDetails();
    }
}

// --- Selection ---

function selectCard(card) {
    if (selectedCard) selectedCard.classList.remove("selected");
    selectedCard = card;
    card.classList.add("selected");
}

// --- Global filter ---

var _filterableContainers = ["workspace-cards", "example-cards", "template-cards", "featured-cards"];

function clearGlobalFilter() {
    var input = document.getElementById("global-filter-input");
    input.value = "";
    input.blur();
    applyGlobalFilter("");
}

function applyGlobalFilter(query) {
    query = query.toLowerCase();
    var filtering = query.length > 0;

    _filterableContainers.forEach(function(containerId) {
        var container = document.getElementById(containerId);
        if (!container) return;
        var cards = container.querySelectorAll(".card");
        cards.forEach(function(card) {
            var name = card.dataset.name || "";
            var tags = card.dataset.tags || "";
            var match = !filtering || name.includes(query) || tags.includes(query);
            card.style.display = match ? "" : "none";
        });

        // Auto-expand collapsed sections that have matches
        if (filtering && container.classList.contains("collapsed")) {
            var hasVisible = Array.prototype.some.call(cards, function(c) {
                return c.style.display !== "none";
            });
            if (hasVisible) {
                container.classList.remove("collapsed");
                var btn = document.querySelector('.section-toggle[data-target="' + containerId + '"]');
                if (btn) btn.setAttribute("aria-expanded", "true");
            }
        }
    });

    // Also filter quickstart shortcuts
    var qsContainer = document.getElementById("quickstart-cards");
    if (qsContainer) {
        var shortcuts = qsContainer.querySelectorAll(".shortcut-card");
        shortcuts.forEach(function(card) {
            var name = (card.querySelector(".shortcut-name") || {}).textContent || "";
            var match = !filtering || name.toLowerCase().includes(query);
            card.style.display = match ? "" : "none";
        });
    }
}

document.addEventListener("DOMContentLoaded", function() {
    var filterInput = document.getElementById("global-filter-input");

    // Focus filter on any printable keystroke (GNOME Activities style)
    document.addEventListener("keydown", function(e) {
        var tag = (e.target.tagName || "").toLowerCase();
        if (tag === "input" || tag === "textarea") return;
        if (!document.getElementById("modal-overlay").classList.contains("hidden")) return;

        if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
            filterInput.focus();
        }
    });

    filterInput.addEventListener("input", function() {
        applyGlobalFilter(this.value);
    });

    filterInput.addEventListener("keydown", function(e) {
        if (e.key === "Escape") {
            e.preventDefault();
            clearGlobalFilter();
        }
    });

    document.body.addEventListener("click", function(e) {
        if (!e.target.closest(".card, .shortcut-card, #details-panel, #hero, #global-filter-bar")) {
            hideDetails();
        }
    });

    document.getElementById("modal-overlay").addEventListener("click", function(e) {
        if (e.target === this) hideModal();
    });
});

// --- Modal helpers ---

function showModal(title, bodyHtml, actionsHtml) {
    document.getElementById("modal-title").textContent = title;
    document.getElementById("modal-body").innerHTML = bodyHtml;
    document.getElementById("modal-actions").innerHTML = actionsHtml || "";
    document.getElementById("modal-overlay").classList.remove("hidden");
}

function hideModal() {
    document.getElementById("modal-overlay").classList.add("hidden");
}

// --- Example flow ---

function openExample(exampleDir) {
    backend.get_active_workspace_dir(function(json_str) {
        var wsDir = JSON.parse(json_str);
        if (wsDir) {
            addExampleAndPromptDeps(exampleDir, wsDir);
        } else {
            showWorkspacePicker(function(pickedDir) {
                addExampleAndPromptDeps(exampleDir, pickedDir);
            });
        }
    });
}

function addExampleAndPromptDeps(exampleDir, wsDir) {
    backend.add_example_to_workspace(exampleDir, wsDir, function(json_str) {
        var result = JSON.parse(json_str);
        var verb = result.is_update ? "updated" : "added";
        showToast("Example '" + result.name + "' " + verb + " successfully", "toast-success");
        loadExamples();
        if (result.missing_dependencies && result.missing_dependencies.length > 0) {
            confirmDependencies(wsDir, result.missing_dependencies);
        }
    });
}

function showWorkspacePicker(onPicked) {
    backend.list_workspaces(function(json_str) {
        var workspaces = JSON.parse(json_str);
        var listHtml = '<div class="modal-ws-list">';
        listHtml += '<div class="modal-ws-item" data-action="new">' +
            '<span class="ws-name">+ Create new workspace</span></div>';
        workspaces.forEach(function(ws) {
            listHtml += '<div class="modal-ws-item" data-dir="' + escapeAttr(ws.directory) + '">' +
                '<span class="ws-name">' + escapeHtml(ws.name) + '</span>' +
                '<span class="ws-sub">' + escapeHtml(ws.last_used) + '</span>' +
                '</div>';
        });
        listHtml += '</div>';
        showModal("Choose a workspace", listHtml, "");

        var actions = document.getElementById("modal-actions");
        var cancelBtn = document.createElement("button");
        cancelBtn.textContent = "Cancel";
        cancelBtn.addEventListener("click", hideModal);
        actions.appendChild(cancelBtn);

        document.querySelectorAll(".modal-ws-item").forEach(function(item) {
            item.addEventListener("click", function() {
                hideModal();
                if (item.dataset.action === "new") {
                    backend.create_workspace();
                    backend.list_workspaces(function(json2) {
                        var wsList = JSON.parse(json2);
                        if (wsList.length > 0) {
                            wsList.sort(function(a, b) {
                                return b.last_modified.localeCompare(a.last_modified);
                            });
                            onPicked(wsList[0].directory);
                        }
                    });
                } else {
                    onPicked(item.dataset.dir);
                }
            });
        });
    });
}

var _pendingDeps = null;

function confirmDependencies(wsDir, deps) {
    if (!deps || deps.length === 0) return;
    _pendingDeps = { wsDir: wsDir, deps: deps };
    var listHtml = '<p>This example needs additional packages:</p><ul class="modal-dep-list">';
    deps.forEach(function(d) { listHtml += '<li>' + escapeHtml(d) + '</li>'; });
    listHtml += '</ul>';
    showModal("Install dependencies?", listHtml, "");

    var actions = document.getElementById("modal-actions");
    var skipBtn = document.createElement("button");
    skipBtn.textContent = "Skip";
    skipBtn.addEventListener("click", hideModal);

    var installBtn = document.createElement("button");
    installBtn.textContent = "Install";
    installBtn.className = "primary";
    installBtn.addEventListener("click", function() {
        hideModal();
        backend.add_dependencies_to_workspace(
            _pendingDeps.wsDir, JSON.stringify(_pendingDeps.deps));
        _pendingDeps = null;
    });

    actions.appendChild(skipBtn);
    actions.appendChild(installBtn);
}

// --- Workspace opening ---

function tryOpenWorkspace(directory) {
    if (confirm("SciQLop will restart to open this workspace.")) {
        backend.open_workspace(directory);
    }
}

// --- Toast notifications ---

function showToast(message, className) {
    var container = document.getElementById("toast-container");
    var toast = document.createElement("div");
    toast.className = "toast" + (className ? " " + className : "");
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(function() { toast.remove(); }, 3000);
}

// --- Utilities ---

function escapeHtml(str) {
    var div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

function escapeAttr(str) {
    return str.replace(/\\/g, "\\\\").replace(/'/g, "\\'");
}

function relativeTime(dateStr) {
    if (!dateStr) return "";
    var date = new Date(dateStr);
    if (isNaN(date.getTime())) return dateStr;
    var now = new Date();
    var diffMs = now - date;
    var diffSec = Math.floor(diffMs / 1000);
    if (diffSec < 60) return "just now";
    var diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return diffMin + (diffMin === 1 ? " minute ago" : " minutes ago");
    var diffHr = Math.floor(diffMin / 60);
    if (diffHr < 24) return diffHr + (diffHr === 1 ? " hour ago" : " hours ago");
    var diffDay = Math.floor(diffHr / 24);
    if (diffDay < 30) return diffDay + (diffDay === 1 ? " day ago" : " days ago");
    var diffMonth = Math.floor(diffDay / 30);
    if (diffMonth < 12) return diffMonth + (diffMonth === 1 ? " month ago" : " months ago");
    var diffYear = Math.floor(diffMonth / 12);
    return diffYear + (diffYear === 1 ? " year ago" : " years ago");
}

function nameToColor(name) {
    var hash = 0;
    for (var i = 0; i < name.length; i++) {
        hash = name.charCodeAt(i) + ((hash << 5) - hash);
    }
    var h = ((hash % 360) + 360) % 360;
    return "hsl(" + h + ", 55%, 55%)";
}

// --- Details panel resize ---

(function() {
    var handle = document.getElementById("details-resize-handle");
    var panel = document.getElementById("details-panel");
    var dragging = false;

    handle.addEventListener("mousedown", function(e) {
        e.preventDefault();
        dragging = true;
        handle.classList.add("dragging");
        panel.style.transition = "none";
        document.body.style.cursor = "col-resize";
        document.body.style.userSelect = "none";
    });

    document.addEventListener("mousemove", function(e) {
        if (!dragging) return;
        var newWidth = window.innerWidth - e.clientX;
        var min = 280;
        var max = window.innerWidth * 0.8;
        if (newWidth < min) newWidth = min;
        if (newWidth > max) newWidth = max;
        panel.style.width = newWidth + "px";
    });

    document.addEventListener("mouseup", function() {
        if (!dragging) return;
        dragging = false;
        handle.classList.remove("dragging");
        panel.style.transition = "";
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
    });
})();

// --- Template context menu ---

function showTemplateContextMenu(event, stem, displayName) {
    dismissTemplateContextMenu();
    var menu = document.createElement("div");
    menu.id = "template-context-menu";
    menu.className = "context-menu";

    var renameItem = document.createElement("div");
    renameItem.className = "context-menu-item";
    renameItem.textContent = "Rename\u2026";
    renameItem.addEventListener("click", function() {
        dismissTemplateContextMenu();
        var newName = prompt("Rename template:", displayName);
        if (newName && newName.trim() && newName.trim() !== stem) {
            backend.rename_template(stem, newName.trim());
        }
    });

    var deleteItem = document.createElement("div");
    deleteItem.className = "context-menu-item danger";
    deleteItem.textContent = "Delete";
    deleteItem.addEventListener("click", function() {
        dismissTemplateContextMenu();
        if (confirm("Delete template '" + displayName + "'?")) {
            backend.delete_template(stem);
        }
    });

    menu.appendChild(renameItem);
    menu.appendChild(deleteItem);
    menu.style.left = event.pageX + "px";
    menu.style.top = event.pageY + "px";
    document.body.appendChild(menu);

    setTimeout(function() {
        document.addEventListener("click", dismissTemplateContextMenu, { once: true });
    }, 0);
}

function dismissTemplateContextMenu() {
    var menu = document.getElementById("template-context-menu");
    if (menu) menu.remove();
}

// --- Collapsible sections ---

function initCollapsibleSections() {
    document.querySelectorAll(".section-toggle").forEach(function(btn) {
        btn.addEventListener("click", function() {
            var targetId = btn.dataset.target;
            var target = document.getElementById(targetId);
            var expanded = btn.getAttribute("aria-expanded") === "true";
            btn.setAttribute("aria-expanded", expanded ? "false" : "true");
            target.classList.toggle("collapsed", expanded);
        });
    });
}

function adaptLayoutToUserState(hasWorkspaces) {
    if (hasWorkspaces) {
        // Returning user: collapse secondary sections
        ["example-cards", "template-cards"].forEach(function(id) {
            var target = document.getElementById(id);
            var btn = document.querySelector('.section-toggle[data-target="' + id + '"]');
            if (target && btn) {
                target.classList.add("collapsed");
                btn.setAttribute("aria-expanded", "false");
            }
        });
    } else {
        // New user: hide empty workspaces section
        document.getElementById("recent-workspaces").style.display = "none";
    }
}

// --- Start ---
initCollapsibleSections();
init();
