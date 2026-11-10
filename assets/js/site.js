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
    // Also handles the close button, whose click bubbles up to the overlay.
    overlay.addEventListener('click', closeFullscreen);
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
    fullscreenImg.alt = img.alt;
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
    if (fullscreenOpener && fullscreenOpener.isConnected) fullscreenOpener.focus({ preventScroll: true });
    fullscreenOpener = null;
}

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

async function loadPage(url, push, restoreY = 0) {
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
    window.scrollTo(0, push ? 0 : restoreY);
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
    loadPage(url.href, true);
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
