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
            backend.open_workspace(ws.directory);
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
    backend.list_workspaces(function(json_str) {
        const workspaces = JSON.parse(json_str);
        const container = document.getElementById("workspace-cards");
        container.innerHTML = "";

        container.appendChild(createNewWorkspaceCard());

        workspaces.forEach(function(ws) {
            container.appendChild(createWorkspaceCard(ws));
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
        '<div class="card-image placeholder">+</div>' +
        '<div class="card-body"><span class="card-name">New workspace</span></div>';
    card.addEventListener("click", function() {
        backend.create_workspace();
    });
    return card;
}

function createWorkspaceCard(ws) {
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

    let badges = "";
    if (ws.is_default) badges += '<span class="card-badge">Default</span>';

    card.innerHTML =
        imageHtml +
        '<div class="card-body">' +
            badges +
            '<span class="card-name">' + escapeHtml(ws.name) + '</span>' +
        '</div>';

    card.addEventListener("click", function(e) {
        selectCard(card);
        showWorkspaceDetails(ws);
    });
    card.addEventListener("dblclick", function() {
        backend.open_workspace(ws.directory);
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
        imageHtml +
        '<div class="card-body">' +
            '<span class="card-name">' + escapeHtml(ex.name) + '</span>' +
            tagsHtml +
        '</div>';

    card.addEventListener("click", function() {
        selectCard(card);
        showExampleDetails(ex);
    });
    card.addEventListener("dblclick", function() {
        backend.open_example(ex.directory);
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
        '<div class="card-image placeholder">' + icon + '</div>' +
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

function showWorkspaceDetails(ws) {
    const panel = document.getElementById("details-panel");
    document.getElementById("details-title").textContent = "Workspace details";

    const content = document.getElementById("details-content");
    content.innerHTML =
        '<div class="details-field"><label>Name</label><span>' + escapeHtml(ws.name) + '</span></div>' +
        '<div class="details-field"><label>Last used</label><span>' + escapeHtml(ws.last_used) + '</span></div>' +
        '<div class="details-field"><label>Last modified</label><span>' + escapeHtml(ws.last_modified) + '</span></div>' +
        '<div class="details-field"><label>Description</label><span>' + escapeHtml(ws.description || "") + '</span></div>' +
        '<div class="details-actions">' +
            '<button onclick="backend.open_workspace(\'' + escapeAttr(ws.directory) + '\')">Open workspace</button>' +
            '<button onclick="backend.duplicate_workspace(\'' + escapeAttr(ws.directory) + '\')">Duplicate workspace</button>' +
            (ws.is_default ? '' :
                '<button class="danger" onclick="confirmDelete(\'' + escapeAttr(ws.directory) + '\', \'' + escapeAttr(ws.name) + '\')">Delete workspace</button>') +
        '</div>';

    panel.classList.remove("hidden");
    panel.classList.add("visible");
}

function showExampleDetails(ex) {
    const panel = document.getElementById("details-panel");
    document.getElementById("details-title").textContent = "Example details";

    const content = document.getElementById("details-content");
    content.innerHTML =
        '<div class="details-field"><label>Name</label><span>' + escapeHtml(ex.name) + '</span></div>' +
        '<div class="details-field"><label>Description</label><span>' + escapeHtml(ex.description || "") + '</span></div>' +
        '<div class="details-actions">' +
            '<button onclick="backend.open_example(\'' + escapeAttr(ex.directory) + '\')">Open example</button>' +
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

// --- Utilities ---

function escapeHtml(str) {
    var div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

function escapeAttr(str) {
    return str.replace(/\\/g, "\\\\").replace(/'/g, "\\'");
}

// --- Start ---
init();
