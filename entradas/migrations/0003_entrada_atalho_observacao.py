import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0001_atalholancamento"), ("entradas", "0002_remove_configuracaodizimo_configuracao_dizimo_unica_por_pessoa_tipo_and_more")]

    operations = [
        migrations.AddField(model_name="entrada", name="atalho", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="entradas", to="core.atalholancamento")),
        migrations.AddField(model_name="entrada", name="categoria_atalho", field=models.CharField(blank=True, editable=False, max_length=30)),
        migrations.AddField(model_name="entrada", name="observacao", field=models.CharField(blank=True, max_length=200, verbose_name="observação")),
    ]
