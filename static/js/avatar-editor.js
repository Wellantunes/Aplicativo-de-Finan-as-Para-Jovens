(function () {
    "use strict";

    const form = document.querySelector("[data-avatar-form]");
    const preview = document.querySelector("[data-avatar-editor-preview]");
    const status = document.querySelector("[data-avatar-status]");
    const shirtColors = document.querySelector("[data-shirt-colors]");
    if (!form || !preview || !window.DropDuoAvatar) return;

    const fieldNames = {
        avatar_v2_base: "base",
        avatar_v2_pele: "skin",
        avatar_v2_cabelo: "hair",
        avatar_v2_cor_cabelo: "hairColor",
        avatar_v2_barba: "beard",
        avatar_v2_roupa: "shirt",
        avatar_v2_cor_roupa: "shirtColor",
    };
    const savedState = form.dataset.avatarHasSaved === "true" ? {
        base: form.dataset.savedBase,
        skin: form.dataset.savedSkin,
        hair: form.dataset.savedHair,
        hairColor: form.dataset.savedHairColor,
        beard: form.dataset.savedBeard,
        shirt: form.dataset.savedShirt,
        shirtColor: form.dataset.savedShirtColor,
    } : null;

    function selectedValue(name) {
        return form.querySelector(`[name="${name}"]:checked`)?.value || "";
    }

    function currentState() {
        const state = {};
        Object.entries(fieldNames).forEach(([name, key]) => {
            state[key] = selectedValue(name);
        });
        return state;
    }

    function selectValue(name, value) {
        const option = form.querySelector(`[name="${name}"][value="${value}"]`);
        if (option) option.checked = true;
    }

    function applyState(state) {
        Object.entries(fieldNames).forEach(([name, key]) => {
            selectValue(name, state[key]);
        });
    }

    function defaultState(base) {
        const defaults = window.DropDuoAvatar.catalog.defaults;
        return { ...(defaults[base] || defaults.masculina) };
    }

    function referenceState(base) {
        if (savedState && savedState.base === base) return { ...savedState };
        return defaultState(base);
    }

    function updateShirtColors() {
        const isTee = selectedValue("avatar_v2_roupa") === "camiseta";
        shirtColors.hidden = !isTee;
        shirtColors.querySelectorAll("input").forEach((input) => {
            input.disabled = !isTee;
        });
        if (!isTee) {
            const blue = shirtColors.querySelector('[value="azul"]');
            if (blue) {
                blue.disabled = false;
                blue.checked = true;
            }
        }
    }

    function updatePreview() {
        updateShirtColors();
        status.textContent = "Atualizando prévia…";
        window.DropDuoAvatar.render(preview, { ...currentState() });
    }

    function handleChange(event) {
        if (event.target.name === "avatar_v2_base") {
            applyState(referenceState(event.target.value));
        }
        updatePreview();
    }

    preview.addEventListener("dropduo:avatar-ready", () => {
        status.textContent = "Prévia atualizada. As alterações ainda não foram salvas.";
    });
    preview.addEventListener("dropduo:avatar-error", () => {
        status.textContent = "A prévia não pôde ser carregada. Você ainda pode cancelar ou tentar novamente.";
    });
    form.addEventListener("change", handleChange);

    if (form.dataset.avatarFormBound !== "true") {
        const initialBase = savedState?.base || selectedValue("avatar_v2_base") || "masculina";
        applyState(referenceState(initialBase));
    }
    updatePreview();
}());
