let backend = null;
let selectedCard = null;
let allPackages = [];
let activeTags = new Set();
let activeCategory = "";
let activeSort = "stars";

var TYPE_ICONS = {plugin: "\uD83D\uDD0C", workspace: "\uD83D\uDCC1", example: "\uD83D\uDCD6"};

// --- Initialization ---

function init() {
    new QWebChannel(qt.webChannelTransport, function(channel) {
        backend = channel.objects.backend;
        loadTags();
        loadPackages();
    });
}

// --- Data loading ---

function loadTags() {
    backend.list_tags(function(json_str) {
        var tags = JSON.parse(json_str);
        var container = document.getElementById("tag-chips");
        container.innerHTML = "";
        tags.forEach(function(tag) {
            var chip = document.createElement("span");
            chip.className = "tag-chip";
            chip.textContent = tag;
            chip.dataset.tag = tag;
            chip.addEventListener("click", function() {
                if (activeTags.has(tag)) {
                    activeTags.delete(tag);
                    chip.classList.remove("active");
                } else {
                    activeTags.add(tag);
                    chip.classList.add("active");
                }
                renderCards();
            });
            container.appendChild(chip);
        });
    });
}

function loadPackages() {
    backend.list_packages("", function(json_str) {
        allPackages = JSON.parse(json_str);
        renderCards();
    });
}

// --- Rendering ---

function renderCards() {
    var query = (document.getElementById("search-input").value || "").toLowerCase();
    var container = document.getElementById("package-cards");
    container.innerHTML = "";

    var filtered = allPackages.filter(function(pkg) {
        if (activeCategory && pkg.type !== activeCategory) return false;

        if (activeTags.size > 0) {
            var pkgTags = pkg.tags || [];
            var hasTag = false;
            activeTags.forEach(function(t) {
                if (pkgTags.indexOf(t) !== -1) hasTag = true;
            });
            if (!hasTag) return false;
        }

        if (query) {
            var text = (pkg.name + " " + pkg.description + " " + (pkg.tags || []).join(" ")).toLowerCase();
            if (text.indexOf(query) === -1) return false;
        }

        return true;
    });

    filtered.sort(function(a, b) {
        if (activeSort === "stars") return b.stars - a.stars;
        if (activeSort === "name") return a.name.localeCompare(b.name);
        return 0;
    });

    filtered.forEach(function(pkg) {
        container.appendChild(createPackageCard(pkg));
    });
}

// --- Card creation ---

function createPackageCard(pkg) {
    var card = document.createElement("div");
    card.className = "card";
    card.dataset.name = pkg.name.toLowerCase();
    card.dataset.tags = (pkg.tags || []).join(" ").toLowerCase();

    var icon = TYPE_ICONS[pkg.type] || "\uD83D\uDCE6";
    card.innerHTML =
        '<div class="card-image-wrapper"><div class="card-image placeholder">' + icon + '</div></div>' +
        '<div class="card-body">' +
            '<span class="card-badge">' + escapeHtml(pkg.type) + '</span>' +
            '<span class="card-name">' + escapeHtml(pkg.name) + '</span>' +
            '<div class="card-stars">\u2B50 ' + pkg.stars + ' &middot; ' + pkg.downloads + ' downloads</div>' +
        '</div>';

    card.addEventListener("click", function() {
        selectCard(card);
        showPackageDetails(pkg);
    });
    return card;
}

// --- Details panel ---

function showPackageDetails(pkg) {
    var panel = document.getElementById("details-panel");
    document.getElementById("details-title").textContent = pkg.name;

    var tagsHtml = (pkg.tags || []).map(function(t) {
        return '<span class="card-badge">' + escapeHtml(t) + '</span>';
    }).join(" ");

    var content = document.getElementById("details-content");
    content.innerHTML =
        '<div class="details-field"><label>Type</label><span><span class="card-badge">' + escapeHtml(pkg.type) + '</span></span></div>' +
        '<div class="details-field"><label>Author</label><span>' + escapeHtml(pkg.author) + '</span></div>' +
        '<div class="details-field"><label>Version</label><span>' + escapeHtml(pkg.version) + '</span></div>' +
        '<div class="details-field"><label>Description</label><span>' + escapeHtml(pkg.description) + '</span></div>' +
        '<div class="details-field"><label>Tags</label><span>' + tagsHtml + '</span></div>' +
        '<div class="details-field"><label>Stars</label><span>\u2B50 ' + pkg.stars + '</span></div>' +
        '<div class="details-field"><label>Downloads</label><span>' + pkg.downloads + '</span></div>' +
        '<div class="details-actions">' +
            '<button class="install">Install (coming soon)</button>' +
        '</div>';

    panel.classList.remove("hidden");
    panel.classList.add("visible");
}

function hideDetails() {
    var panel = document.getElementById("details-panel");
    panel.classList.remove("visible");
    panel.classList.add("hidden");
    if (selectedCard) {
        selectedCard.classList.remove("selected");
        selectedCard = null;
    }
}

// --- Selection ---

function selectCard(card) {
    if (selectedCard) selectedCard.classList.remove("selected");
    selectedCard = card;
    card.classList.add("selected");
}

// --- Event listeners ---

document.addEventListener("DOMContentLoaded", function() {
    // Tab switching
    document.querySelectorAll(".tab").forEach(function(tab) {
        tab.addEventListener("click", function() {
            document.querySelector(".tab.active").classList.remove("active");
            tab.classList.add("active");
            activeCategory = tab.dataset.category;
            renderCards();
        });
    });

    // Search
    document.getElementById("search-input").addEventListener("input", function() {
        renderCards();
    });

    // Sort
    document.getElementById("sort-select").addEventListener("change", function() {
        activeSort = this.value;
        renderCards();
    });

    // Click outside to deselect
    document.body.addEventListener("click", function(e) {
        if (!e.target.closest(".card, #details-panel, .tag-chip, .tab, #toolbar")) {
            hideDetails();
        }
    });
});

// --- Utilities ---

function escapeHtml(str) {
    var div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

// --- Start ---
init();
