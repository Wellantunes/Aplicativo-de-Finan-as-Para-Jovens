const formularioSaida = document.querySelector("[data-expense-form]");

if (formularioSaida) {
    const situacao = formularioSaida.querySelector("#id_situacao");
    const camposPendentes = ["vencimento"];
    const camposPagos = ["data_pagamento", "forma_pagamento", "conta"];

    function atualizarCamposVisiveis() {
        if (!situacao) return;
        const estaPaga = situacao.value === "paga";

        camposPendentes.forEach((nome) => {
            const grupo = formularioSaida.querySelector(`[data-field-name="${nome}"]`);
            if (grupo) grupo.hidden = estaPaga;
        });
        camposPagos.forEach((nome) => {
            const grupo = formularioSaida.querySelector(`[data-field-name="${nome}"]`);
            if (grupo) grupo.hidden = !estaPaga;
        });
    }

    if (situacao) {
        situacao.addEventListener("change", atualizarCamposVisiveis);
        atualizarCamposVisiveis();
    }
}
