from django.db import migrations, models


def preservar_salas_que_ja_usam_dizimos(apps, schema_editor):
    Sala = apps.get_model("salas", "Sala")
    ConfiguracaoDizimo = apps.get_model("entradas", "ConfiguracaoDizimo")
    Entrada = apps.get_model("entradas", "Entrada")

    salas_com_dizimo = set(
        ConfiguracaoDizimo.objects.filter(
            sala_id__isnull=False,
            calcular_dizimo=True,
        ).values_list("sala_id", flat=True)
    )
    salas_com_dizimo.update(
        Entrada.objects.filter(
            sala_id__isnull=False,
            calcular_dizimo=True,
        ).values_list("sala_id", flat=True)
    )
    Sala.objects.filter(pk__in=salas_com_dizimo).update(controlar_dizimos=True)


class Migration(migrations.Migration):
    dependencies = [
        ("salas", "0002_sala_simbolo_sala_tipo"),
        ("entradas", "0002_remove_configuracaodizimo_configuracao_dizimo_unica_por_pessoa_tipo_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="sala",
            name="controlar_dizimos",
            field=models.BooleanField(default=False, verbose_name="esta sala vai controlar dízimos?"),
        ),
        migrations.RunPython(
            preservar_salas_que_ja_usam_dizimos,
            migrations.RunPython.noop,
        ),
    ]
