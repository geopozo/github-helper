const sortBy = (btnId, filter) => {
    const filterBtn = document.getElementById(btnId);
    const order = filterBtn.dataset.order === "asc" ? "desc" : "asc";
    filterBtn.dataset.order = order;
    isAsc = order === "asc"
    filterBtn.textContent = `${isAsc ? "⬆️" : "⬇️"}`;
    filterBtn.title = `Sort by ${isAsc ? "asc" : "desc"}`;

    const rows = Array.from(tbody.querySelectorAll("tr"));

    rows.sort((a, b) => {
        const nameA = a.querySelector(filter).textContent.trim().toLowerCase();
        const nameB = b.querySelector(filter).textContent.trim().toLowerCase();
        return order === "asc"
            ? nameA.localeCompare(nameB)
            : nameB.localeCompare(nameA);
    });

    rows.forEach(row => tbody.appendChild(row));
    updateVisibleRowClasses();
}
