from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("usuarios", "0003_usuario_compartilhar_novos_lancamentos_and_more")]

    operations = [
        migrations.AddField(
            model_name="usuario",
            name="avatar_concluido",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="usuario",
            name="avatar_pele",
            field=models.CharField(choices=[("clara", "Clara"), ("media", "Média"), ("escura", "Escura")], default="media", max_length=10, verbose_name="pele"),
        ),
        migrations.AddField(
            model_name="usuario",
            name="avatar_cabelo",
            field=models.CharField(choices=[("preto", "Preto"), ("castanho", "Castanho"), ("loiro", "Loiro"), ("ruivo", "Ruivo"), ("raspado", "Raspado")], default="castanho", max_length=10, verbose_name="cabelo"),
        ),
        migrations.AddField(
            model_name="usuario",
            name="avatar_olhos",
            field=models.CharField(choices=[("castanhos", "Castanhos"), ("azuis", "Azuis"), ("verdes", "Verdes")], default="castanhos", max_length=10, verbose_name="olhos"),
        ),
        migrations.AddField(
            model_name="usuario",
            name="avatar_sobrancelhas",
            field=models.CharField(choices=[("suaves", "Suaves"), ("marcadas", "Marcadas")], default="suaves", max_length=10, verbose_name="sobrancelhas"),
        ),
        migrations.AddField(
            model_name="usuario",
            name="avatar_barba",
            field=models.CharField(choices=[("sem_barba", "Sem barba"), ("barba", "Barba"), ("cavanhaque", "Cavanhaque")], default="sem_barba", max_length=12, verbose_name="barba"),
        ),
        migrations.AddField(
            model_name="usuario",
            name="avatar_oculos",
            field=models.CharField(choices=[("sem_oculos", "Sem óculos"), ("redondos", "Redondos"), ("quadrados", "Quadrados")], default="sem_oculos", max_length=12, verbose_name="óculos"),
        ),
        migrations.AddField(
            model_name="usuario",
            name="avatar_roupa",
            field=models.CharField(choices=[("azul", "Azul"), ("coral", "Coral"), ("dourada", "Dourada")], default="azul", max_length=10, verbose_name="roupa"),
        ),
    ]
