const modal = document.getElementById("my-modal");

const openModal = (data) => {
    const iframe = modal.querySelector("iframe");
    modal.style.display = "grid";
    iframe.src = data;
}

const closeModal = () => modal.style.display = "none";
