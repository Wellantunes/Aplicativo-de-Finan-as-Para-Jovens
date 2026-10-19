from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("cartoes", "0003_compracredito_autor_and_more"),
        ("contas", "0003_regras_e_visual_do_cartao"),
    ]

    operations = [
        migrations.AlterField(
            model_name="pagamentofatura",
            name="conta",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="pagamentos_fatura",
                to="contas.conta",
                verbose_name="conta utilizada",
            ),
        ),
    ]
