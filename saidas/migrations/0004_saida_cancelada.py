from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("saidas", "0003_saida_atalho_observacao")]

    operations = [
        migrations.AlterField(
            model_name="saida",
            name="situacao",
            field=models.CharField(
                choices=[
                    ("pendente", "A pagar"),
                    ("paga", "Paga"),
                    ("cancelada", "Cancelada"),
                ],
                default="pendente",
                max_length=10,
                verbose_name="situação",
            ),
        ),
    ]
