// Comportamentos pequenos e compartilhados por todas as telas.

const avisoConexao = document.querySelector("[data-connection-message]");

function atualizarEstadoDaConexao() {
    if (!avisoConexao) return;
    avisoConexao.hidden = navigator.onLine;
}

window.addEventListener("online", atualizarEstadoDaConexao);
window.addEventListener("offline", atualizarEstadoDaConexao);
atualizarEstadoDaConexao();

document.querySelectorAll("[data-dismiss-message]").forEach((botao) => {
    botao.addEventListener("click", () => {
        botao.closest("[data-dismissible-message]")?.remove();
    });
});

document.querySelectorAll("[data-auto-dismiss-message]").forEach((mensagem) => {
    window.setTimeout(() => mensagem.remove(), 3000);
});

document.querySelectorAll("form[method='post']").forEach((formulario) => {
    formulario.addEventListener("submit", (evento) => {
        if (formulario.dataset.enviando === "true") {
            evento.preventDefault();
            return;
        }

        formulario.dataset.enviando = "true";
        formulario.querySelectorAll("button[type='submit']").forEach((botao) => {
            botao.disabled = true;
            botao.setAttribute("aria-disabled", "true");
            botao.dataset.textoOriginal = botao.textContent;
            botao.textContent = botao.dataset.loadingText || "Enviando...";
        });
    });
});

// Ao voltar pelo histórico, o navegador pode restaurar a página com o botão
// ainda desabilitado. Reativamos o formulário para que ele possa ser corrigido.
window.addEventListener("pageshow", (evento) => {
    if (!evento.persisted) return;
    document.querySelectorAll("form[data-enviando='true']").forEach((formulario) => {
        delete formulario.dataset.enviando;
        formulario.querySelectorAll("button[type='submit'][data-texto-original]").forEach((botao) => {
            botao.disabled = false;
            botao.removeAttribute("aria-disabled");
            botao.textContent = botao.dataset.textoOriginal;
            delete botao.dataset.textoOriginal;
        });
    });
});

document.querySelectorAll(".form-field").forEach((grupo, indice) => {
    const campo = grupo.querySelector("input, select, textarea");
    if (!campo) return;

    const descricoes = Array.from(grupo.querySelectorAll(".field-help, .field-error"));
    descricoes.forEach((descricao, posicao) => {
        if (!descricao.id) descricao.id = `descricao-campo-${indice}-${posicao}`;
    });
    if (descricoes.length) {
        campo.setAttribute("aria-describedby", descricoes.map((item) => item.id).join(" "));
    }
    if (grupo.querySelector(".field-error")) campo.setAttribute("aria-invalid", "true");
});

const painel = document.querySelector(".dashboard");
const botaoValores = document.querySelector("[data-toggle-values]");

if (painel && botaoValores) {
    let valoresOcultos = false;
    try {
        valoresOcultos = localStorage.getItem("ocultarValoresFinanceiros") === "sim";
    } catch (erro) {
        valoresOcultos = false;
    }

    function atualizarVisibilidadeDosValores() {
        painel.classList.toggle("values-hidden", valoresOcultos);
        botaoValores.setAttribute("aria-pressed", String(valoresOcultos));
        botaoValores.textContent = valoresOcultos ? "Mostrar valores" : "Ocultar valores";
    }

    botaoValores.addEventListener("click", () => {
        valoresOcultos = !valoresOcultos;
        try {
            localStorage.setItem(
                "ocultarValoresFinanceiros",
                valoresOcultos ? "sim" : "nao",
            );
        } catch (erro) {
            // O painel continua funcionando mesmo com o armazenamento bloqueado.
        }
        atualizarVisibilidadeDosValores();
    });

    atualizarVisibilidadeDosValores();
}

const menuAdicionar = document.querySelector("[data-quick-add]");
if (menuAdicionar) {
    const acionadorAdicionar = menuAdicionar.querySelector("summary");

    document.addEventListener("click", (evento) => {
        if (!menuAdicionar.contains(evento.target)) menuAdicionar.open = false;
    });

    document.addEventListener("keydown", (evento) => {
        if (evento.key !== "Escape" || !menuAdicionar.open) return;
        menuAdicionar.open = false;
        acionadorAdicionar?.focus();
    });
}

const menusDeItem = Array.from(document.querySelectorAll(".shortcut-item__options"));
if (menusDeItem.length) {
    document.addEventListener("click", (evento) => {
        menusDeItem.forEach((menu) => {
            if (!menu.contains(evento.target)) menu.open = false;
        });
    });

    document.addEventListener("keydown", (evento) => {
        if (evento.key !== "Escape") return;
        const menuAberto = menusDeItem.find((menu) => menu.open);
        if (!menuAberto) return;
        menuAberto.open = false;
        menuAberto.querySelector("summary")?.focus();
    });
}

document.querySelectorAll("form[data-auto-submit]").forEach((formulario) => {
    formulario.addEventListener("change", () => formulario.requestSubmit());
});

function campoDeFormulario(elemento) {
    return elemento?.matches("input, select, textarea");
}

document.addEventListener("focusin", (evento) => {
    if (campoDeFormulario(evento.target)) document.body.classList.add("keyboard-open");
});

document.addEventListener("focusout", () => {
    requestAnimationFrame(() => {
        if (!campoDeFormulario(document.activeElement)) {
            document.body.classList.remove("keyboard-open");
        }
    });
});

document.querySelectorAll("[data-quick-status]").forEach((grupoSituacao) => {
    const formulario = grupoSituacao.closest("form");
    const campoData = formulario?.querySelector("[data-financial-date]");
    const opcoes = grupoSituacao.querySelectorAll("input[type='radio']");
    const tipo = grupoSituacao.querySelector("[data-financial-status]")?.dataset.financialStatus;
    if (!campoData || !opcoes.length || !tipo) return;

    function sugerirSituacaoPelaData() {
        if (!campoData.value) return;
        const hoje = new Date();
        const dataHoje = [
            hoje.getFullYear(),
            String(hoje.getMonth() + 1).padStart(2, "0"),
            String(hoje.getDate()).padStart(2, "0"),
        ].join("-");
        const valorSugerido = campoData.value > dataHoje
            ? (tipo === "entrada" ? "a_receber" : "pendente")
            : (tipo === "entrada" ? "recebida" : "paga");
        const opcao = Array.from(opcoes).find((item) => item.value === valorSugerido);
        if (opcao) opcao.checked = true;
    }

    campoData.addEventListener("change", sugerirSituacaoPelaData);
});

const formularioCartao = document.querySelector("[data-card-form]");
if (formularioCartao) {
    function atualizarCampoDeDia(tipo) {
        const regraMarcada = formularioCartao.querySelector(
            `input[name="regra_${tipo}"]:checked`,
        );
        const campoDia = formularioCartao.querySelector(`[data-card-fixed-day="${tipo}"]`);
        const grupoDia = campoDia?.closest(".form-field");
        const usaUltimoDia = regraMarcada?.value === "ultimo_dia";
        if (!campoDia || !grupoDia) return;
        grupoDia.toggleAttribute("data-fixed-day-hidden", usaUltimoDia);
        campoDia.disabled = usaUltimoDia;
    }

    ["fechamento", "vencimento"].forEach((tipo) => {
        formularioCartao.querySelectorAll(`input[name="regra_${tipo}"]`).forEach(
            (campo) => campo.addEventListener("change", () => atualizarCampoDeDia(tipo)),
        );
        atualizarCampoDeDia(tipo);
    });
}

const formularioCompra = document.querySelector("[data-purchase-form]");
if (formularioCompra) {
    const campoData = formularioCompra.querySelector("#id_data_compra");
    const fechamento = formularioCompra.querySelector("[data-preview-close]");
    const vencimento = formularioCompra.querySelector("[data-preview-due]");
    const campoAlterar = formularioCompra.querySelector("#id_alterar_fatura");
    const grupoFatura = formularioCompra.querySelector("[data-invoice-choice]");
    const campoFatura = formularioCompra.querySelector("#id_fatura_destino");

    function atualizarEscolhaManual() {
        const ativa = Boolean(campoAlterar?.checked);
        if (grupoFatura) grupoFatura.hidden = !ativa;
        if (campoFatura) campoFatura.disabled = !ativa;
    }

    async function atualizarPrevia() {
        if (!campoData?.value) return;
        const url = new URL(formularioCompra.dataset.previewUrl, window.location.origin);
        url.searchParams.set("data", campoData.value);
        try {
            const resposta = await fetch(url, {headers: {"Accept": "application/json"}});
            if (!resposta.ok) return;
            const dados = await resposta.json();
            if (fechamento) fechamento.textContent = dados.fechamento;
            if (vencimento) vencimento.textContent = dados.vencimento;
        } catch (erro) {
            // A validação no servidor continua sendo a fonte de verdade.
        }
    }

    campoAlterar?.addEventListener("change", atualizarEscolhaManual);
    campoData?.addEventListener("change", atualizarPrevia);
    atualizarEscolhaManual();
}
