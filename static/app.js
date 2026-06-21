// Lets each stylist pick whichever font is easier for THEM to read,
// instead of one font being forced on everyone. Their choice is
// remembered in this browser via localStorage, so it persists between
// visits without needing any backend/database changes.

const FONT_KEY = 'preferredFont'; // the localStorage key we save under
const toggleBtn = document.getElementById('font-toggle');

function applyFont(font) {
    if (font === 'opendyslexic') {
        document.body.classList.add('font-opendyslexic');
        toggleBtn.textContent = 'Font: OpenDyslexic';
    } else {
        document.body.classList.remove('font-opendyslexic');
        toggleBtn.textContent = 'Font: Atkinson Hyperlegible';
    }
}

// On every page load, check what was saved last time (defaults to
// Atkinson Hyperlegible if nothing has been saved yet).
const saved = localStorage.getItem(FONT_KEY) || 'atkinson';
applyFont(saved);

// addEventListener attaches a function that runs whenever this button
// is clicked - no page reload needed.
toggleBtn.addEventListener('click', function () {
    const current = localStorage.getItem(FONT_KEY) || 'atkinson';
    const next = current === 'atkinson' ? 'opendyslexic' : 'atkinson';
    localStorage.setItem(FONT_KEY, next);
    applyFont(next);
});
