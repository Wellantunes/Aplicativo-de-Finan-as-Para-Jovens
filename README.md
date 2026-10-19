# Drop Duo

Aplicativo financeiro Django mobile-first. Cada pessoa possui um espaço
individual completo e pode, opcionalmente, compartilhar recursos e lançamentos
com uma sala de até dois participantes. Login Google, contas, cartões, entradas,
dízimos, saídas, parcelas, faturas e dashboard mensal estão disponíveis.

## Requisitos

- Python 3.10 ou superior
- PostgreSQL 17 ou compatível
- PowerShell (para os exemplos abaixo)

## 1. Instalar as dependências

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## 2. Preencher as variáveis de ambiente

Crie o arquivo local a partir do exemplo:

```powershell
Copy-Item .env.example .env
```

Edite o `.env` e substitua os valores de exemplo. As configurações disponíveis
são:

- `DJANGO_SECRET_KEY`: chave secreta da aplicação.
- `DJANGO_DEBUG`: ativa ou desativa o modo de desenvolvimento.
- `DJANGO_ALLOWED_HOSTS`: hosts permitidos, separados por vírgula.
- `DATABASE_ENGINE`: backend do banco; use `django.db.backends.postgresql`.
- `DATABASE_NAME`, `DATABASE_USER` e `DATABASE_PASSWORD`: credenciais do banco.
- `DATABASE_HOST` e `DATABASE_PORT`: endereço e porta do PostgreSQL.
- `TEST_DATABASE_NAME`: banco PostgreSQL de testes pré-criado (opcional).
- `DJANGO_STATIC_ROOT`: destino do `collectstatic` (opcional).
- `GOOGLE_OAUTH_CLIENT_ID`: identificador público do cliente OAuth.
- `GOOGLE_OAUTH_CLIENT_SECRET`: segredo do cliente OAuth.

O `.env` é ignorado pelo Git. Somente o `.env.example`, sem senhas reais, deve
ser versionado.

## 3. Preparar o banco

Crie um usuário e um banco exclusivos no PostgreSQL. No ambiente local atual:

- serviço: `postgresql-x64-17`;
- banco: `financeiro_db`;
- usuário da aplicação: `financeiro_user`;
- endereço: `127.0.0.1:5432`.

As senhas permanecem apenas no `.env` local.

## 4. Executar as migrações

```powershell
python manage.py migrate
python manage.py createsuperuser
python manage.py check
```

## 5. Iniciar o servidor local

```powershell
python manage.py runserver
```

Acesse:

- página inicial: `http://127.0.0.1:8000/`
- administração: `http://127.0.0.1:8000/admin/`

## Login Google

No Google Cloud, configure o retorno OAuth com a mesma origem usada para abrir o
servidor local:

- `http://127.0.0.1:8000/accounts/google/login/callback/`
- `http://localhost:8000/accounts/google/login/callback/`

O acesso público é exclusivamente pelo Google; cadastro e recuperação de senha
do `django-allauth` ficam desativados. O login por senha do Django permanece
disponível somente no painel administrativo. A saída da sessão usa uma
requisição POST protegida por CSRF.

Após o login, o usuário retorna ao espaço individual. Nome, e-mail e foto de
perfil são sincronizados quando disponibilizados pelo Google, mas o app exibe o
avatar próprio configurado pela pessoa. Novos usuários veem uma configuração
curta e opcional de renda prevista, dízimo e primeiro cadastro.

O endereço de retorno precisa coincidir exatamente com o cadastrado no Google,
inclusive protocolo, host e porta. O ambiente local usa a porta `8000`; trocar
para outra porta não corrige `redirect_uri_mismatch`. Use o mesmo endereço para
abrir o app e para cadastrar o callback.

## Espaço individual e propriedade

O app funciona sem sala. Contas, cartões e lançamentos individuais pertencem ao
usuário. A renda mensal informada no perfil é apenas uma previsão: ela não cria
entrada nem altera saldo. O orçamento individual também é informativo.

Cada cadastro possui exatamente um proprietário: um usuário ou uma sala. O
autor registra quem fez o cadastro e o responsável atribui a receita ou despesa.
Constraints no banco impedem propriedade ausente ou ambígua.

Ao compartilhar, o registro individual continua pertencendo ao titular e ganha
uma referência para a sala. Nada é copiado. Assim, saldos, parcelas e faturas não
são somados duas vezes. Um registro criado dentro da sala pertence somente à
sala e não aparece como gasto pessoal dos participantes.

## Sala compartilhada

A tela **Salas** sempre mostra uma listagem. Um usuário sem sala pode:

- criar uma sala informando nome e orçamento mensal previsto;
- entrar em uma sala existente com um código de convite.

Ao criar a sala, o sistema gera um convite de uso único, válido por 24 horas.
Antes de aceitar, a outra pessoa vê o nome e o orçamento da sala. Cada usuário pode
participar de apenas uma sala e cada sala aceita no máximo duas pessoas.

Mesmo quando participa de uma sala, o login abre o espaço individual. O botão
**Entrar na sala** troca explicitamente para o espaço compartilhado, e **Voltar
ao meu espaço** retorna ao individual. A listagem mostra nomes e fotos dos
participantes, sem exibir seus e-mails.

O orçamento aceita zero, recusa números negativos e representa somente uma
previsão. Ele não cria despesas nem altera saldos.

O acesso às páginas da sala é conferido no backend. Alterar o número da sala na
URL não permite que uma pessoa externa visualize seus dados. A entrada usa uma
transação e bloqueio de linha no PostgreSQL para preservar o limite mesmo se
duas pessoas tentarem aceitar convites ao mesmo tempo.

## Compartilhamento, contas e cartões

Contas e cartões podem pertencer ao usuário ou à sala. Os dois participantes
administram recursos da sala; somente o proprietário administra um recurso
individual, mesmo quando ele está compartilhado.

No perfil, **Gerenciar compartilhamento** permite selecionar contas, cartões e
o alcance dos lançamentos: nenhum, desde o início do mês ou todo o histórico.
Uma prévia é exibida antes da confirmação. Aceitar convite nunca compartilha o
histórico silenciosamente. A confirmação reconcilia a seleção: registros fora
do alcance escolhido deixam de ser compartilhados.

A opção **Compartilhar novos lançamentos individuais por padrão** vale para
entradas, saídas, compras no crédito e registros rápidos criados depois da
ativação. Ela não altera o histórico. Registros rápidos sem conta também podem
ser compartilhados no fluxo retroativo. O registro continua pertencendo ao seu
autor, não é copiado e somente o proprietário pode alterá-lo. Se o proprietário
sair da sala, os participantes restantes deixam de enxergar seus registros
pessoais compartilhados.

Os cadastros incluem:

- contas em dinheiro, com saldo inicial e a data desse saldo;
- vales-alimentação, mantidos separadamente das contas em dinheiro;
- cartões de crédito, com cor do símbolo e regras independentes de fechamento
  e vencimento.

As cores disponíveis para o símbolo do cartão incluem roxo, amarelo, verde,
azul, vermelho e preto. A cor escolhida acompanha o cartão nas listagens e no
registro de compras em **Lançamentos → Saída**.

O titular sempre deve participar da sala. O saldo inicial é somente o ponto de
partida do cadastro e não gera receita. Os cartões não armazenam limite, número,
validade ou código de segurança. Cada regra pode usar um dia fixo de 1 a 31 ou
o último dia do mês. Um dia fixo inexistente é ajustado para o último dia
disponível, mas continua sendo diferente da regra “último dia do mês”.

Uma conta compartilhada exibe o saldo real uma única vez. Esse saldo pode ser
influenciado por movimentos privados, mas os detalhes privados do titular não
são mostrados à outra pessoa. O mesmo vale para cartões: a sala diferencia o total
real da fatura do subtotal de parcelas autorizadas. A outra pessoa não pode pagar
uma fatura individual; o titular deve registrar o pagamento.

Todas as consultas e alterações conferem propriedade e participação no backend.
Uma pessoa externa não acessa os dados pela URL, e o outro participante não edita nem
exclui registros individuais alheios.

## Entradas e dízimos

As entradas comuns registram o valor líquido recebido ou esperado sem exigir
uma conta bancária ou carteira. O mês financeiro é definido pela data prevista
do lançamento, mesmo quando a confirmação acontece depois. Vínculos com contas
existentes em registros antigos continuam preservados e acessíveis.

O dízimo previsto pode usar percentual ou valor manual e fica salvo no próprio
lançamento. Alterar a configuração padrão depois não recalcula entradas antigas.
O valor previsto não é uma saída realizada. A devolução continua sendo uma
operação especial e, quando usa uma conta antiga, reduz seu saldo uma única vez.

Devoluções parciais são permitidas até atingir o valor previsto. A tela mostra
os valores previsto, devolvido e restante. Mesmo quando a entrada original é um
vale-alimentação, a devolução utiliza uma conta em dinheiro.

Entradas sem devoluções podem ser editadas e excluídas, atualizando o resultado
do mês correspondente. Depois que existe uma devolução vinculada, edição e exclusão
ficam bloqueadas nesta versão para preservar o histórico. Formulários de entrada
e devolução possuem uma chave única para impedir duplicação em reenvios.

## Saídas à vista e contas pendentes

As saídas podem ser registradas como pendentes ou pagas. Uma pendência exige
vencimento e entra no resultado do respectivo mês sem reduzir o saldo de uma
conta. Uma saída comum paga também guarda a data efetiva; conta e forma de
pagamento não fazem parte desse fluxo simplificado. Vínculos financeiros de
registros antigos permanecem preservados.

Editar valor ou data de referência atualiza o resultado do mês correspondente.
Trocar entre paga e pendente atualiza somente o estado operacional, sem contar o
mesmo compromisso novamente. A ação de pagamento usa bloqueio de linha no
PostgreSQL para impedir registro duplicado em solicitações simultâneas.

A listagem geral de saídas mantém filtros por mês, responsável e situação. As
telas de Entradas e Custo de vida abrem diretamente o mês e o espaço escolhidos,
sem formulário de filtros visível. Pagas e pendentes permanecem no mês da data
de referência.

## Compras, parcelas e faturas

Cartões são cadastrados e consultados na tela **Cartões**. Para registrar uma
nova compra, abra **Lançamentos → Saída** e toque no cartão desejado. O formulário
compacto pede descrição, valor e data, mostra a fatura calculada e registra uma
única parcela nesta etapa. Compras parceladas antigas continuam preservadas e
podem ser consultadas no detalhe do cartão.

O ciclo usa o primeiro fechamento igual ou posterior à data da compra. Uma
compra feita no próprio dia do fechamento ainda entra nesse ciclo. O vencimento
é a primeira ocorrência da regra de vencimento posterior ao fechamento. **O mês
da fatura é sempre o mês do vencimento.** Por exemplo, fechamento em 25/10 e
vencimento em 05/11 formam a fatura de novembro.

O valor é distribuído em centavos sem perder nem acrescentar dinheiro. Dias de
fechamento e vencimento são ajustados ao último dia existente nos meses mais
curtos. Faturas do mesmo cartão e mês reúnem as parcelas correspondentes. As
datas de uma fatura específica podem ser corrigidas para acompanhar o calendário
do banco. A correção não altera as regras gerais nem move compras silenciosamente.
Alterar as regras do cartão afeta somente ciclos ainda não criados.

Registrar a compra não altera o saldo de uma conta. O pagamento integral pode
ser vinculado a uma conta em dinheiro ou apenas marcar a fatura como paga. Sem
conta, nenhum saldo bancário é alterado; pagamentos antigos continuam com seus
vínculos. Reenvios e pagamentos simultâneos são protegidos no backend. Compras
de faturas já pagas não podem ser editadas ou excluídas nesta versão,
preservando o histórico do pagamento.

Parcelas marcadas como custo de vida entram no mês da respectiva fatura.

## Dashboard mensal

O indicador principal é **Resultado do mês em dinheiro**. A fórmula exata é:

```text
entradas em dinheiro do mês
- saídas comuns em dinheiro do mês
- parcelas com vencimento no mês
- dízimos efetivamente devolvidos no mês
= resultado do mês em dinheiro
```

O card **Entradas do mês** soma dinheiro e vale e mostra somente o total. A
composição entre dinheiro e vale fica no topo da página de Entradas. O vale
também possui um card separado como detalhamento, sem duplicar o lançamento. As
entradas e saídas de vale-alimentação não aumentam nem reduzem silenciosamente o
**Resultado do mês**, que continua sendo exclusivamente em dinheiro. O custo de
vida e outros gastos continuam sendo uma visão de consumo e podem incluir vale.

Recebimentos e compromissos pendentes entram uma única vez no mês de referência,
inclusive quando a data ainda é futura. Registros cancelados ficam de fora. O
cálculo usa `Decimal`, não inclui saldo inicial de contas, não transporta sobra
ou déficit para o mês seguinte e permite resultado negativo. Pagamentos de
fatura não repetem as parcelas e devoluções de dízimo são subtraídas uma vez.

O painel individual funciona sem sala e mostra somente os registros pessoais,
além do saldo real das contas próprias. Efeitos de pagamentos feitos pela sala
continuam no saldo real, sem transformar o gasto da sala em gasto pessoal.

O painel da sala reúne registros pertencentes à sala e registros individuais
explicitamente compartilhados. Os filtros são **Todos**, cada participante e
**Da sala**. Este último usa a propriedade do registro; o filtro de pessoa usa o
responsável pelo lançamento.

Entradas em dinheiro e vale-alimentação aparecem na composição do total. O custo
de vida e os outros gastos usam a data prevista ou de referência do lançamento. Parcelas de
cartão entram no mês de vencimento da fatura. Já as saídas de dinheiro mostram
apenas valores que realmente saíram das contas, incluindo pagamentos de faturas,
sem somar as parcelas novamente.

Os cards **Entradas** e **Saídas** abrem as listagens do mesmo mês e espaço,
onde cada registro pode ser editado ou excluído conforme as permissões atuais.

Meses anteriores usam o saldo no último dia daquele mês. O mês atual usa a
posição de hoje. Os compromissos
reúnem contas e faturas ainda pendentes até o fim do mês, inclusive atrasadas,
além dos dízimos ainda não devolvidos.

No filtro individual, uma parcela pertence à pessoa responsável pela compra,
mesmo quando o cartão está no nome do outro participante.

### Datas previstas e confirmações

Uma entrada futura começa como **A receber** e uma saída futura começa como **A
pagar**. Esses registros entram imediatamente no resultado do mês da data de
referência. Ao confirmar o recebimento ou o pagamento, o mesmo registro recebe
a data efetiva; nenhum lançamento duplicado é criado e o resultado permanece no
mês original.

Se um pagamento previsto para novembro ocorrer em dezembro, ele permanece no
resultado de novembro. Somente uma alteração explícita na data de referência
move o lançamento para outro mês. Registros cancelados não entram nos totais.

Para dados históricos sem data prevista, o sistema usa a data efetiva como
fallback, sem reescrever os registros existentes.

## Experiência no celular

Usuários autenticados possuem uma barra inferior com acesso ao painel,
lançamentos, cartões e salas. Contas antigas permanecem preservadas e o perfil
mostra um acesso secundário somente para quem já possui uma conta individual
cadastrada. O fluxo principal não convida novos usuários a cadastrar contas.
O espaço atual fica sempre identificado. O botão
**Adicionar** permanece acessível nas
telas principais e abre atalhos para entrada, saída e compra no crédito.

Em **Lançamentos**, a pessoa escolhe Entrada ou Saída, toca em um item cadastrado,
informa valor e data e conclui. Na aba Saída, cartões ativos aparecem como opções
próprias e abrem a compra no crédito; eles não criam itens duplicados. Não existe
aba Histórico nem escolha de conta nesse fluxo. Cada item possui nome e um
símbolo próprio de Entrada ou Saída. O tipo vem da aba em que **Novo item** foi
aberto e não precisa ser escolhido novamente. O item pode ser editado ou
arquivado sem apagar lançamentos anteriores.

O card **Vale no mês** e o item **Vale-alimentação** de Lançamentos abrem o
mesmo formulário rápido, com valor, descrição e data. Esse registro é classificado
explicitamente como benefício, permanece separado do dinheiro e não cria um
item auxiliar no banco.
O registro rápido funciona sem conta bancária: ele entra no resultado do mês,
mas não altera arbitrariamente o saldo de uma conta. Registros antigos que já
possuem conta continuam preservados.

Os catálogos de símbolos são separados: atualmente existem 7 opções para
Entrada e 54 para Saída. Um símbolo do tipo oposto é rejeitado também no
backend. Os PNGs antigos permanecem somente como fallback de registros legados;
não aparecem como opções em novos cadastros.

As listagens possuem paginação. Filtros aparecem apenas nos fluxos em que ajudam;
Entradas e Custo de vida mostram diretamente o mês e o espaço selecionados.
Os formulários usam teclado decimal ou numérico nos campos apropriados, exibem
os erros junto ao campo e bloqueiam novos envios enquanto uma solicitação está
em andamento. Quando o aparelho fica sem internet, a interface avisa para
aguardar a conexão antes de enviar dados.

O dashboard possui a opção **Ocultar valores**. Essa preferência fica somente
no navegador usado pela pessoa e não altera nenhum lançamento.

O manifesto e o ícone permitem adicionar o app à tela inicial pelo menu do
navegador. No Android, use **Adicionar à tela inicial**. No iPhone, abra o menu
de compartilhamento do Safari e escolha **Adicionar à Tela de Início**.

Esta instalação não transforma o projeto em aplicativo de loja. Não existe
modo offline nem service worker nesta versão: uma conexão ativa continua sendo
necessária para consultar ou registrar dados. Respostas autenticadas usam
`no-store` para evitar que páginas financeiras sejam guardadas no cache local.

## Testes

Para testar bloqueios e concorrência reais, use um banco PostgreSQL separado.
Um administrador do PostgreSQL precisa executar apenas:

```sql
CREATE DATABASE financeiro_test OWNER financeiro_user;
```

Depois, defina `TEST_DATABASE_NAME=financeiro_test` no `.env` e preserve o banco
pré-criado com `--keepdb`. O usuário da aplicação não precisa receber
`SUPERUSER` nem `CREATEDB`:

```powershell
python manage.py test --keepdb --noinput
```

A configuração é recusada quando `TEST_DATABASE_NAME` é igual a `DATABASE_NAME`,
evitando que a suíte use por engano o banco de desenvolvimento.

Para uma verificação funcional rápida, SQLite pode ser usado, mas os testes de
concorrência que dependem de bloqueio de linha são pulados nesse backend:

```powershell
$env:DATABASE_ENGINE = "django.db.backends.sqlite3"
$env:DATABASE_NAME = ":memory:"
$env:TEST_DATABASE_NAME = ""
python manage.py test
```

Antes de entregar mudanças, confira também migrações e arquivos estáticos:

```powershell
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py collectstatic --noinput
```

Para validar `collectstatic` sem misturar a saída com o projeto, defina
temporariamente `DJANGO_STATIC_ROOT` para uma pasta vazia.

## Configurações do projeto

- idioma: português do Brasil (`pt-br`);
- fuso horário: `America/Cuiaba`;
- datas com suporte a fuso horário (`USE_TZ = True`);
- usuário customizado: `usuarios.Usuario`;
- autenticação: `django-allauth`, com o provider Google registrado;
- interface compartilhada mobile-first.

As credenciais OAuth do Google são carregadas exclusivamente pelo `.env`. Nenhum
Client ID ou Client Secret deve ser adicionado diretamente ao código.

## Estrutura

- `config`: configurações e rotas principais.
- `cartoes`: compras no crédito, parcelas, faturas e pagamentos.
- `contas`: contas em dinheiro, vales-alimentação e cartões de crédito.
- `core`: página inicial e estrutura visual compartilhada.
- `dashboard`: cálculos e tela do resumo financeiro mensal.
- `entradas`: entradas, configurações e devoluções de dízimos.
- `saidas`: saídas à vista, contas pendentes e pagamentos.
- `salas`: sala compartilhada, participantes e convites temporários.
- `usuarios`: modelo de usuário customizado.
- `templates`: templates HTML globais.
- `static`: CSS, JavaScript e imagens.

## Limitações de produção

O projeto está preparado para desenvolvimento e piloto local, não para ser
publicado apenas executando `runserver`. Um ambiente de produção ainda precisa
de HTTPS, cookies seguros, `DEBUG=False`, chave secreta forte, host e proxy
confiáveis, servidor WSGI/ASGI, serviço de arquivos estáticos, backups,
monitoramento e credenciais OAuth de produção. `manage.py check` sozinho não
comprova prontidão para publicação.

### Configuração de produção preparada

Use `DJANGO_ENV=production`. Nesse modo, o projeto recusa `DEBUG=True`, SQLite,
hosts vazios ou com `*` e origens CSRF ausentes ou sem HTTPS. Preencha também:

```text
DJANGO_SECRET_KEY=<chave longa e aleatória>
DJANGO_ALLOWED_HOSTS=app.exemplo.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://app.exemplo.com
DJANGO_SECURE_SSL_REDIRECT=True
DJANGO_SESSION_COOKIE_SECURE=True
DJANGO_CSRF_COOKIE_SECURE=True
```

HSTS começa desativado. Depois de confirmar que todo o domínio funciona apenas
por HTTPS, ative um valor curto, como `DJANGO_SECURE_HSTS_SECONDS=300`, acompanhe
o ambiente e aumente gradualmente. Não habilite subdomínios ou preload antes de
validar todos os endereços afetados.

Enquanto `DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS` e
`DJANGO_SECURE_HSTS_PRELOAD` permanecerem desativados, `check --deploy` informa
os alertas `security.W005` e `security.W021`. Eles são mantidos de propósito até
a infraestrutura comprovar que todos os subdomínios usam HTTPS e que o domínio
pode entrar com segurança na lista de preload.

`DJANGO_TRUST_PROXY_SSL_HEADER=True` deve ser usado somente quando um proxy
confiável remover o cabeçalho recebido do público e definir
`X-Forwarded-Proto`. Sem essa garantia, mantenha a opção desativada.

Em um servidor Linux, depois de instalar as dependências e executar
`collectstatic`, a aplicação pode ser iniciada com:

```powershell
gunicorn config.wsgi:application --config gunicorn.conf.py
```

O WhiteNoise entrega os arquivos gerados em `STATIC_ROOT`; o proxy deve servir
HTTPS e encaminhar as requisições ao Gunicorn. Logs de erro vão para a saída do
processo e não incluem corpos de formulários. A infraestrutura deve coletar essa
saída e definir retenção e alertas.

O procedimento de backup e restauração está em
`docs/backup-postgresql.md`. Os arquivos de CI apenas executam verificações; não
fazem implantação, backup ou monitoramento.

### OAuth por ambiente

O Google Cloud precisa possuir exatamente os callbacks dos endereços usados:

```text
http://127.0.0.1:8000/accounts/google/login/callback/
http://localhost:8000/accounts/google/login/callback/
https://app.exemplo.com/accounts/google/login/callback/
```

Substitua `app.exemplo.com` pelo host real de produção. O callback HTTPS só pode
ser considerado validado depois de um login real no ambiente publicado.

## Identidade visual

A interface usa a identidade **Drop Duo**, com paleta centralizada no arquivo
`static/css/style.css`: creme `#FFF4DC`, azul `#2855D9`, coral `#EF6A50` e
dourado `#E9B949`. O app usa PNGs pixelados em `static/dropduo`, incluindo os
catálogos de itens, e SVGs auxiliares em `static/images`. Textos e valores
financeiros continuam sendo HTML dinâmico e acessível.

Os títulos curtos usam **Pixelify Sans**, armazenada localmente em
`static/fonts`. A fonte é distribuída sob a SIL Open Font License 1.1; uma cópia
da licença está em `static/fonts/OFL-PixelifySans.txt`. Formulários e valores
usam uma fonte comum do sistema para manter a leitura confortável.
