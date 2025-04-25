const publicCheckbox = document.getElementById('toggle-public');
const privateCheckbox = document.getElementById('toggle-private');
const archivedCheckbox = document.getElementById('toggle-archive');
const ownerInput = document.getElementById('owner-filter');
const repoInput = document.getElementById('repo-filter');
const modal = document.getElementById("my-modal");

const openModal = (data) => {
    const iframe = modal.querySelector("iframe");
    modal.style.display = "grid";
    iframe.src = data;
}

const closeModal = () => modal.style.display = "none";

function filterAll() {
    console.log("Filtering All.")
    const ownerFilter = ownerInput.value.toLowerCase();
    const repoFilter = repoInput.value.toLowerCase();
    const rows = document.querySelectorAll('table tbody tr');

    rows.forEach(row => {
        const matchOwner = [...row.querySelectorAll('span.owner')].some(td =>
            td.textContent.toLowerCase().includes(ownerFilter)
        );
        const matchRepo = [...row.querySelectorAll('span.repo')].some(td =>
            td.textContent.toLowerCase().includes(repoFilter)
        );
        archived = !(!archivedCheckbox.checked && row.classList.contains('archived'))
        private = !(!privateCheckbox.checked && row.classList.contains('private'))
        public = !(!publicCheckbox.checked && row.classList.contains('public'))

        toDisplay = matchOwner && matchRepo && archived && private && public
        row.style.display = toDisplay ? '' : 'none';
    });
    updateVisibleRowClasses();
}

function updateVisibleRowClasses() {
    const rows = [...document.querySelectorAll('table tbody tr')];
    let visibleIndex = 0;

    rows.forEach(row => {
        row.classList.remove('odd', 'even');

        if (row.style.display !== 'none') {
            row.classList.add(visibleIndex % 2 === 0 ? 'even' : 'odd');
            visibleIndex++;
        }
    });
}

publicCheckbox.addEventListener('change', filterAll);
privateCheckbox.addEventListener('change', filterAll);
archivedCheckbox.addEventListener('change', filterAll);
ownerInput.addEventListener('input', filterAll);
repoInput.addEventListener('input', filterAll);
filterAll();
