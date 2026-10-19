import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("entradas", "0003_entrada_atalho_observacao")]

    operations = [
        migrations.AlterField(
            model_name="entrada",
            name="conta_destino",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="entradas",
                to="contas.conta",
                verbose_name="conta de destino",
            ),
        )
    ]
