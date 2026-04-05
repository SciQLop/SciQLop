var backend = null;
var selectedCard = null;
var allPackages = [];
var installedVersions = {};
var activeTags = new Set();
var activeCategory = "";
var activeSort = "stars";

var TYPE_ICONS = {plugin: "\uD83D\uDD0C", workspace: "\uD83D\uDCC1", template: "\uD83D\uDCC4", example: "\uD83D\uDCD6"};

// --- Initialization ---

function init() {
    new QWebChannel(qt.webChannelTransport, function(channel) {
        backend = channel.objects.backend;
        backend.packages_ready.connect(onPackagesReady);
        backend.install_finished.connect(onInstallFinished);
        backend.uninstall_finished.connect(onUninstallFinished);
        backend.fetch_packages();
    });
}

// --- Data loading ---

function onPackagesReady(json_str) {
    allPackages = JSON.parse(json_str);
    document.getElementById("loading").style.display = "none";
    refreshInstalledVersions();
    loadTags();
}

function refreshInstalledVersions() {
    backend.get_installed_versions(function(json_str) {
        installedVersions = JSON.parse(json_str);
        renderCards();
    });
}

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

// --- Install status helpers ---

function installStatus(pkg) {
    var installed = installedVersions[pkg.name];
    if (!installed) return "not-installed";
    var versions = pkg.versions || [];
    if (!versions.length) return "installed";
    var latest = versions[versions.length - 1].version;
    return installed === latest ? "installed" : "update-available";
}

function statusLabel(status, installedVer) {
    if (status === "installed") return "Installed \u2713";
    if (status === "update-available") return "Update (v" + installedVer + " installed)";
    return "";
}

// --- Rendering ---

function latestVersion(pkg) {
    var versions = pkg.versions || [];
    return versions.length > 0 ? versions[versions.length - 1] : null;
}

function renderCards() {
    var query = (document.getElementById("search-input").value || "").toLowerCase();
    var container = document.getElementById("package-cards");
    container.innerHTML = "";

    var filtered = allPackages.filter(function(pkg) {
        var type = pkg.type || "plugin";
        if (activeCategory && type !== activeCategory) return false;

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
        if (activeSort === "stars") return (b.stars || 0) - (a.stars || 0);
        return a.name.localeCompare(b.name);
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

    var type = pkg.type || "plugin";
    var icon = TYPE_ICONS[type] || "\uD83D\uDCE6";
    var latest = latestVersion(pkg);
    var versionStr = latest ? latest.version : "";
    var starsHtml = pkg.stars != null ? "\u2B50 " + pkg.stars : "";

    var status = installStatus(pkg);
    var badgeHtml = "";
    if (status === "installed") {
        badgeHtml = '<span class="status-badge installed">Installed</span>';
    } else if (status === "update-available") {
        badgeHtml = '<span class="status-badge update">Update available</span>';
    }

    card.innerHTML =
        '<div class="card-image-wrapper"><div class="card-image placeholder">' + icon + '</div></div>' +
        '<div class="card-body">' +
            '<span class="card-badge">' + escapeHtml(type) + '</span>' +
            badgeHtml +
            '<span class="card-name">' + escapeHtml(pkg.name) + '</span>' +
            '<div class="card-meta">' + escapeHtml(pkg.author) +
                (versionStr ? ' \u00B7 v' + escapeHtml(versionStr) : '') +
                (starsHtml ? ' \u00B7 ' + starsHtml : '') +
            '</div>' +
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

    var type = pkg.type || "plugin";
    var latest = latestVersion(pkg);
    var versionStr = latest ? latest.version : "\u2014";
    var compatStr = latest ? latest.sciqlop : "\u2014";
    var status = installStatus(pkg);
    var installedVer = installedVersions[pkg.name] || null;

    var tagsHtml = (pkg.tags || []).map(function(t) {
        return '<span class="card-badge">' + escapeHtml(t) + '</span>';
    }).join(" ");

    var starsHtml = pkg.stars != null ? '\u2B50 ' + pkg.stars : "\u2014";

    var installedHtml = "";
    if (installedVer) {
        installedHtml = '<div class="details-field"><label>Installed</label><span>v' + escapeHtml(installedVer) + '</span></div>';
    }

    var buttonHtml = "";
    if (latest) {
        if (status === "installed") {
            buttonHtml = '<button class="install installed" disabled>Installed \u2713</button>' +
                '<button class="install uninstall" id="uninstall-btn" data-name="' + escapeHtml(pkg.name) + '">Uninstall</button>';
        } else if (status === "update-available") {
            buttonHtml = '<button class="install update" id="install-btn" data-name="' + escapeHtml(pkg.name) + '">Update to v' + escapeHtml(versionStr) + '</button>' +
                '<button class="install uninstall" id="uninstall-btn" data-name="' + escapeHtml(pkg.name) + '">Uninstall</button>';
        } else {
            buttonHtml = '<button class="install" id="install-btn" data-name="' + escapeHtml(pkg.name) + '">Install</button>';
        }
    }

    var content = document.getElementById("details-content");
    content.innerHTML =
        '<div class="details-field"><label>Type</label><span><span class="card-badge">' + escapeHtml(type) + '</span></span></div>' +
        '<div class="details-field"><label>Author</label><span>' + escapeHtml(pkg.author) + '</span></div>' +
        '<div class="details-field"><label>License</label><span>' + escapeHtml(pkg.license || "\u2014") + '</span></div>' +
        '<div class="details-field"><label>Version</label><span>' + escapeHtml(versionStr) + '</span></div>' +
        installedHtml +
        (latest ? '<div class="details-field"><label>Requires</label><span>SciQLop ' + escapeHtml(compatStr) + '</span></div>' : '') +
        '<div class="details-field"><label>Description</label><span>' + escapeHtml(pkg.description) + '</span></div>' +
        '<div class="details-field"><label>Tags</label><span>' + tagsHtml + '</span></div>' +
        '<div class="details-field"><label>Stars</label><span>' + starsHtml + '</span></div>' +
        '<div class="details-actions">' + buttonHtml + '</div>';

    var btn = document.getElementById("install-btn");
    if (btn) {
        btn.addEventListener("click", function() {
            btn.textContent = "Installing...";
            btn.disabled = true;
            backend.install_package(btn.dataset.name);
        });
    }

    var unBtn = document.getElementById("uninstall-btn");
    if (unBtn) {
        unBtn.addEventListener("click", function() {
            unBtn.textContent = "Uninstalling...";
            unBtn.disabled = true;
            backend.uninstall_package(unBtn.dataset.name);
        });
    }

    panel.classList.remove("hidden");
    panel.classList.add("visible");
}

function onInstallFinished(json_str) {
    var result = JSON.parse(json_str);
    if (result.ok && result.version) {
        installedVersions[result.name] = result.version;
    }
    renderCards();
    var btn = document.getElementById("install-btn");
    if (!btn) return;
    if (result.ok) {
        btn.textContent = "Installed \u2713";
        btn.className = "install installed";
        btn.disabled = true;
    } else {
        btn.textContent = "Failed";
        btn.disabled = false;
    }
}

function onUninstallFinished(json_str) {
    var result = JSON.parse(json_str);
    if (result.ok) {
        delete installedVersions[result.name];
    }
    renderCards();
    var unBtn = document.getElementById("uninstall-btn");
    if (!unBtn) return;
    if (result.ok) {
        unBtn.textContent = "Uninstalled";
        unBtn.disabled = true;
    } else {
        unBtn.textContent = "Failed";
        unBtn.disabled = false;
    }
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
    document.querySelectorAll(".tab").forEach(function(tab) {
        tab.addEventListener("click", function() {
            document.querySelector(".tab.active").classList.remove("active");
            tab.classList.add("active");
            activeCategory = tab.dataset.category;
            renderCards();
        });
    });

    document.getElementById("search-input").addEventListener("input", function() {
        renderCards();
    });

    document.getElementById("sort-select").addEventListener("change", function() {
        activeSort = this.value;
        renderCards();
    });

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
