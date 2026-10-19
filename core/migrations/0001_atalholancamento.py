import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("contas", "0002_cartaocredito_autor_and_more"),
        ("salas", "0003_sala_controlar_dizimos"),
        ("usuarios", "0004_usuario_avatar"),
    ]

    operations = [
        migrations.CreateModel(
            name="AtalhoLancamento",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome", models.CharField(max_length=60, verbose_name="nome")),
                ("tipo", models.CharField(choices=[("entrada", "Entrada"), ("saida", "Saída")], max_length=10, verbose_name="tipo")),
                ("simbolo", models.CharField(choices=[("generico", "Genérico"), ("casa", "Casa"), ("alimentacao", "Alimentação"), ("carteira", "Carteira"), ("entrada", "Entrada"), ("coracao", "Coração"), ("moedas", "Moedas"), ("calendario", "Calendário"), ("lista", "Lista")], default="generico", max_length=30, verbose_name="símbolo")),
                ("cor", models.CharField(choices=[("azul", "Azul"), ("coral", "Coral"), ("dourado", "Dourado"), ("verde", "Verde"), ("azul_claro", "Azul claro")], default="azul", max_length=15, verbose_name="cor de destaque")),
                ("categoria", models.CharField(max_length=30, verbose_name="categoria financeira")),
                ("ordem", models.PositiveIntegerField(default=0)),
                ("arquivado", models.BooleanField(default=False)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                ("conta_padrao", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="atalhos_padrao", to="contas.conta", verbose_name="conta padrão")),
                ("proprietario_usuario", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="atalhos_lancamento", to=settings.AUTH_USER_MODEL)),
                ("sala", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="atalhos_lancamento", to="salas.sala")),
            ],
            options={"verbose_name": "atalho de lançamento", "verbose_name_plural": "atalhos de lançamento", "ordering": ["tipo", "ordem", "nome", "pk"]},
        ),
        migrations.AddConstraint(
            model_name="atalholancamento",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(sala__isnull=False, proprietario_usuario__isnull=True)
                    | models.Q(sala__isnull=True, proprietario_usuario__isnull=False)
                ),
                name="atalho_um_proprietario",
            ),
        ),
    ]
