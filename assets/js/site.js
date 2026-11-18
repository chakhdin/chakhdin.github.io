const pageCache = new Map();

function selectVersion(id, updateHash) {
    const tabs = [...document.querySelectorAll('[data-version-tab]')];
    if (!tabs.length) return;
    const first = tabs[0].dataset.versionTab;
    if (!tabs.some((tab) => tab.dataset.versionTab === id)) id = first;

    tabs.forEach((tab) => {
        const selected = tab.dataset.versionTab === id;
        tab.setAttribute('aria-selected', String(selected));
        tab.tabIndex = selected ? 0 : -1;
    });
    document.querySelectorAll('[data-version]').forEach((el) => {
        el.hidden = el.dataset.version !== id;
    });

    if (updateHash) {
        const url = id === first ? location.pathname + location.search : '#' + encodeURIComponent(id);
        history.replaceState(history.state, '', url);
    }
}

function initMedia() {
    document.body.style.overflow = '';

    const tabs = [...document.querySelectorAll('[data-version-tab]')];
    tabs.forEach((tab, i) => {
        tab.addEventListener('click', () => selectVersion(tab.dataset.versionTab, true));
        tab.addEventListener('keydown', (e) => {
            let next = null;
            if (e.key === 'ArrowRight') next = tabs[(i + 1) % tabs.length];
            else if (e.key === 'ArrowLeft') next = tabs[(i - 1 + tabs.length) % tabs.length];
            else if (e.key === 'Home') next = tabs[0];
            else if (e.key === 'End') next = tabs[tabs.length - 1];
            if (!next) return;
            e.preventDefault();
            selectVersion(next.dataset.versionTab, true);
            next.focus();
        });
    });
    selectVersion(decodeURIComponent(location.hash.slice(1)), false);

    // Neighbour pages load when their link is pointed at or focused; with a
    // mouse (arrow-key browsing) also shortly after this page has loaded.
    ['nav-next', 'nav-prev'].forEach((id) => {
        const link = document.getElementById(id);
        if (!link) return;
        const prefetch = () => prefetchPage(link.href);
        link.addEventListener('pointerenter', prefetch);
        link.addEventListener('focus', prefetch);
        if (window.matchMedia('(pointer: fine)').matches) setTimeout(prefetch, 1000);
    });

    const overlay = document.getElementById('fullscreen-overlay');
    const fullscreenImg = document.getElementById('fullscreen-image');
    if (!overlay || !fullscreenImg) return;

    document.querySelectorAll('.hero-image').forEach((img) => {
        img.addEventListener('click', (e) => {
            e.stopPropagation();
            openFullscreen(img);
        });
        // Same keys as a native button: Enter on keydown, Space on keyup (so the
        // keyup does not land on the close button and shut the viewer at once).
        img.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') { e.preventDefault(); openFullscreen(img); }
            else if (e.key === ' ') e.preventDefault();
        });
        img.addEventListener('keyup', (e) => {
            if (e.key === ' ') openFullscreen(img);
        });
    });
    const closeBtn = document.getElementById('fullscreen-close');
    if (closeBtn) closeBtn.addEventListener('click', closeFullscreen);
    initZoom(overlay, fullscreenImg);
    overlay.addEventListener('keydown', (e) => {
        // The close button is the only focusable element: keep focus on it.
        if (e.key !== 'Tab') return;
        e.preventDefault();
        const closeBtn = document.getElementById('fullscreen-close');
        if (closeBtn) closeBtn.focus();
    });
}

let fullscreenOpener = null;

function openFullscreen(img) {
    const overlay = document.getElementById('fullscreen-overlay');
    const fullscreenImg = document.getElementById('fullscreen-image');
    // data-full: a larger version than the one shown (rig photos).
    fullscreenImg.src = img.dataset.full || img.currentSrc || img.src;
    // data-zoom: the full-size file, loaded only when the viewer zooms in.
    fullscreenImg.dataset.zoom = img.dataset.zoom || img.dataset.full || img.src;
    fullscreenImg.alt = img.alt;
    resetZoom();
    overlay.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
    fullscreenOpener = img;
    const closeBtn = document.getElementById('fullscreen-close');
    if (closeBtn) closeBtn.focus();
}

function closeFullscreen() {
    const overlay = document.getElementById('fullscreen-overlay');
    if (!overlay || overlay.classList.contains('hidden')) return;
    overlay.classList.add('hidden');
    document.body.style.overflow = '';
    resetZoom();
    if (fullscreenOpener && fullscreenOpener.isConnected) fullscreenOpener.focus({ preventScroll: true });
    fullscreenOpener = null;
}

// Zoom state of the fullscreen viewer. scale is screen px per image px; null
// means fitted to the screen by the CSS classes, with no inline geometry.
const zoom = { scale: null, x: 0, y: 0, pointers: new Map(), drag: null, pinch: null, pending: null, lastTap: 0, tapTimer: 0 };
const ZOOM_MAX = 2;
const TAP_SLOP = 6;
const DOUBLE_TAP_MS = 300;

function zoomImage() {
    return document.getElementById('fullscreen-image');
}

// Scale at which the whole image fits inside the overlay padding (never above 1,
// like the max-w-full / max-h-full classes).
function fitScale(img) {
    const overlay = img.parentElement;
    const cs = getComputedStyle(overlay);
    const w = overlay.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
    const h = overlay.clientHeight - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom);
    return Math.min(1, w / img.naturalWidth, h / img.naturalHeight);
}

function needsZoomSource(img) {
    return Boolean(img.dataset.zoom) && img.getAttribute('src') !== img.dataset.zoom;
}

function canZoom(img) {
    return img.naturalWidth > 0 && (needsZoomSource(img) || fitScale(img) < 0.99);
}

function currentScale(img) {
    return zoom.scale === null ? img.getBoundingClientRect().width / img.naturalWidth : zoom.scale;
}

function applyZoom() {
    const img = zoomImage();
    if (!img) return;
    if (zoom.scale === null) {
        img.removeAttribute('style');
        img.style.cursor = canZoom(img) ? 'zoom-in' : '';
        return;
    }
    const overlay = img.parentElement;
    const vw = overlay.clientWidth;
    const vh = overlay.clientHeight;
    const w = img.naturalWidth * zoom.scale;
    const h = img.naturalHeight * zoom.scale;
    // Centre a side smaller than the screen; otherwise keep the screen covered.
    zoom.x = w <= vw ? (vw - w) / 2 : Math.min(0, Math.max(vw - w, zoom.x));
    zoom.y = h <= vh ? (vh - h) / 2 : Math.min(0, Math.max(vh - h, zoom.y));
    Object.assign(img.style, {
        position: 'absolute', left: zoom.x + 'px', top: zoom.y + 'px',
        width: w + 'px', height: h + 'px', maxWidth: 'none', maxHeight: 'none',
        cursor: zoom.drag && zoom.drag.moved ? 'grabbing' : 'grab',
    });
}

function resetZoom() {
    zoom.scale = null;
    zoom.drag = null;
    zoom.pinch = null;
    zoom.pending = null;
    zoom.pointers.clear();
    clearTimeout(zoom.tapTimer);
    applyZoom();
}

// Zooms to scale, keeping the image point under (cx, cy) in place.
function zoomAt(scale, cx, cy) {
    const img = zoomImage();
    if (!img || !img.naturalWidth) return;
    const fit = fitScale(img);
    const current = currentScale(img);
    if (zoom.scale === null) {
        const rect = img.getBoundingClientRect();
        zoom.x = rect.left;
        zoom.y = rect.top;
    }
    scale = Math.min(Math.max(ZOOM_MAX, fit), scale);
    if (scale <= fit * 1.001) { resetZoom(); return; }
    zoom.x = cx - (cx - zoom.x) * scale / current;
    zoom.y = cy - (cy - zoom.y) * scale / current;
    zoom.scale = scale;
    applyZoom();
}

// Swaps in the full-size file; until it has loaded the current one stays on screen.
function loadZoomSource(img) {
    if (!needsZoomSource(img)) return false;
    img.addEventListener('load', () => {
        if (zoom.pending) {
            const { cx, cy } = zoom.pending;
            zoom.pending = null;
            applyZoom();
            zoomAt(1, cx, cy);
        } else if (zoom.scale !== null) {
            // Same size on screen, now drawn from the larger file.
            zoom.scale = parseFloat(img.style.width) / img.naturalWidth;
            applyZoom();
        } else {
            applyZoom();
        }
    }, { once: true });
    // Missing or unreachable full-size file: go on zooming the image already shown.
    const previous = img.getAttribute('src');
    img.addEventListener('error', () => {
        img.dataset.zoom = '';
        img.src = previous;
    }, { once: true });
    img.src = img.dataset.zoom;
    return true;
}

// Fit <-> 100 % around the clicked or tapped point.
function toggleZoom(cx, cy) {
    const img = zoomImage();
    if (zoom.scale !== null) { resetZoom(); return; }
    if (loadZoomSource(img)) {
        zoom.pending = { cx, cy };
        img.style.cursor = 'progress';
        return;
    }
    zoomAt(1, cx, cy);
}

function onTap(e, img, target) {
    // Pointer capture retargets pointerup to the overlay: use the pointerdown target.
    const onImage = target === img;
    if (e.pointerType === 'mouse') {
        if (onImage && (zoom.scale !== null || canZoom(img))) toggleZoom(e.clientX, e.clientY);
        else closeFullscreen();
        return;
    }
    // Touch: a double tap zooms; a single tap closes the fitted image.
    const now = Date.now();
    if (now - zoom.lastTap < DOUBLE_TAP_MS) {
        clearTimeout(zoom.tapTimer);
        zoom.lastTap = 0;
        if (zoom.scale !== null || canZoom(img)) toggleZoom(e.clientX, e.clientY);
        return;
    }
    zoom.lastTap = now;
    zoom.tapTimer = setTimeout(() => {
        if (zoom.scale === null && !zoom.pending) closeFullscreen();
    }, DOUBLE_TAP_MS);
}

function pinchState() {
    const [a, b] = [...zoom.pointers.values()];
    return { dist: Math.hypot(a.x - b.x, a.y - b.y), cx: (a.x + b.x) / 2, cy: (a.y + b.y) / 2 };
}

function initZoom(overlay, img) {
    img.addEventListener('load', () => { if (zoom.scale === null && !zoom.pending) applyZoom(); });
    overlay.addEventListener('pointerdown', (e) => {
        if (e.target.closest('#fullscreen-close')) return;
        if (e.pointerType === 'mouse') {
            // No native image drag or text selection.
            e.preventDefault();
            if (e.button !== 0) return;
        }
        overlay.setPointerCapture(e.pointerId);
        zoom.pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
        if (zoom.pointers.size === 2) {
            loadZoomSource(img);
            zoom.pinch = { ...pinchState(), scale: currentScale(img) };
            zoom.drag = null;
        } else if (zoom.pointers.size === 1) {
            zoom.drag = { sx: e.clientX, sy: e.clientY, x0: zoom.x, y0: zoom.y, moved: false, multi: false, target: e.target };
        }
    });
    overlay.addEventListener('pointermove', (e) => {
        if (!zoom.pointers.has(e.pointerId)) return;
        zoom.pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
        if (zoom.pinch && zoom.pointers.size === 2) {
            const p = pinchState();
            zoomAt(zoom.pinch.scale * p.dist / zoom.pinch.dist, p.cx, p.cy);
            // Follow the fingers' midpoint as well.
            if (zoom.scale !== null) {
                zoom.x += p.cx - zoom.pinch.cx;
                zoom.y += p.cy - zoom.pinch.cy;
                applyZoom();
            }
            zoom.pinch.cx = p.cx;
            zoom.pinch.cy = p.cy;
            return;
        }
        const d = zoom.drag;
        if (!d) return;
        if (!d.moved && Math.hypot(e.clientX - d.sx, e.clientY - d.sy) > TAP_SLOP) {
            d.moved = true;
            d.sx = e.clientX;
            d.sy = e.clientY;
            d.x0 = zoom.x;
            d.y0 = zoom.y;
        }
        if (d.moved && zoom.scale !== null) {
            zoom.x = d.x0 + e.clientX - d.sx;
            zoom.y = d.y0 + e.clientY - d.sy;
            applyZoom();
        }
    });
    const end = (e) => {
        if (!zoom.pointers.has(e.pointerId)) return;
        zoom.pointers.delete(e.pointerId);
        const d = zoom.drag;
        if (zoom.pinch) {
            // The finger left on screen goes on panning from where it is.
            zoom.pinch = null;
            const rest = [...zoom.pointers.values()][0];
            zoom.drag = rest ? { sx: rest.x, sy: rest.y, x0: zoom.x, y0: zoom.y, moved: true, multi: true } : null;
            return;
        }
        zoom.drag = null;
        if (e.type === 'pointerup' && d && !d.moved && !d.multi) onTap(e, img, d.target);
        else applyZoom();
    };
    overlay.addEventListener('pointerup', end);
    overlay.addEventListener('pointercancel', end);
    overlay.addEventListener('wheel', (e) => {
        e.preventDefault();
        if (!img.naturalWidth || (zoom.scale === null && !canZoom(img))) return;
        const scale = currentScale(img) * Math.exp(-e.deltaY * 0.002);
        loadZoomSource(img);
        zoomAt(scale, e.clientX, e.clientY);
    }, { passive: false });
}

window.addEventListener('resize', () => { if (zoom.scale !== null) applyZoom(); });

async function fetchPage(url) {
    const cacheKey = url.split('#')[0];
    let html = pageCache.get(cacheKey);
    if (html) return html;
    const res = await fetch(url);
    if (!res.ok) return null;
    html = await res.text();
    pageCache.set(cacheKey, html);
    return html;
}

const prefetched = new Set();

// Fetches a page and its hero image in the srcset variant this screen will
// use, so a later click finds both in the cache.
function prefetchPage(url) {
    if (navigator.connection && navigator.connection.saveData) return;
    const key = url.split('#')[0];
    if (prefetched.has(key)) return;
    prefetched.add(key);
    fetchPage(url).then((html) => {
        if (!html) return;
        const doc = new DOMParser().parseFromString(html, 'text/html');
        doc.querySelectorAll('.hero-image:not([hidden])').forEach((img) => preloadImage(img, url));
    }).catch(() => {});
}

// Selectors for <head> elements that carry per-page SEO metadata and must be
// swapped in on client-side navigation, or every page after the first keeps
// the previous page's description/canonical/structured data.
const HEAD_META_SELECTOR = [
    'meta[name="description"]',
    'link[rel="canonical"]',
    'link[rel="alternate"][hreflang]',
    'meta[property^="og:"]',
    'meta[name^="twitter:"]',
    'script[type="application/ld+json"]',
].join(', ');

function updateHeadMeta(doc) {
    document.head.querySelectorAll(HEAD_META_SELECTOR).forEach((el) => el.remove());
    doc.head.querySelectorAll(HEAD_META_SELECTOR).forEach((el) => {
        document.head.appendChild(el.cloneNode(true));
    });
}

function preloadImage(img, baseUrl) {
    const src = img.getAttribute('src');
    if (!src) return Promise.resolve();
    const pre = new Image();
    const sizes = img.getAttribute('sizes');
    const srcset = img.getAttribute('srcset');
    if (sizes) pre.sizes = sizes;
    if (srcset) pre.srcset = srcset;
    pre.src = new URL(src, baseUrl).href;
    return pre.decode ? pre.decode().catch(() => {}) : new Promise((resolve) => {
        pre.addEventListener('load', resolve, { once: true });
        pre.addEventListener('error', resolve, { once: true });
    });
}

// Back/Forward restore each page's scroll position from its history entry.
if ('scrollRestoration' in history) history.scrollRestoration = 'manual';

function saveScroll() {
    history.replaceState({ ...history.state, scrollY: window.scrollY }, '');
}

let scrollSaveTimer;
window.addEventListener('scroll', () => {
    clearTimeout(scrollSaveTimer);
    scrollSaveTimer = setTimeout(saveScroll, 150);
}, { passive: true });

// After a back link, centre the card that links to the page just left.
function scrollToCardFor(fromUrl) {
    const path = new URL(fromUrl).pathname;
    const card = [...document.querySelectorAll('main a[href]')]
        .find((a) => a.id !== 'back-link' && new URL(a.href).pathname === path);
    if (!card) return false;
    card.scrollIntoView({ block: 'center' });
    return true;
}

async function loadPage(url, push, restoreY = 0, fromUrl = null) {
    let html = null;
    try {
        html = await fetchPage(url);
    } catch (e) {
        // Network error: fall through to a normal page load.
    }
    if (!html) {
        window.location.href = url;
        return;
    }

    const doc = new DOMParser().parseFromString(html, 'text/html');
    // Wait for the visible hero image to be fully decoded before swapping the
    // DOM, so the new <img> paints immediately instead of flashing blank.
    await Promise.all(
        [...doc.querySelectorAll('.hero-image:not([hidden])')].map((img) => preloadImage(img, url))
    );
    if (push) {
        // Record the outgoing page's position now; a pending debounced save
        // would otherwise write it into the new entry.
        clearTimeout(scrollSaveTimer);
        saveScroll();
    }
    document.title = doc.title;
    document.documentElement.lang = doc.documentElement.lang;
    document.body.innerHTML = doc.body.innerHTML;
    updateHeadMeta(doc);

    if (push) {
        history.pushState({ url }, '', url);
    }
    if (!(fromUrl && scrollToCardFor(fromUrl))) window.scrollTo(0, push ? 0 : restoreY);
    initMedia();

    const main = document.querySelector('main');
    if (main) {
        main.setAttribute('tabindex', '-1');
        main.focus({ preventScroll: true });
    }
}

document.addEventListener('click', (e) => {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    const link = e.target.closest('a');
    if (!link || !link.href) return;
    if (link.target && link.target !== '_self') return;
    if (link.hasAttribute('download')) return;

    const url = new URL(link.href, window.location.href);
    if (url.origin !== window.location.origin) return;
    // Files (e.g. the full-size rig photos) open natively, not as pages.
    if (/\.\w+$/.test(url.pathname) && !url.pathname.endsWith('.html')) return;
    // Language links keep the selected version of a multi-version page.
    if (link.hasAttribute('data-keep-hash') && location.hash) url.hash = location.hash;
    if (url.pathname === window.location.pathname && url.search === window.location.search) return;

    e.preventDefault();
    loadPage(url.href, true, 0, link.id === 'back-link' ? window.location.href : null);
});

window.addEventListener('popstate', () => {
    // Read the target entry's position before a pending save can overwrite it.
    clearTimeout(scrollSaveTimer);
    loadPage(window.location.href, false, (history.state && history.state.scrollY) || 0);
});

// Elements that use the arrow keys themselves: seeking a video, moving a
// caret, picking an option.
const OWNS_ARROW_KEYS = 'input, textarea, select, video, audio, [contenteditable]';

document.addEventListener('keydown', (e) => {
    // Already handled, e.g. by the version tabs moving between versions.
    if (e.defaultPrevented) return;
    const overlay = document.getElementById('fullscreen-overlay');
    if (e.key === 'Escape') {
        // On a single-image page, Escape closes the fullscreen zoom if it's open;
        // otherwise it navigates back to the collection, same as clicking "Back to X".
        if (overlay && !overlay.classList.contains('hidden')) {
            closeFullscreen();
        } else {
            const backLink = document.getElementById('back-link');
            if (backLink) backLink.click();
        }
    }
    if (e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
    if (!(e.target instanceof Element && e.target.closest(OWNS_ARROW_KEYS))) {
        const nextBtn = document.getElementById('nav-next');
        const prevBtn = document.getElementById('nav-prev');
        if (e.key === 'ArrowLeft' && nextBtn) { nextBtn.click(); }
        else if (e.key === 'ArrowRight' && prevBtn) { prevBtn.click(); }
    }
});

initMedia();
// Manual restoration also covers a reload: go back to the saved position.
if (history.state && history.state.scrollY) window.scrollTo(0, history.state.scrollY);
