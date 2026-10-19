# Padrões de desenvolvimento

Este projeto deve permanecer fácil de entender para uma pessoa desenvolvedora
júnior e para qualquer pessoa que assuma sua manutenção no futuro.

## Código

- Escolha a solução mais simples que atenda completamente ao requisito atual.
- Evite abstrações prematuras, camadas desnecessárias e arquiteturas complexas.
- Use nomes claros e intuitivos para módulos, classes, funções e variáveis.
- Mantenha o idioma e as convenções já adotados no contexto; não misture padrões
  sem necessidade.
- Crie funções e classes pequenas, com uma responsabilidade bem definida.
- Prefira fluxo explícito a atalhos difíceis de ler ou código excessivamente
  compacto.
- Evite duplicação relevante, mas não crie abstrações apenas para eliminar duas
  linhas semelhantes.
- Adicione comentários para explicar decisões e motivos, não para repetir o que
  o código já diz.
- Escreva mensagens de erro claras e trate falhas de maneira previsível.

## Arquitetura e dependências

- Preserve uma arquitetura simples e adequada ao tamanho atual do projeto.
- Não antecipe funcionalidades que ainda não foram solicitadas.
- Adicione uma dependência somente quando ela trouxer benefício claro e não
  houver uma alternativa simples com a biblioteca padrão ou o framework.
- Siga primeiro as convenções do Django e depois as convenções locais.

## Qualidade

- Inclua ou atualize testes para comportamentos novos e correções importantes.
- Execute verificações e testes relevantes antes de concluir uma alteração.
- Mantenha segredos e configurações locais fora do Git.
- Atualize o README quando mudarem instalação, configuração ou uso do projeto.
- Entregue o repositório sem arquivos temporários ou artefatos de validação.

## Comunicação

- Explique mudanças em linguagem direta, considerando que o responsável pelo
  projeto está aprendendo.
- Ao introduzir um conceito menos comum, explique brevemente por que ele é
  necessário.
- Destaque decisões e possíveis riscos sem usar jargão desnecessário.
