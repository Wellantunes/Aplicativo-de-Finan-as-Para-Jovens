from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):
    dependencies = [("contas", "0002_cartaocredito_autor_and_more")]

    operations = [
        migrations.AddField(
            model_name="cartaocredito",
            name="arquivado",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="cartaocredito",
            name="cor_simbolo",
            field=models.CharField(
                choices=[
                    ("roxo", "Roxo"),
                    ("amarelo", "Amarelo"),
                    ("verde", "Verde"),
                    ("azul", "Azul"),
                    ("preto", "Preto"),
                ],
                default="roxo",
                max_length=10,
                verbose_name="cor do símbolo",
            ),
        ),
        migrations.AddField(
            model_name="cartaocredito",
            name="regra_fechamento",
            field=models.CharField(
                choices=[
                    ("dia_fixo", "Dia fixo"),
                    ("ultimo_dia", "Último dia do mês"),
                ],
                default="dia_fixo",
                max_length=12,
                verbose_name="regra de fechamento",
            ),
        ),
        migrations.AddField(
            model_name="cartaocredito",
            name="regra_vencimento",
            field=models.CharField(
                choices=[
                    ("dia_fixo", "Dia fixo"),
                    ("ultimo_dia", "Último dia do mês"),
                ],
                default="dia_fixo",
                max_length=12,
                verbose_name="regra de vencimento",
            ),
        ),
        migrations.AlterField(
            model_name="cartaocredito",
            name="dia_fechamento",
            field=models.PositiveSmallIntegerField(
                blank=True,
                null=True,
                validators=[
                    django.core.validators.MinValueValidator(1),
                    django.core.validators.MaxValueValidator(31),
                ],
                verbose_name="dia de fechamento",
            ),
        ),
        migrations.AlterField(
            model_name="cartaocredito",
            name="dia_vencimento",
            field=models.PositiveSmallIntegerField(
                blank=True,
                null=True,
                validators=[
                    django.core.validators.MinValueValidator(1),
                    django.core.validators.MaxValueValidator(31),
                ],
                verbose_name="dia de vencimento",
            ),
        ),
    ]
