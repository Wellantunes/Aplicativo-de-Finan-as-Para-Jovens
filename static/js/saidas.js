const formularioSaida = document.querySelector("[data-expense-form]");

if (formularioSaida) {
    const situacao = formularioSaida.querySelector("#id_situacao");
    const camposPendentes = ["vencimento"];
    const camposPagos = ["data_pagamento", "forma_pagamento", "conta"];

    function atualizarCamposVisiveis() {
        const estaPaga = situacao.value === "paga";

        camposPendentes.forEach((nome) => {
            formularioSaida.querySelector(`[data-field-name="${nome}"]`).hidden = estaPaga;
        });
        camposPagos.forEach((nome) => {
            formularioSaida.querySelector(`[data-field-name="${nome}"]`).hidden = !estaPaga;
        });
    }

    situacao.addEventListener("change", atualizarCamposVisiveis);
    atualizarCamposVisiveis();
}
