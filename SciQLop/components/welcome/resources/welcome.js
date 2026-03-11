let backend = null;
let selectedCard = null;

// --- Initialization ---

function init() {
    new QWebChannel(qt.webChannelTransport, function(channel) {
        backend = channel.objects.backend;
        loadQuickstart();
        loadWorkspaces();
        loadExamples();

        backend.workspace_list_changed.connect(loadWorkspaces);
        backend.quickstart_changed.connect(loadQuickstart);
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
    document.getElementById("sections").classList.add("with-details");
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
    document.getElementById("sections").classList.add("with-details");
}

function hideDetails() {
    const panel = document.getElementById("details-panel");
    panel.classList.remove("visible");
    panel.classList.add("hidden");
    document.getElementById("sections").classList.remove("with-details");
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
    const wsFilter = document.getElementById("workspace-filter");
    if (wsFilter) {
        wsFilter.addEventListener("input", function() {
            filterCards("workspace-cards", this.value);
        });
    }
    const exFilter = document.getElementById("example-filter");
    if (exFilter) {
        exFilter.addEventListener("input", function() {
            filterCards("example-cards", this.value);
        });
    }

    document.getElementById("sections").addEventListener("click", function(e) {
        if (!e.target.closest(".card, .shortcut-card")) {
            hideDetails();
        }
    });
});

function filterCards(containerId, query) {
    query = query.toLowerCase();
    const container = document.getElementById(containerId);
    const cards = container.querySelectorAll(".card");
    cards.forEach(function(card) {
        const name = card.dataset.name || "";
        const tags = card.dataset.tags || "";
        const match = !query || name.includes(query) || tags.includes(query);
        card.style.display = match ? "" : "none";
    });
}

// --- Utilities ---

function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

function escapeAttr(str) {
    return str.replace(/\\/g, "\\\\").replace(/'/g, "\\'");
}

// --- Start ---
init();
