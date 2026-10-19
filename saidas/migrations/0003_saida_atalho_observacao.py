import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0001_atalholancamento"), ("saidas", "0002_saida_autor_saida_proprietario_usuario_and_more")]

    operations = [
        migrations.AddField(model_name="saida", name="atalho", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="saidas", to="core.atalholancamento")),
        migrations.AddField(model_name="saida", name="categoria_atalho", field=models.CharField(blank=True, editable=False, max_length=30)),
        migrations.AddField(model_name="saida", name="observacao", field=models.CharField(blank=True, max_length=200, verbose_name="observação")),
    ]
