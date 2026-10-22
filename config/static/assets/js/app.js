/*
 * Поиск во всех выпадающих списках (Tom Select).
 * Запускается на window "load" — после скриптов страниц, которые сами создают TomSelect
 * (такие списки уже помечены классом .tomselected и пропускаются).
 * Отключить для конкретного списка: <select data-no-search>.
 */
(function () {
    "use strict";

    function initSearchSelects(root) {
        if (typeof TomSelect === "undefined") return;

        (root || document).querySelectorAll("select").forEach(function (el) {
            if (el.tomselect || el.classList.contains("tomselected")) return;
            if (el.hasAttribute("data-no-search") || el.closest("[data-no-search]")) return;

            // "---------" от Django заменяем на понятный текст
            var emptyOption = el.querySelector('option[value=""]');
            if (emptyOption && /^-+$/.test(emptyOption.textContent.trim())) {
                var form = el.closest("form");
                var isFilter = form && (form.getAttribute("method") || "get").toLowerCase() === "get";
                emptyOption.textContent = isFilter ? "Все" : "— не выбрано —";
            }
            var settings = {
                create: false,
                allowEmptyOption: true,
                maxOptions: null,
                sortField: [{field: "$order"}],
                placeholder: "Выберите…",
                render: {
                    no_results: function () {
                        return '<div class="no-results">Ничего не найдено</div>';
                    }
                }
            };
            if (el.multiple) {
                settings.plugins = ["remove_button"];
            }

            try {
                new TomSelect(el, settings);
            } catch (e) {
                console.warn("TomSelect init failed", el, e);
            }
        });
    }

    window.initSearchSelects = initSearchSelects;
    window.addEventListener("load", function () {
        initSearchSelects(document);
    });
})();
