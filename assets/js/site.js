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

    const overlay = document.getElementById('fullscreen-overlay');
    const fullscreenImg = document.getElementById('fullscreen-image');
    if (!overlay || !fullscreenImg) return;

    document.querySelectorAll('.hero-image').forEach((img) => {
        img.addEventListener('click', (e) => {
            e.stopPropagation();
            fullscreenImg.src = img.currentSrc || img.src;
            fullscreenImg.alt = img.alt;
            overlay.classList.remove('hidden');
            document.body.style.overflow = 'hidden';
        });
    });
    overlay.addEventListener('click', () => {
        overlay.classList.add('hidden');
        document.body.style.overflow = '';
    });
}

function updatePrefetchLinks(doc) {
    document.querySelectorAll('link[rel="prefetch"][data-pjax]').forEach((el) => el.remove());
    doc.querySelectorAll('link[rel="prefetch"]').forEach((el) => {
        const clone = el.cloneNode();
        clone.setAttribute('data-pjax', '');
        document.head.appendChild(clone);
    });
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

async function loadPage(url, push) {
    const cacheKey = url.split('#')[0];
    let html = pageCache.get(cacheKey);
    if (!html) {
        let res;
        try {
            res = await fetch(url);
        } catch (e) {
            window.location.href = url;
            return;
        }
        if (!res.ok) {
            window.location.href = url;
            return;
        }
        html = await res.text();
        pageCache.set(cacheKey, html);
    }

    const doc = new DOMParser().parseFromString(html, 'text/html');
    // Wait for the visible hero image to be fully decoded before swapping the
    // DOM, so the new <img> paints immediately instead of flashing blank.
    await Promise.all(
        [...doc.querySelectorAll('.hero-image:not([hidden])')].map((img) => preloadImage(img, url))
    );
    document.title = doc.title;
    document.documentElement.lang = doc.documentElement.lang;
    document.body.innerHTML = doc.body.innerHTML;
    updatePrefetchLinks(doc);
    updateHeadMeta(doc);

    if (push) {
        history.pushState({ url }, '', url);
    }
    window.scrollTo(0, 0);
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
    // Language links keep the selected version of a multi-version page.
    if (link.hasAttribute('data-keep-hash') && location.hash) url.hash = location.hash;
    if (url.pathname === window.location.pathname && url.search === window.location.search) return;

    e.preventDefault();
    loadPage(url.href, true);
});

window.addEventListener('popstate', () => {
    loadPage(window.location.href, false);
});

document.addEventListener('keydown', (e) => {
    const overlay = document.getElementById('fullscreen-overlay');
    if (e.key === 'Escape') {
        // On a single-image page, Escape closes the fullscreen zoom if it's open;
        // otherwise it navigates back to the collection, same as clicking "Back to X".
        if (overlay && !overlay.classList.contains('hidden')) {
            overlay.classList.add('hidden');
            document.body.style.overflow = '';
        } else {
            const backLink = document.getElementById('back-link');
            if (backLink) backLink.click();
        }
    }
    if (e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') {
        const nextBtn = document.getElementById('nav-next');
        const prevBtn = document.getElementById('nav-prev');
        if (e.key === 'ArrowLeft' && nextBtn) { nextBtn.click(); }
        else if (e.key === 'ArrowRight' && prevBtn) { prevBtn.click(); }
    }
});

initMedia();
