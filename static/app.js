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


// ============================================
// PHONE NUMBER FORMATTING
// Reformats digits into 000-000-0000 as the
// stylist types, on the client form's phone
// field only.
// ============================================
const phoneInput = document.getElementById('phone');

if (phoneInput) {
    phoneInput.addEventListener('input', function () {
        // \D matches any non-digit character; replacing it with '' strips
        // anything that isn't 0-9, so pasted text like "(803) 445-5192"
        // still formats correctly. slice(0, 10) caps it at 10 digits.
        const digits = phoneInput.value.replace(/\D/g, '').slice(0, 10);

        let formatted = digits;
        if (digits.length > 6) {
            formatted = digits.slice(0, 3) + '-' + digits.slice(3, 6) + '-' + digits.slice(6);
        } else if (digits.length > 3) {
            formatted = digits.slice(0, 3) + '-' + digits.slice(3);
        }
        phoneInput.value = formatted;
    });
}


// ============================================
// CLIENT SEARCH
// Filters the client list as you type. Pure
// client-side - no server round-trip needed,
// since a single salon's client list is small
// enough to filter instantly in the browser.
// Only runs on the home page.
// ============================================
(function () {
    const searchInput = document.getElementById('client-search');
    const noResults = document.getElementById('no-results');

    if (!searchInput) {
        return; // not on the client list page - nothing to wire up
    }

    const clientItems = document.querySelectorAll('#client-list li[data-name]');

    searchInput.addEventListener('input', function () {
        const query = searchInput.value.trim().toLowerCase();
        let anyVisible = false;

        clientItems.forEach(function (li) {
            const matches = li.dataset.name.includes(query);
            li.style.display = matches ? '' : 'none';
            if (matches) {
                anyVisible = true;
            }
        });

        if (noResults) {
            noResults.style.display = (query && !anyVisible) ? '' : 'none';
        }
    });
})();

// ============================================
// FORMULATION MIX BOXES
// Lets a stylist add more than one formulation
// to a single appointment (e.g. a root formula
// plus a separate gloss), each with its own
// classification, developer, recipe, and
// development time. Only runs on the
// new/edit formulation page.
// ============================================
(function () {
    const container = document.getElementById('mixes');
    const addBtn = document.getElementById('add-mix');
    const indicesInput = document.getElementById('mix-indices');
    const template = document.getElementById('mix-template');

    if (!container || !addBtn || !indicesInput || !template) {
        return; // not on the formulation form - nothing to wire up
    }

    // Indices are never reused, even after a box is removed, so two boxes
    // can never accidentally share field names.
    let nextIndex = parseInt(container.dataset.nextIndex, 10);

    function relabelAndSync() {
        const boxes = container.querySelectorAll('.formula-mix');
        const letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';

        boxes.forEach(function (box, position) {
            box.querySelector('.mix-label').textContent = 'Formulation ' + letters[position];
            const removeBtn = box.querySelector('.remove-mix');
            // Always allow removing down to 1 box, never to 0
            removeBtn.style.display = boxes.length > 1 ? '' : 'none';
        });

        // Keep the hidden mix_indices field in sync with whatever boxes
        // currently exist, so the backend knows exactly which mix_N_*
        // fields to read on submit.
        const liveIndices = Array.from(boxes).map(function (box) {
            return box.dataset.index;
        });
        indicesInput.value = liveIndices.join(',');
    }

    addBtn.addEventListener('click', function () {
        const fragment = template.content.cloneNode(true);
        const box = fragment.querySelector('.formula-mix');
        box.dataset.index = nextIndex;

        // Every field in the template has data-name="mix___INDEX___foo"
        // instead of a real name attribute (a name this early would let
        // an empty, unused box accidentally get submitted as index 0).
        // Swap in the real index now that this box is actually being used.
        fragment.querySelectorAll('[data-name]').forEach(function (field) {
            field.name = field.dataset.name.replace('__INDEX__', nextIndex);
        });

        container.appendChild(fragment);
        nextIndex++;
        relabelAndSync();
    });

    // One listener on the container instead of one per remove button -
    // this also automatically covers boxes added later via cloning.
    container.addEventListener('click', function (event) {
        if (event.target.classList.contains('remove-mix')) {
            event.target.closest('.formula-mix').remove();
            relabelAndSync();
        }
    });

    relabelAndSync();
})();


// ============================================
// FORMULATIONS SEARCH
// Filters the formulations list as you type,
// matching against client name, date, and the
// consultation notes preview. Same pattern as
// the client search above - pure client-side,
// no server round-trip needed.
// ============================================
(function () {
    const searchInput = document.getElementById('formulations-search');
    const noResults   = document.getElementById('formulations-no-results');

    if (!searchInput) {
        return; // not on the formulations page - nothing to wire up
    }

    const items = document.querySelectorAll('#formulations-list li[data-search]');

    searchInput.addEventListener('input', function () {
        const query = searchInput.value.trim().toLowerCase();
        let anyVisible = false;

        items.forEach(function (li) {
            const matches = !query || li.dataset.search.includes(query);
            li.style.display = matches ? '' : 'none';
            if (matches) anyVisible = true;
        });

        if (noResults) {
            noResults.style.display = (query && !anyVisible) ? '' : 'none';
        }
    });
})();
