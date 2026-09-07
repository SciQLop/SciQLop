var backend = null;
var allPackages = [];
var installedVersions = {};
var activeTags = new Set();
var activePage = "explore";
var activeSort = "stars";
var heroTimer = null;
var heroIndex = 0;

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

// Split on ".", compare each segment numerically if both sides are numeric,
// else as strings; a missing segment counts as 0. Returns <0, 0 or >0.
function compareVersions(a, b) {
    var partsA = String(a).split(".");
    var partsB = String(b).split(".");
    var len = Math.max(partsA.length, partsB.length);
    for (var i = 0; i < len; i++) {
        var pa = partsA[i] || "0";
        var pb = partsB[i] || "0";
        var na = parseInt(pa, 10), nb = parseInt(pb, 10);
        var cmp = (String(na) === pa && String(nb) === pb) ? na - nb : (pa < pb ? -1 : pa > pb ? 1 : 0);
        if (cmp !== 0) return cmp;
    }
    return 0;
}

function installStatus(pkg) {
    var installed = installedVersions[pkg.name];
    if (!installed) return "not-installed";
    var versions = pkg.versions || [];
    if (!versions.length) return "installed";
    var latest = versions[versions.length - 1].version;
    return compareVersions(latest, installed) > 0 ? "update-available" : "installed";
}

// --- Rendering ---

function latestVersion(pkg) {
    var versions = pkg.versions || [];
    return versions.length > 0 ? versions[versions.length - 1] : null;
}

var TYPE_ORDER = ["plugin", "workspace", "template", "example"];
var TYPE_LABEL = {plugin: "Plugins", workspace: "Workspaces", template: "Templates", example: "Examples"};

function filterPackages() {
    var query = (document.getElementById("search-input").value || "").toLowerCase();
    return allPackages.filter(function(pkg) {
        if (activeTags.size > 0) {
            var pkgTags = pkg.tags || [];
            var hasTag = false;
            activeTags.forEach(function(t) { if (pkgTags.indexOf(t) !== -1) hasTag = true; });
            if (!hasTag) return false;
        }
        if (query) {
            var text = (pkg.name + " " + pkg.description + " " + (pkg.tags || []).join(" ")).toLowerCase();
            if (text.indexOf(query) === -1) return false;
        }
        return true;
    });
}

function sortPackages(list) {
    return list.slice().sort(function(a, b) {
        if (activeSort === "stars") return (b.stars || 0) - (a.stars || 0);
        return a.name.localeCompare(b.name);
    });
}

function appendTiles(container, list) {
    sortPackages(list).forEach(function(pkg) { container.appendChild(createTile(pkg)); });
}

function renderSection(container, type, list) {
    if (list.length === 0) return;
    var head = document.createElement("div");
    head.className = "section-h";
    head.innerHTML = '<h4>' + escapeHtml(TYPE_LABEL[type] || type) + '</h4>' +
        '<span>' + list.length + ' available</span>';
    container.appendChild(head);
    var grid = document.createElement("div");
    grid.className = "cards-grid";
    appendTiles(grid, list);
    container.appendChild(grid);
}

// --- Hero banner ---

function featuredPackages() {
    return allPackages.filter(function(p) { return cardImageUrl(p); });
}

function heroActionLabel(status) {
    if (status === "installed") return "Installed ✓";
    if (status === "update-available") return "Update";
    return "Install";
}

function renderHero() {
    var host = document.getElementById("hero");
    if (heroTimer) { clearInterval(heroTimer); heroTimer = null; }
    var query = (document.getElementById("search-input").value || "");
    var feat = featuredPackages();
    if (query || activePage !== "explore" || feat.length === 0) { host.innerHTML = ""; return; }

    heroIndex = heroIndex % feat.length;
    drawHero(host, feat);
    if (feat.length > 1) {
        heroTimer = setInterval(function() {
            heroIndex = (heroIndex + 1) % feat.length;
            drawHero(host, feat);
        }, 6000);
    }
}

function drawHero(host, feat) {
    var pkg = feat[heroIndex];
    var status = installStatus(pkg);
    var dots = feat.map(function(_, i) {
        return '<i class="' + (i === heroIndex ? "on" : "") + '" data-i="' + i + '"></i>';
    }).join("");
    host.innerHTML =
        '<div class="hero">' +
            '<img src="' + escapeAttr(cardImageUrl(pkg)) + '">' +
            '<div class="hero-veil"></div>' +
            '<div class="hero-meta">' +
                '<span class="hero-kick">Featured</span>' +
                '<h3>' + escapeHtml(pkg.name) + '</h3>' +
                '<p>' + escapeHtml(pkg.description || "") + '</p>' +
                '<button class="hero-btn">' + heroActionLabel(status) + '</button>' +
            '</div>' +
            '<div class="hero-dots">' + dots + '</div>' +
        '</div>';

    host.querySelector(".hero").addEventListener("click", function(e) {
        if (e.target.closest(".hero-dots")) return;
        showPackageDetails(pkg);
    });
    host.querySelectorAll(".hero-dots i").forEach(function(dot) {
        dot.addEventListener("click", function(e) {
            e.stopPropagation();
            heroIndex = parseInt(dot.dataset.i, 10);
            renderHero();
        });
    });
}

function renderCards() {
    var query = (document.getElementById("search-input").value || "").toLowerCase();
    var flat = activePage !== "explore" || !!query;
    var sortSel = document.getElementById("sort-select");
    var chips = document.getElementById("tag-chips");
    if (sortSel) sortSel.style.display = flat ? "" : "none";
    if (chips) chips.style.display = flat ? "" : "none";
    var container = document.getElementById("package-cards");
    container.innerHTML = "";
    renderHero();
    updateUpdatesCount();

    if (activePage === "installed") {
        container.className = "cards-grid";
        appendTiles(container, pageSubset(filterPackages()));
        emptyStateIfNeeded(container, "No plugins installed yet.");
        return;
    }
    if (activePage === "updates") {
        container.className = "cards-grid";
        appendTiles(container, pageSubset(filterPackages()));
        emptyStateIfNeeded(container, "Everything is up to date.");
        return;
    }
    // explore
    if (query) {
        container.className = "cards-grid";
        appendTiles(container, filterPackages());
        return;
    }
    container.className = "sections";
    var filtered = filterPackages();
    TYPE_ORDER.forEach(function(type) {
        renderSection(container, type, filtered.filter(function(p) { return (p.type || "plugin") === type; }));
    });
    emptyStateIfNeeded(container, "No plugins available.");
}

function pageSubset(list) {
    return list.filter(function(pkg) {
        var status = installStatus(pkg);
        if (activePage === "installed") return status !== "not-installed";
        if (activePage === "updates") return status === "update-available";
        return true;
    });
}

function emptyStateIfNeeded(container, message) {
    if (container.children.length > 0) return;
    container.className = "empty-state";
    container.innerHTML = '<p>' + escapeHtml(message) + '</p>';
}

function updateUpdatesCount() {
    var n = allPackages.filter(function(p) { return installStatus(p) === "update-available"; }).length;
    var el = document.getElementById("updates-count");
    if (el) el.textContent = n > 0 ? "(" + n + ")" : "";
}

// --- Tile creation ---

// Deterministic hue 0-359 from the entry name, so an image-less tile always
// gets the same color and tiles look intentional rather than broken.
function tileHue(name) {
    var h = 0;
    for (var i = 0; i < name.length; i++) {
        h = (h * 31 + name.charCodeAt(i)) % 360;
    }
    return h;
}

function placeholderTile(pkg) {
    var hue = tileHue(pkg.name || "?");
    var initial = (pkg.name || "?").trim().charAt(0).toUpperCase();
    return '<div class="tile-shot placeholder" style="background:linear-gradient(135deg,' +
        'hsl(' + hue + ',38%,32%),hsl(' + ((hue + 40) % 360) + ',32%,18%))">' +
        escapeHtml(initial) + '</div>';
}

function tileShot(pkg) {
    var url = cardImageUrl(pkg);
    if (!url) return placeholderTile(pkg);
    return '<div class="tile-shot"><img src="' + escapeAttr(url) + '"></div>';
}

function statusBadgeHtml(status) {
    if (status === "installed") return '<span class="status-badge installed">Installed</span>';
    if (status === "update-available") return '<span class="status-badge update">Update</span>';
    return "";
}

function createTile(pkg) {
    var tile = document.createElement("div");
    tile.className = "tile";
    tile.dataset.name = (pkg.name || "").toLowerCase();

    var status = installStatus(pkg);
    var latest = latestVersion(pkg);
    var versionStr = latest ? latest.version : "";
    var starsHtml = pkg.stars != null ? "\u2605 " + pkg.stars : "\u2605 \u2014";
    var footer = [starsHtml, pkg.license || "\u2014", versionStr ? "v" + versionStr : ""]
        .filter(Boolean)
        .map(function(s) { return '<span>' + escapeHtml(s) + '</span>'; })
        .join("");

    tile.innerHTML =
        tileShot(pkg) +
        '<div class="tile-body">' +
            '<div class="tile-name">' + escapeHtml(pkg.name) + statusBadgeHtml(status) + '</div>' +
            '<div class="tile-sum">' + escapeHtml(pkg.description || "") + '</div>' +
            '<div class="tile-ft">' + footer + '</div>' +
        '</div>';

    var img = tile.querySelector(".tile-shot img");
    if (img) {
        img.addEventListener("error", function() {
            tile.querySelector(".tile-shot").outerHTML = placeholderTile(pkg);
        });
    }

    tile.addEventListener("click", function() { showPackageDetails(pkg); });
    return tile;
}

// --- Carousel ---

function renderCarousel(urls) {
    if (urls.length === 0) return "";
    var slides = urls.map(function(u, i) {
        return '<img class="carousel-slide' + (i === 0 ? ' active' : '') +
               '" src="' + escapeAttr(u) + '">';
    }).join("");
    var nav = "";
    var dots = "";
    if (urls.length > 1) {
        nav = '<button class="carousel-arrow prev" data-dir="-1" aria-label="Previous">‹</button>' +
              '<button class="carousel-arrow next" data-dir="1" aria-label="Next">›</button>';
        dots = '<div class="carousel-dots">' + urls.map(function(u, i) {
            return '<span class="carousel-dot' + (i === 0 ? ' active' : '') + '"></span>';
        }).join("") + '</div>';
    }
    return '<div class="carousel" id="carousel">' +
               '<div class="carousel-viewport">' + slides + nav + '</div>' +
               dots +
           '</div>';
}

function initCarousel(root) {
    var carousel = root.querySelector("#carousel");
    if (!carousel) return;
    var slides = carousel.querySelectorAll(".carousel-slide");
    var dots = carousel.querySelectorAll(".carousel-dot");
    var current = 0;

    function show(i) {
        if (slides.length === 0) return;
        current = (i + slides.length) % slides.length;
        slides.forEach(function(s, idx) { s.classList.toggle("active", idx === current); });
        dots.forEach(function(d, idx) { d.classList.toggle("active", idx === current); });
    }

    function dropSlide(slide) {
        slide.remove();
        // Dots are positional indicators; drop one (the last) to keep dot
        // count == slide count, robust to any number/order of failures.
        var allDots = carousel.querySelectorAll(".carousel-dot");
        if (allDots.length > 0) allDots[allDots.length - 1].remove();
        slides = carousel.querySelectorAll(".carousel-slide");
        dots = carousel.querySelectorAll(".carousel-dot");
        if (slides.length === 0) {
            carousel.style.display = "none";
            return;
        }
        if (slides.length === 1) {
            carousel.querySelectorAll(".carousel-arrow").forEach(function(a) { a.style.display = "none"; });
            var dotsWrap = carousel.querySelector(".carousel-dots");
            if (dotsWrap) dotsWrap.style.display = "none";
        }
        show(Math.min(current, slides.length - 1));
    }

    carousel.querySelectorAll(".carousel-arrow").forEach(function(btn) {
        btn.addEventListener("click", function(e) {
            e.stopPropagation();
            show(current + parseInt(btn.dataset.dir, 10));
        });
    });
    dots.forEach(function(dot, idx) {
        dot.addEventListener("click", function() { show(idx); });
    });
    slides.forEach(function(slide) {
        slide.addEventListener("click", function() { openLightbox(slide.src); });
        slide.addEventListener("error", function() { dropSlide(slide); });
    });
}

// --- Detail page ---

var detailReturnScroll = 0;
var currentDetailPkg = null;

function detailThumbsHtml(urls) {
    if (urls.length < 2) return "";
    var items = urls.map(function(u, i) {
        return '<div class="detail-thumb' + (i === 0 ? ' on' : '') + '" data-i="' + i +
            '"><img src="' + escapeAttr(u) + '"></div>';
    }).join("");
    return '<div class="detail-thumbs">' + items + '</div>';
}

function factRow(label, value) {
    return '<div class="detail-fact"><label>' + escapeHtml(label) + '</label><span>' + value + '</span></div>';
}

function detailActionsHtml(pkg, status, latest) {
    var name = escapeAttr(pkg.name);
    if (!latest) return "";
    var ver = escapeHtml(latest.version);
    if (status === "installed") {
        return '<button class="detail-btn installed" disabled>Installed \u2713</button>' +
            '<button class="detail-btn uninstall" id="uninstall-btn" data-name="' + name + '">Uninstall</button>';
    }
    if (status === "update-available") {
        return '<button class="detail-btn update" id="install-btn" data-name="' + name + '">Update to v' + ver + '</button>' +
            '<button class="detail-btn uninstall" id="uninstall-btn" data-name="' + name + '">Uninstall</button>';
    }
    return '<button class="detail-btn install" id="install-btn" data-name="' + name + '">Install</button>';
}

function showPackageDetails(pkg) {
    currentDetailPkg = pkg;
    var type = pkg.type || "plugin";
    var latest = latestVersion(pkg);
    var versionStr = latest ? latest.version : "\u2014";
    var compatStr = latest && latest.sciqlop ? latest.sciqlop : "\u2014";
    var status = installStatus(pkg);
    var installedVer = installedVersions[pkg.name] || null;
    var shots = screenshotUrls(pkg);
    var tagsHtml = (pkg.tags || []).join(" \u00B7 ") || "\u2014";
    var starsHtml = pkg.stars != null ? "\u2605 " + pkg.stars : "\u2014";

    var carousel = shots.length > 0
        ? renderCarousel(shots) + detailThumbsHtml(shots)
        : '<div class="detail-noshot">' + escapeHtml((pkg.name || "?").charAt(0).toUpperCase()) + '</div>';

    var facts = factRow("Type", '<span class="card-badge">' + escapeHtml(type) + '</span>') +
        factRow("Author", escapeHtml(pkg.author || "\u2014")) +
        factRow("License", escapeHtml(pkg.license || "\u2014")) +
        factRow("Version", escapeHtml(versionStr)) +
        (installedVer ? factRow("Installed", "v" + escapeHtml(installedVer)) : "") +
        factRow("Requires", "SciQLop " + escapeHtml(compatStr)) +
        factRow("Stars", escapeHtml(starsHtml)) +
        factRow("Tags", escapeHtml(tagsHtml));

    document.getElementById("detail-content").innerHTML =
        '<div class="detail-grid">' +
            '<div class="detail-media">' + carousel + '</div>' +
            '<div class="detail-side">' +
                '<h2>' + escapeHtml(pkg.name) + '</h2>' +
                '<div class="detail-author">by ' + escapeHtml(pkg.author || "\u2014") + '</div>' +
                '<div class="detail-actions">' + detailActionsHtml(pkg, status, latest) + '</div>' +
                '<div class="detail-facts">' + facts + '</div>' +
            '</div>' +
            '<div class="detail-desc">' + escapeHtml(pkg.description || "") + '</div>' +
        '</div>';

    wireDetailActions();
    initCarousel(document.getElementById("detail-content"));
    initDetailThumbs();
    openDetailPage();
}

function wireDetailActions() {
    var btn = document.getElementById("install-btn");
    if (btn) {
        btn.addEventListener("click", function() {
            clearInstallError();
            btn.textContent = "Installing...";
            btn.disabled = true;
            backend.install_package(btn.dataset.name);
        });
    }
    var unBtn = document.getElementById("uninstall-btn");
    if (unBtn) {
        unBtn.addEventListener("click", function() {
            clearInstallError();
            unBtn.textContent = "Uninstalling...";
            unBtn.disabled = true;
            backend.uninstall_package(unBtn.dataset.name);
        });
    }
}

function refreshDetailActions() {
    if (!currentDetailPkg) return;
    var actions = document.querySelector(".detail-actions");
    if (!actions) return;
    actions.innerHTML = detailActionsHtml(currentDetailPkg, installStatus(currentDetailPkg), latestVersion(currentDetailPkg));
    wireDetailActions();
}

function initDetailThumbs() {
    var root = document.getElementById("detail-content");
    var thumbs = root.querySelectorAll(".detail-thumb");
    thumbs.forEach(function(thumb) {
        thumb.addEventListener("click", function() {
            var i = parseInt(thumb.dataset.i, 10);
            root.querySelectorAll(".carousel-slide").forEach(function(s, idx) { s.classList.toggle("active", idx === i); });
            root.querySelectorAll(".carousel-dot").forEach(function(d, idx) { d.classList.toggle("active", idx === i); });
            thumbs.forEach(function(t, idx) { t.classList.toggle("on", idx === i); });
        });
    });
}

function openDetailPage() {
    detailReturnScroll = window.scrollY;
    document.body.classList.add("detail-open");
    document.getElementById("detail-page").classList.remove("hidden");
    window.scrollTo(0, 0);
}

function hideDetails() {
    currentDetailPkg = null;
    document.getElementById("detail-page").classList.add("hidden");
    document.body.classList.remove("detail-open");
    window.scrollTo(0, detailReturnScroll);
}

function onInstallFinished(json_str) {
    var result = JSON.parse(json_str);
    if (result.ok && result.version) {
        installedVersions[result.name] = result.version;
    }
    renderCards();
    if (result.ok) {
        refreshDetailActions();
        if (result.loaded === false) {
            showInstallError("Installed, but not loaded: " + result.reason);
        } else {
            clearInstallError();
        }
        return;
    }
    var btn = document.getElementById("install-btn");
    if (!btn) return;
    btn.textContent = "Failed";
    btn.disabled = false;
    showInstallError(result.error);
}

function clearInstallError() {
    var box = document.getElementById("install-error");
    if (box) box.remove();
}

function showInstallError(message) {
    clearInstallError();
    if (!message) return;
    var actions = document.querySelector(".detail-actions");
    if (!actions) return;
    var box = document.createElement("pre");
    box.id = "install-error";
    box.className = "install-error";
    box.textContent = message;
    actions.parentNode.insertBefore(box, actions.nextSibling);
}

function onUninstallFinished(json_str) {
    var result = JSON.parse(json_str);
    if (result.ok) {
        delete installedVersions[result.name];
    }
    renderCards();
    if (result.ok) {
        clearInstallError();
        refreshDetailActions();
        return;
    }
    var unBtn = document.getElementById("uninstall-btn");
    if (!unBtn) return;
    unBtn.textContent = "Failed";
    unBtn.disabled = false;
    showInstallError(result.error);
}

function openLightbox(src) {
    var lb = document.getElementById("lightbox");
    document.getElementById("lightbox-img").src = src;
    lb.classList.remove("hidden");
}

function closeLightbox() {
    var lb = document.getElementById("lightbox");
    lb.classList.add("hidden");
    document.getElementById("lightbox-img").src = "";
}

// --- Event listeners ---

document.addEventListener("DOMContentLoaded", function() {
    document.querySelectorAll(".page-btn").forEach(function(btn) {
        btn.addEventListener("click", function() {
            document.querySelector(".page-btn.active").classList.remove("active");
            btn.classList.add("active");
            activePage = btn.dataset.page;
            hideDetails();
            renderCards();
            window.scrollTo(0, 0);
        });
    });

    document.getElementById("search-input").addEventListener("input", function() {
        renderCards();
    });

    document.getElementById("sort-select").addEventListener("change", function() {
        activeSort = this.value;
        renderCards();
    });

    document.getElementById("detail-back").addEventListener("click", hideDetails);

    document.getElementById("lightbox").addEventListener("click", closeLightbox);

    document.addEventListener("keydown", function(e) {
        if (e.key !== "Escape") return;
        var lb = document.getElementById("lightbox");
        if (lb && !lb.classList.contains("hidden")) {
            closeLightbox();
            return;
        }
        hideDetails();
    });

    document.body.addEventListener("click", function(e) {
        if (!e.target.closest(".tile, #detail-page, #lightbox, .tag-chip, .page-btn, #toolbar, #hero")) {
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

function escapeAttr(str) {
    return escapeHtml(str).replace(/"/g, "&quot;");
}

// Card thumbnail: explicit image, else first screenshot, else null (emoji).
function cardImageUrl(pkg) {
    if (pkg.image) return pkg.image;
    var shots = pkg.screenshots || [];
    return shots.length > 0 ? shots[0] : null;
}

// Carousel list: screenshots if any, else the single image, else empty.
function screenshotUrls(pkg) {
    var shots = pkg.screenshots || [];
    if (shots.length > 0) return shots.slice();
    return pkg.image ? [pkg.image] : [];
}

// --- Start ---
init();
