from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("contas", "0003_regras_e_visual_do_cartao")]

    operations = [
        migrations.AlterField(
            model_name="cartaocredito",
            name="cor_simbolo",
            field=models.CharField(
                choices=[
                    ("roxo", "Roxo"),
                    ("amarelo", "Amarelo"),
                    ("verde", "Verde"),
                    ("azul", "Azul"),
                    ("vermelho", "Vermelho"),
                    ("preto", "Preto"),
                ],
                default="roxo",
                max_length=10,
                verbose_name="cor do símbolo",
            ),
        ),
    ]
