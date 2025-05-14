const publicCheckbox = document.getElementById('toggle-public');
const privateCheckbox = document.getElementById('toggle-private');
const archivedCheckbox = document.getElementById('toggle-archive');
const ownerInput = document.getElementById('owner-filter');
const repoInput = document.getElementById('repo-filter');
const tbody = document.querySelector("tbody");

function filterAll() {
    console.log("Filtering All.")
    const ownerFilter = ownerInput.value.toLowerCase();
    const repoFilter = repoInput.value.toLowerCase();
    const rows = document.querySelectorAll('table tbody tr');

    rows.forEach(row => {
        const matchOwner = [...row.querySelectorAll('td.owner')].some(td =>
            td.textContent.toLowerCase().includes(ownerFilter)
        );
        const matchRepo = [...row.querySelectorAll('td.repo')].some(td =>
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

const openModalIframe = (data) => {
    const iframe = modal.querySelector("iframe");
    iframe.src = data;
    openModal();
}

publicCheckbox.addEventListener('change', filterAll);
privateCheckbox.addEventListener('change', filterAll);
archivedCheckbox.addEventListener('change', filterAll);
ownerInput.addEventListener('input', filterAll);
repoInput.addEventListener('input', filterAll);
filterAll();

const sortByRepo = () => {
    const repoFilter = document.getElementById("sort-button");
    const order = repoFilter.dataset.order === "asc" ? "desc" : "asc";
    repoFilter.dataset.order = order;
    repoFilter.textContent = order === "asc" ? "⬆️" : "⬇️";
    repoFilter.title = `Sort by ${order === "asc" ? "asc" : "desc"}`;

    const rows = Array.from(tbody.querySelectorAll("tr"));

    rows.sort((a, b) => {
        const nameA = a.querySelector(".repo").textContent.trim().toLowerCase();
        const nameB = b.querySelector(".repo").textContent.trim().toLowerCase();
        return order === "asc"
            ? nameA.localeCompare(nameB)
            : nameB.localeCompare(nameA);
    });

    rows.forEach(row => tbody.appendChild(row));
    updateVisibleRowClasses();
}
