// GitHub Pages serves only the root (English) 404.html: under /it/ or /ru/, swap in that language's 404 page.
(() => {
    const m = location.pathname.match(/^\/(it|ru)\//);
    if (!m || document.documentElement.lang === m[1]) return;
    fetch('/' + m[1] + '/404.html').then((r) => (r.ok ? r.text() : null)).then((html) => {
        if (!html) return;
        const doc = new DOMParser().parseFromString(html, 'text/html');
        document.title = doc.title;
        document.documentElement.lang = doc.documentElement.lang;
        document.body.innerHTML = doc.body.innerHTML;
    }).catch(() => {});
})();
