from django.db import migrations


def usar_mes_do_vencimento(apps, schema_editor):
    Fatura = apps.get_model("cartoes", "Fatura")
    referencias = [
        (fatura.pk, fatura.data_vencimento.year, fatura.data_vencimento.month)
        for fatura in Fatura.objects.all().iterator()
    ]

    # A referência temporária evita colisões com a restrição única durante a troca.
    for fatura_id, ano, _ in referencias:
        Fatura.objects.filter(pk=fatura_id).update(ano_referencia=ano + 10000)

    for fatura_id, ano, mes in referencias:
        Fatura.objects.filter(pk=fatura_id).update(
            ano_referencia=ano,
            mes_referencia=mes,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("cartoes", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            usar_mes_do_vencimento,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
