import re

from django import forms


class FiltroDashboardForm(forms.Form):
    mes = forms.CharField(
        label="Mês",
        widget=forms.TextInput(attrs={"type": "month"}),
    )
    responsavel = forms.ChoiceField(label="Responsável", required=False)

    def __init__(self, *args, sala=None, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        if sala:
            escolhas = [("", "Todos")]
            escolhas.extend(
                (
                    f"usuario:{membro.usuario_id}",
                    membro.usuario.first_name or membro.usuario.username,
                )
                for membro in sala.membros.select_related("usuario").all()
            )
            escolhas.append(("sala", "Da sala"))
        else:
            escolhas = [("", "Meu espaço")]
        self.fields["responsavel"].choices = escolhas

    def clean_mes(self):
        mes = self.cleaned_data["mes"]
        if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", mes):
            raise forms.ValidationError("Informe um mês válido.")
        return mes
