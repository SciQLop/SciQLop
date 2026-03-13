let backend = null;
let selectedCard = null;

// --- Initialization ---

function init() {
    new QWebChannel(qt.webChannelTransport, function(channel) {
        backend = channel.objects.backend;
        loadHero();
        loadQuickstart();
        loadWorkspaces();
        loadExamples();
        loadNews();
        loadFeatured();

        backend.workspace_list_changed.connect(function() {
            loadWorkspaces();
            loadHero();
        });
        backend.quickstart_changed.connect(loadQuickstart);

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
        hero.innerHTML =
            '<div class="hero-info">' +
                '<span class="hero-name">\u26A1 Resume: ' + escapeHtml(ws.name) + '</span>' +
                '<span class="hero-sub">Last used: ' + escapeHtml(ws.last_used) + '</span>' +
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
            card.title = s.description;
            if (s.icon) {
                const img = document.createElement("img");
                img.src = s.icon;
                img.style.width = "48px";
                img.style.height = "48px";
                card.appendChild(img);
            }
            const label = document.createElement("span");
            label.textContent = s.name;
            card.appendChild(label);
            card.addEventListener("click", function() {
                backend.run_quickstart(s.name);
            });
            container.appendChild(card);
        });
    });
}

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
        });
    });
}

function loadExamples() {
    backend.list_examples(function(json_str) {
        const examples = JSON.parse(json_str);
        const container = document.getElementById("example-cards");
        container.innerHTML = "";
        examples.forEach(function(ex) {
            container.appendChild(createExampleCard(ex));
        });
    });
}

function loadNews() {
    backend.list_news(function(json_str) {
        const news = JSON.parse(json_str);
        const container = document.getElementById("news-list");
        container.innerHTML = "";
        news.forEach(function(item) {
            const row = document.createElement("div");
            row.className = "news-item";
            row.innerHTML =
                '<span class="news-icon">' + item.icon + '</span>' +
                '<span class="news-text">' + escapeHtml(item.title) + '</span>' +
                '<span class="news-date">' + escapeHtml(item.date || "") + '</span>';
            container.appendChild(row);
        });
    });
}

function loadFeatured() {
    backend.list_featured_packages(function(json_str) {
        const packages = JSON.parse(json_str);
        const container = document.getElementById("featured-cards");
        container.innerHTML = "";
        packages.forEach(function(pkg) {
            container.appendChild(createFeaturedCard(pkg));
        });
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

    card.innerHTML =
        '<div class="card-image-wrapper">' + imageHtml + '</div>' +
        '<div class="card-body">' +
            badges +
            '<span class="card-name">' + escapeHtml(ws.name) + '</span>' +
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

    card.innerHTML =
        '<div class="card-image-wrapper">' + imageHtml + '</div>' +
        '<div class="card-body">' +
            '<span class="card-name">' + escapeHtml(ex.name) + '</span>' +
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

var TYPE_ICONS = {plugin: "\uD83D\uDD0C", workspace: "\uD83D\uDCC1", example: "\uD83D\uDCD6"};

function createFeaturedCard(pkg) {
    const card = document.createElement("div");
    card.className = "card";
    card.dataset.name = pkg.name.toLowerCase();
    card.dataset.tags = (pkg.tags || []).join(" ").toLowerCase();

    const icon = TYPE_ICONS[pkg.type] || "\uD83D\uDCE6";
    card.innerHTML =
        '<div class="card-image-wrapper"><div class="card-image placeholder">' + icon + '</div></div>' +
        '<div class="card-body">' +
            '<span class="card-badge">' + escapeHtml(pkg.type) + '</span>' +
            '<span class="card-name">' + escapeHtml(pkg.name) + '</span>' +
            '<div class="card-stars">\u2B50 ' + pkg.stars + '</div>' +
        '</div>';

    card.addEventListener("click", function() {
        selectCard(card);
        showFeaturedDetails(pkg);
    });
    return card;
}

// --- Details panel ---

function showWorkspaceDetails(ws, isActive) {
    const panel = document.getElementById("details-panel");
    document.getElementById("details-title").textContent = "Workspace details";

    const editable = !ws.is_default;
    const content = document.getElementById("details-content");

    var nameHtml = editable
        ? '<input id="ws-name-input" type="text" value="' + escapeAttr(ws.name) + '">'
        : '<span>' + escapeHtml(ws.name) + '</span>';

    var descHtml = editable
        ? '<textarea id="ws-desc-input" rows="2">' + escapeHtml(ws.description || "") + '</textarea>'
        : '<span>' + escapeHtml(ws.description || "") + '</span>';

    var pkgHtml = buildPackageList(ws, isActive, editable);

    content.innerHTML =
        '<div class="details-field"><label>Name</label>' + nameHtml + '</div>' +
        '<div class="details-field"><label>Last used</label><span>' + escapeHtml(ws.last_used) + '</span></div>' +
        '<div class="details-field"><label>Last modified</label><span>' + escapeHtml(ws.last_modified) + '</span></div>' +
        '<div class="details-field"><label>Description</label>' + descHtml + '</div>' +
        '<div class="details-section"><label>Packages</label>' + pkgHtml + '</div>' +
        '<div class="details-actions">' +
            '<button class="primary" onclick="tryOpenWorkspace(\'' + escapeAttr(ws.directory) + '\')">Open workspace</button>' +
            '<div class="details-actions-row">' +
                '<button class="secondary" onclick="backend.duplicate_workspace(\'' + escapeAttr(ws.directory) + '\')">Clone</button>' +
                (ws.is_default ? '' :
                    '<button class="secondary danger" onclick="confirmDelete(\'' + escapeAttr(ws.directory) + '\', \'' + escapeAttr(ws.name) + '\')">Delete</button>') +
            '</div>' +
        '</div>';

    if (editable) {
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
                ws.requires = (ws.requires || []).concat([dep]);
                if (isActive) {
                    backend.add_dependencies_to_workspace(
                        ws.directory, JSON.stringify([dep]));
                } else {
                    backend.update_workspace_field(ws.directory,
                        JSON.stringify({field: "requires", value: ws.requires}));
                }
                showWorkspaceDetails(ws, isActive);
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

    const content = document.getElementById("details-content");
    content.innerHTML =
        '<div class="details-field"><label>Name</label><span>' + escapeHtml(ex.name) + '</span></div>' +
        '<div class="details-field"><label>Description</label><span>' + escapeHtml(ex.description || "") + '</span></div>' +
        '<div class="details-actions">' +
            '<button onclick="openExample(\'' + escapeAttr(ex.directory) + '\')">Add to workspace</button>' +
        '</div>';

    panel.classList.remove("hidden");
    panel.classList.add("visible");
}

function showFeaturedDetails(pkg) {
    const panel = document.getElementById("details-panel");
    document.getElementById("details-title").textContent = pkg.type.charAt(0).toUpperCase() + pkg.type.slice(1) + " details";

    const tagsHtml = (pkg.tags || []).map(function(t) {
        return '<span class="card-badge">' + escapeHtml(t) + '</span>';
    }).join(" ");

    const content = document.getElementById("details-content");
    content.innerHTML =
        '<div class="details-field"><label>Name</label><span>' + escapeHtml(pkg.name) + '</span></div>' +
        '<div class="details-field"><label>Type</label><span>' + escapeHtml(pkg.type) + '</span></div>' +
        '<div class="details-field"><label>Author</label><span>' + escapeHtml(pkg.author) + '</span></div>' +
        '<div class="details-field"><label>Description</label><span>' + escapeHtml(pkg.description || "") + '</span></div>' +
        '<div class="details-field"><label>Tags</label><span>' + tagsHtml + '</span></div>' +
        '<div class="details-field"><label>Stars</label><span>\u2B50 ' + pkg.stars + '</span></div>' +
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

// --- Filtering ---

document.addEventListener("DOMContentLoaded", function() {
    var wsFilter = document.getElementById("workspace-filter");
    if (wsFilter) {
        wsFilter.addEventListener("input", function() {
            filterCards("workspace-cards", this.value);
        });
    }
    var exFilter = document.getElementById("example-filter");
    if (exFilter) {
        exFilter.addEventListener("input", function() {
            filterCards("example-cards", this.value);
        });
    }

    document.body.addEventListener("click", function(e) {
        if (!e.target.closest(".card, .shortcut-card, #details-panel, #hero")) {
            hideDetails();
        }
    });

    document.getElementById("modal-overlay").addEventListener("click", function(e) {
        if (e.target === this) hideModal();
    });
});

function filterCards(containerId, query) {
    query = query.toLowerCase();
    var container = document.getElementById(containerId);
    var cards = container.querySelectorAll(".card");
    cards.forEach(function(card) {
        var name = card.dataset.name || "";
        var tags = card.dataset.tags || "";
        var match = !query || name.includes(query) || tags.includes(query);
        card.style.display = match ? "" : "none";
    });
}

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

// --- Utilities ---

function escapeHtml(str) {
    var div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

function escapeAttr(str) {
    return str.replace(/\\/g, "\\\\").replace(/'/g, "\\'");
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

// --- Start ---
init();
