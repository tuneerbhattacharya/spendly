// main.js — students will add JavaScript here as features are built

// Ask for confirmation before submitting any form carrying a data-confirm message.
document.addEventListener("submit", function (e) {
    var message = e.target.dataset && e.target.dataset.confirm;
    if (message && !window.confirm(message)) {
        e.preventDefault();
    }
});
