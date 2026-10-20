const formularioEntrada = document.querySelector("[data-entry-form]");

if (formularioEntrada) {
    const configuracoesElemento = document.querySelector("#configuracoes-dizimo");
    const configuracoes = configuracoesElemento
        ? JSON.parse(configuracoesElemento.textContent)
        : {};

    const pessoa = formularioEntrada.querySelector("#id_pessoa");
    const tipo = formularioEntrada.querySelector("#id_tipo");
    const calcular = formularioEntrada.querySelector("#id_calcular_dizimo");
    const forma = formularioEntrada.querySelector("#id_forma_calculo");
    const percentual = formularioEntrada.querySelector("#id_percentual_dizimo");
    const valorManual = formularioEntrada.querySelector("#id_valor_dizimo_manual");

    const camposDeDizimoDisponiveis = Boolean(
        pessoa && tipo && calcular && forma && percentual && valorManual,
    );

    function atualizarCamposVisiveis() {
        if (!camposDeDizimoDisponiveis) return;
        const deveCalcular = calcular.checked;
        const usaPercentual = forma.value === "percentual";
        const usaValorManual = forma.value === "valor_manual";

        formularioEntrada.querySelector('[data-field-name="forma_calculo"]').hidden = !deveCalcular;
        formularioEntrada.querySelector('[data-field-name="percentual_dizimo"]').hidden =
            !deveCalcular || !usaPercentual;
        formularioEntrada.querySelector('[data-field-name="valor_dizimo_manual"]').hidden =
            !deveCalcular || !usaValorManual;
    }

    function aplicarConfiguracao() {
        if (!camposDeDizimoDisponiveis) return;
        const configuracao = configuracoes[`${pessoa.value}:${tipo.value}`];
        if (!configuracao) {
            calcular.checked = false;
            forma.value = "";
            percentual.value = "";
            valorManual.value = "";
        } else {
            calcular.checked = configuracao.calcular;
            forma.value = configuracao.forma;
            percentual.value = configuracao.percentual;
            valorManual.value = configuracao.valorManual;
        }
        atualizarCamposVisiveis();
    }

    if (camposDeDizimoDisponiveis) {
        pessoa.addEventListener("change", aplicarConfiguracao);
        tipo.addEventListener("change", aplicarConfiguracao);
        calcular.addEventListener("change", atualizarCamposVisiveis);
        forma.addEventListener("change", atualizarCamposVisiveis);
        atualizarCamposVisiveis();
    }
}
