const pageCache = new Map();

function selectVersion(id, updateHash) {
    const tabs = [...document.querySelectorAll('[data-version-tab]')];
    if (!tabs.length) return;
    const first = tabs[0].dataset.versionTab;
    if (!tabs.some((tab) => tab.dataset.versionTab === id)) id = first;

    tabs.forEach((tab) => tab.setAttribute('aria-selected', String(tab.dataset.versionTab === id)));
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

    document.querySelectorAll('[data-version-tab]').forEach((tab) => {
        tab.addEventListener('click', () => selectVersion(tab.dataset.versionTab, true));
    });
    selectVersion(decodeURIComponent(location.hash.slice(1)), false);

    const overlay = document.getElementById('fullscreen-overlay');
    const fullscreenImg = document.getElementById('fullscreen-image');
    if (!overlay || !fullscreenImg) return;

    document.querySelectorAll('.hero-image').forEach((img) => {
        img.addEventListener('click', (e) => {
            e.stopPropagation();
            fullscreenImg.src = img.currentSrc || img.src;
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
    document.title = doc.title;
    document.documentElement.lang = doc.documentElement.lang;
    document.body.innerHTML = doc.body.innerHTML;
    updatePrefetchLinks(doc);

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
    if (e.key === 'Escape' && overlay) {
        overlay.classList.add('hidden');
        document.body.style.overflow = '';
    }
    if (e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') {
        const nextBtn = document.getElementById('nav-next');
        const prevBtn = document.getElementById('nav-prev');
        if (e.key === 'ArrowLeft' && nextBtn) { nextBtn.click(); }
        else if (e.key === 'ArrowRight' && prevBtn) { prevBtn.click(); }
    }
});

initMedia();
