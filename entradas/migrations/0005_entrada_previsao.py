from django.db import migrations, models


def preservar_datas_existentes(apps, schema_editor):
    Entrada = apps.get_model("entradas", "Entrada")
    Entrada.objects.update(
        situacao="recebida",
        data_prevista=models.F("data"),
    )


class Migration(migrations.Migration):
    dependencies = [("entradas", "0004_entrada_conta_destino_opcional")]

    operations = [
        migrations.AddField(
            model_name="entrada",
            name="situacao",
            field=models.CharField(
                choices=[
                    ("a_receber", "A receber"),
                    ("recebida", "Recebida"),
                    ("cancelada", "Cancelada"),
                ],
                default="recebida",
                max_length=12,
                verbose_name="situação",
            ),
        ),
        migrations.AddField(
            model_name="entrada",
            name="data_prevista",
            field=models.DateField(blank=True, null=True, verbose_name="data prevista"),
        ),
        migrations.AlterField(
            model_name="entrada",
            name="data",
            field=models.DateField(blank=True, null=True, verbose_name="data do recebimento"),
        ),
        migrations.RunPython(preservar_datas_existentes, migrations.RunPython.noop),
    ]
