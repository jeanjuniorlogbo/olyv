(function () {
    'use strict';
    const read = () => { try { return localStorage.getItem('theme') || 'light'; } catch (e) { return 'light'; } };
    const write = t => { try { localStorage.setItem('theme', t); } catch (e) { } };
    const apply = t => document.body.classList.toggle('dark-theme', t === 'dark');
    const saved = read();
    apply(saved);
    const toggle = document.getElementById('theme-toggle');
    if (!toggle) return;
    const buttons = toggle.querySelectorAll('button');
    const mark = t => buttons.forEach(b => b.classList.toggle('active', b.dataset.theme === t));
    mark(saved);
    buttons.forEach(b => b.addEventListener('click', () => {
        apply(b.dataset.theme);
        mark(b.dataset.theme);
        write(b.dataset.theme);
    }));
})();
