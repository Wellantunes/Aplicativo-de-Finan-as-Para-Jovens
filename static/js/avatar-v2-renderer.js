(function () {
    "use strict";

    const imageCache = new Map();
    const catalog = {
        canvas: { width: 512, height: 560 },
        defaults: {
            masculina: {
                base: "masculina",
                skin: "media",
                hair: "curto",
                hairColor: "castanho",
                beard: "sem_barba",
                shirt: "camiseta",
                shirtColor: "creme",
            },
            feminina: {
                base: "feminina",
                skin: "media",
                hair: "comprido",
                hairColor: "castanho",
                beard: "sem_barba",
                shirt: "camiseta",
                shirtColor: "creme",
            },
        },
        bases: {
            masculina: {
                assetSuffix: "M",
                base: [40, 50, 438, 510],
                shortHair: [137, 29, 279, 217],
                longHair: [56, 24, 400, 422],
                beard: [156, 195, 200, 128],
                jacket: [31, 268, 451, 336],
                portrait: [108, 20, 296, 296],
            },
            feminina: {
                assetSuffix: "F",
                base: [54, 60, 405, 470],
                shortHair: [132, 39, 252, 196],
                longHair: [65, 32, 382, 403],
                beard: [169, 205, 175, 112],
                jacket: [52, 282, 407, 303],
                portrait: [110, 24, 292, 292],
            },
        },
    };

    function loadImage(source) {
        if (!imageCache.has(source)) {
            imageCache.set(source, new Promise((resolve, reject) => {
                const image = new Image();
                image.onload = () => resolve(image);
                image.onerror = () => reject(new Error(`Não foi possível carregar ${source}`));
                image.src = source;
            }));
        }
        return imageCache.get(source);
    }

    function stateFromCanvas(canvas) {
        return {
            base: canvas.dataset.avatarBase,
            skin: canvas.dataset.avatarPele,
            hair: canvas.dataset.avatarCabelo,
            hairColor: canvas.dataset.avatarCorCabelo,
            beard: canvas.dataset.avatarBarba,
            shirt: canvas.dataset.avatarRoupa,
            shirtColor: canvas.dataset.avatarCorRoupa,
        };
    }

    function nextRenderSequence(canvas) {
        const sequence = Number(canvas.dataset.avatarRenderSequence || 0) + 1;
        canvas.dataset.avatarRenderSequence = String(sequence);
        return sequence;
    }

    async function composeAvatar(canvas, state, baseCatalog) {
        const assets = canvas.dataset;
        const renderedRoot = canvas.getAttribute("data-asset-rendered-root");
        const baseSuffix = baseCatalog.assetSuffix;
        const baseAssetName = state.shirt === "camisa_azul"
            ? `assetJacketBase${baseSuffix}`
            : `assetBase${baseSuffix}`;
        const baseFileName = baseSuffix.toLowerCase();
        const composition = document.createElement("canvas");
        composition.width = catalog.canvas.width;
        composition.height = catalog.canvas.height;
        const context = composition.getContext("2d");
        context.imageSmoothingEnabled = false;

        const [base, skin] = await Promise.all([
            loadImage(assets[baseAssetName]),
            loadImage(`${renderedRoot}skin/base-${baseFileName}-${state.skin}.png`),
        ]);
        context.drawImage(base, ...baseCatalog.base);
        context.drawImage(skin, ...baseCatalog.base);

        if (state.shirt === "camiseta") {
            const shirt = await loadImage(
                `${renderedRoot}shirt/base-${baseFileName}-${state.shirtColor}.png`
            );
            context.drawImage(shirt, ...baseCatalog.base);
        } else {
            const jacket = await loadImage(assets.assetJacket);
            context.drawImage(jacket, ...baseCatalog.jacket);
        }

        if (state.beard === "curta") {
            const beard = await loadImage(
                `${renderedRoot}hair/beard-short-${state.hairColor}.png`
            );
            context.drawImage(beard, ...baseCatalog.beard);
        }

        if (state.hair === "curto") {
            const hair = await loadImage(
                `${renderedRoot}hair/hair-short-${state.hairColor}.png`
            );
            context.drawImage(hair, ...baseCatalog.shortHair);
        } else if (state.hair === "comprido") {
            const hair = await loadImage(
                `${renderedRoot}hair/hair-long-${state.hairColor}.png`
            );
            context.drawImage(hair, ...baseCatalog.longHair);
        }

        return composition;
    }

    function drawComposition(canvas, composition, baseCatalog) {
        const context = canvas.getContext("2d");
        context.clearRect(0, 0, canvas.width, canvas.height);
        context.imageSmoothingEnabled = false;
        if (canvas.dataset.avatarVariant === "portrait") {
            context.drawImage(
                composition,
                ...baseCatalog.portrait,
                0,
                0,
                canvas.width,
                canvas.height
            );
            return;
        }
        context.drawImage(composition, 0, 0, canvas.width, canvas.height);
    }

    async function render(canvas, customState) {
        const state = { ...(customState || stateFromCanvas(canvas)) };
        const baseCatalog = catalog.bases[state.base] || catalog.bases.masculina;
        const renderSequence = nextRenderSequence(canvas);
        canvas.classList.remove("dropduo-avatar__v2--ready");
        try {
            const composition = await composeAvatar(canvas, state, baseCatalog);
            if (Number(canvas.dataset.avatarRenderSequence) !== renderSequence) return;
            drawComposition(canvas, composition, baseCatalog);
            canvas.classList.add("dropduo-avatar__v2--ready");
            canvas.dispatchEvent(new CustomEvent("dropduo:avatar-ready", { detail: state }));
        } catch (error) {
            if (Number(canvas.dataset.avatarRenderSequence) !== renderSequence) return;
            canvas.classList.remove("dropduo-avatar__v2--ready");
            canvas.dispatchEvent(new CustomEvent("dropduo:avatar-error", { detail: error }));
        }
    }

    function renderAll() {
        document.querySelectorAll("[data-dropduo-avatar-v2]").forEach((canvas) => render(canvas));
    }

    window.DropDuoAvatar = { catalog, render, renderAll, stateFromCanvas };
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", renderAll);
    else renderAll();
}());
