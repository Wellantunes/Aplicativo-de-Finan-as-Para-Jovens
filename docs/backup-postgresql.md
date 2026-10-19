# Backup e restauração do PostgreSQL

Este documento não significa que o backup esteja agendado ou sendo monitorado.
O responsável pela infraestrutura deve configurar e acompanhar a execução no
ambiente que hospeda o banco.

## Backup diário

Use uma conta com permissão de leitura no banco e guarde a senha em `.pgpass` ou
em um gerenciador de segredos. Não coloque a senha no comando ou no repositório.

```powershell
pg_dump --host=SERVIDOR --username=USUARIO_BACKUP --format=custom --file=dropduo-AAAA-MM-DD.dump BANCO_PRODUCAO
```

Agende o comando diariamente no serviço de tarefas da infraestrutura. Mantenha,
como ponto de partida, 7 cópias diárias, 4 semanais e 6 mensais. Armazene uma
cópia criptografada fora do servidor da aplicação e restrinja o acesso.

## Validação e restauração

Nunca teste a restauração sobre o banco de produção. Crie um banco isolado e
restaure nele:

```powershell
createdb --host=SERVIDOR --username=ADMIN dropduo_restore_test
pg_restore --host=SERVIDOR --username=ADMIN --dbname=dropduo_restore_test --clean --if-exists dropduo-AAAA-MM-DD.dump
```

Depois, execute com as variáveis apontando para o banco isolado:

```powershell
python manage.py check
python manage.py showmigrations
```

Valide periodicamente usuários, salas, lançamentos, faturas e vínculos. Registre
data, responsável, duração e resultado do teste. Exclua o banco isolado somente
depois da conferência.
