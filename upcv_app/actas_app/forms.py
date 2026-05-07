from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory

from .models import (
    ActaSesion,
    AcuerdoConsistorial,
    AgendaPlantilla,
    AreaInformeCatalogo,
    AsistenciaSesion,
    AsuntoNuevoSesion,
    AsuntoPendiente,
    CorrespondenciaSesion,
    InformeSesion,
    MiembroConsistorio,
    PuntoAgendaSesion,
    PuntoAgendaPlantilla,
    SeguimientoAsuntoPendiente,
    SesionConsistorial,
    TextoBaseActa,
    TipoSesion,
)


class SesionConsistorialForm(forms.ModelForm):
    plantilla_agenda = forms.ModelChoiceField(
        queryset=AgendaPlantilla.objects.filter(activa=True),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    copiar_pendientes_abiertos = forms.BooleanField(required=False)

    class Meta:
        model = SesionConsistorial
        fields = [
            "tipo_sesion", "fecha", "lugar", "hora_inicio", "hora_fin", "moderador", "secretario", "quorum_requerido",
            "observaciones_generales",
        ]
        widgets = {
            "tipo_sesion": forms.Select(attrs={"class": "form-control"}),
            "fecha": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "lugar": forms.TextInput(attrs={"class": "form-control"}),
            "hora_inicio": forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
            "hora_fin": forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
            "moderador": forms.Select(attrs={"class": "form-control"}),
            "secretario": forms.Select(attrs={"class": "form-control"}),
            "quorum_requerido": forms.NumberInput(attrs={"class": "form-control"}),
            "observaciones_generales": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }


class PuntoAgendaSesionForm(forms.ModelForm):
    class Meta:
        model = PuntoAgendaSesion
        fields = ["seccion", "numeral", "titulo", "tipo_punto", "orden", "activo", "contenido_resumen", "observaciones"]
        widgets = {
            "seccion": forms.TextInput(attrs={"class": "form-control"}),
            "numeral": forms.TextInput(attrs={"class": "form-control"}),
            "titulo": forms.TextInput(attrs={"class": "form-control"}),
            "tipo_punto": forms.Select(attrs={"class": "form-control"}),
            "orden": forms.NumberInput(attrs={"class": "form-control"}),
            "contenido_resumen": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "observaciones": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }


AgendaSesionFormset = inlineformset_factory(
    SesionConsistorial,
    PuntoAgendaSesion,
    form=PuntoAgendaSesionForm,
    extra=1,
    can_delete=True,
)


class AsistenciaSesionForm(forms.ModelForm):
    class Meta:
        model = AsistenciaSesion
        fields = ["miembro", "asistencia", "observaciones"]
        widgets = {
            "miembro": forms.Select(attrs={"class": "form-control"}),
            "asistencia": forms.Select(attrs={"class": "form-control"}),
            "observaciones": forms.TextInput(attrs={"class": "form-control"}),
        }


AsistenciaSesionFormset = inlineformset_factory(
    SesionConsistorial,
    AsistenciaSesion,
    form=AsistenciaSesionForm,
    extra=0,
    can_delete=False,
)


class InformeSesionForm(forms.ModelForm):
    AREAS_INFORME_BASE = [
        "Pastor",
        "Tesorería",
        "Purificadora",
        "Anciano de turno",
        "Diáconos",
        "Femenil",
        "Jóvenes",
        "Educación Cristiana",
        "Visita Jícaro",
        "Consejera Femenil",
        "Consejo Diáconos",
        "Secretario",
        "Fondo pastoral",
        "Otros",
    ]
    AREAS_FINANCIERAS = {
        "Tesorería",
        "Purificadora",
        "Diáconos",
        "Femenil",
        "Jóvenes",
        "Educación Cristiana",
        "Fondo pastoral",
    }

    area = forms.ChoiceField(label="Categoría del informe", widget=forms.Select(attrs={"class": "form-control"}))
    area_otro = forms.CharField(
        label="Título personalizado",
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Escribe el nombre del informe"}),
    )

    class Meta:
        model = InformeSesion
        fields = [
            "area",
            "area_otro",
            "tipo_informe",
            "expositor",
            "resumen",
            "saldo_inicial",
            "ingresos",
            "egresos",
            "saldo_final",
            "fondo_especial",
            "observaciones",
        ]
        widgets = {
            "tipo_informe": forms.Select(attrs={"class": "form-control"}),
            "expositor": forms.TextInput(attrs={"class": "form-control", "placeholder": "Responsable o expositor"}),
            "resumen": forms.Textarea(attrs={"class": "form-control", "rows": 4, "placeholder": "Contenido o detalle narrativo del informe"}),
            "saldo_inicial": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
            "ingresos": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
            "egresos": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
            "saldo_final": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "readonly": "readonly"}),
            "fondo_especial": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
            "observaciones": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }

    def __init__(self, *args, sesion=None, **kwargs):
        self.sesion = sesion
        super().__init__(*args, **kwargs)
        catalogo = list(AreaInformeCatalogo.objects.filter(activa=True).values_list("nombre", flat=True))
        areas = list(dict.fromkeys([*self.AREAS_INFORME_BASE, *catalogo]))
        self.fields["area"].choices = [(area, area) for area in areas]
        self.fields["tipo_informe"].required = False
        for field_name in ["saldo_inicial", "ingresos", "egresos", "saldo_final", "fondo_especial"]:
            self.fields[field_name].required = False
        if self.instance and self.instance.pk:
            area_actual = self.instance.area
            if area_actual not in areas:
                self.initial["area"] = "Otros"
                self.initial["area_otro"] = area_actual
            else:
                self.initial.setdefault("area", area_actual)

    def clean(self):
        cleaned_data = super().clean()
        area = cleaned_data.get("area")
        area_otro = (cleaned_data.get("area_otro") or "").strip()
        area_final = area_otro if area == "Otros" else area
        if not area_final:
            raise ValidationError("Selecciona o escribe la categoría del informe.")

        for campo in ["saldo_inicial", "ingresos", "egresos", "fondo_especial"]:
            if cleaned_data.get(campo) is None:
                cleaned_data[campo] = Decimal("0.00")
            if cleaned_data[campo] < 0:
                self.add_error(campo, "Este valor no puede ser negativo.")

        es_financiero = area_final in self.AREAS_FINANCIERAS
        cleaned_data["area"] = area_final
        cleaned_data["tipo_informe"] = InformeSesion.TipoInforme.FINANCIERO if es_financiero else InformeSesion.TipoInforme.NARRATIVO
        if es_financiero:
            cleaned_data["saldo_final"] = cleaned_data["saldo_inicial"] + cleaned_data["ingresos"] - cleaned_data["egresos"]
        else:
            cleaned_data["saldo_inicial"] = Decimal("0.00")
            cleaned_data["ingresos"] = Decimal("0.00")
            cleaned_data["egresos"] = Decimal("0.00")
            cleaned_data["saldo_final"] = Decimal("0.00")
            cleaned_data["fondo_especial"] = Decimal("0.00")

        if self.sesion and area != "Otros":
            duplicado = InformeSesion.objects.filter(sesion=self.sesion, area__iexact=area_final)
            if self.instance and self.instance.pk:
                duplicado = duplicado.exclude(pk=self.instance.pk)
            if duplicado.exists():
                self.add_error(
                    "area",
                    f"Ya existe un informe de {area_final} registrado para esta sesión. Puede editar el informe existente.",
                )
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.area = self.cleaned_data["area"]
        instance.tipo_informe = self.cleaned_data["tipo_informe"]
        instance.saldo_inicial = self.cleaned_data["saldo_inicial"]
        instance.ingresos = self.cleaned_data["ingresos"]
        instance.egresos = self.cleaned_data["egresos"]
        instance.saldo_final = self.cleaned_data["saldo_final"]
        instance.fondo_especial = self.cleaned_data["fondo_especial"]
        if commit:
            instance.save()
        return instance


class CorrespondenciaSesionForm(forms.ModelForm):
    class Meta:
        model = CorrespondenciaSesion
        exclude = ["sesion", "creado_en", "actualizado_en"]
        widgets = {
            "remitente": forms.TextInput(attrs={"class": "form-control"}),
            "asunto": forms.TextInput(attrs={"class": "form-control"}),
            "descripcion": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "decision": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }


class AsuntoPendienteForm(forms.ModelForm):
    class Meta:
        model = AsuntoPendiente
        fields = ["titulo", "descripcion", "responsable", "estado", "prioridad", "activo"]
        widgets = {
            "titulo": forms.TextInput(attrs={"class": "form-control"}),
            "descripcion": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "responsable": forms.Select(attrs={"class": "form-control"}),
            "estado": forms.Select(attrs={"class": "form-control"}),
            "prioridad": forms.Select(attrs={"class": "form-control"}),
        }


class SeguimientoAsuntoPendienteForm(forms.ModelForm):
    class Meta:
        model = SeguimientoAsuntoPendiente
        fields = ["sesion", "detalle", "estado_nuevo"]
        widgets = {
            "sesion": forms.Select(attrs={"class": "form-control"}),
            "detalle": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "estado_nuevo": forms.Select(attrs={"class": "form-control"}),
        }


class AsuntoNuevoSesionForm(forms.ModelForm):
    class Meta:
        model = AsuntoNuevoSesion
        exclude = ["sesion", "creado_en", "actualizado_en"]
        widgets = {
            "titulo": forms.TextInput(attrs={"class": "form-control"}),
            "descripcion": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "presentado_por": forms.TextInput(attrs={"class": "form-control"}),
            "decision": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }


class AcuerdoConsistorialForm(forms.ModelForm):
    class Meta:
        model = AcuerdoConsistorial
        fields = ["sesion", "origen_tipo", "texto", "responsable", "estado", "fecha", "observaciones"]
        widgets = {
            "sesion": forms.Select(attrs={"class": "form-control"}),
            "origen_tipo": forms.Select(attrs={"class": "form-control"}),
            "texto": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "responsable": forms.Select(attrs={"class": "form-control"}),
            "estado": forms.Select(attrs={"class": "form-control"}),
            "fecha": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "observaciones": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }


class ActaSesionForm(forms.ModelForm):
    class Meta:
        model = ActaSesion
        fields = ["contenido_borrador", "contenido_final", "estado"]
        widgets = {
            "contenido_borrador": forms.Textarea(attrs={"class": "form-control", "rows": 8}),
            "contenido_final": forms.Textarea(attrs={"class": "form-control", "rows": 8}),
            "estado": forms.Select(attrs={"class": "form-control"}),
        }


class TipoSesionForm(forms.ModelForm):
    class Meta:
        model = TipoSesion
        fields = ["nombre", "descripcion", "activa"]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "descripcion": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }


class MiembroConsistorioForm(forms.ModelForm):
    class Meta:
        model = MiembroConsistorio
        fields = ["nombres", "apellidos", "cargo", "tipo_miembro", "activo", "observaciones"]
        widgets = {
            "nombres": forms.TextInput(attrs={"class": "form-control"}),
            "apellidos": forms.TextInput(attrs={"class": "form-control"}),
            "cargo": forms.TextInput(attrs={"class": "form-control"}),
            "tipo_miembro": forms.Select(attrs={"class": "form-control"}),
            "observaciones": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }


class AgendaPlantillaForm(forms.ModelForm):
    class Meta:
        model = AgendaPlantilla
        fields = ["nombre", "descripcion", "activa"]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "descripcion": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }


class PuntoAgendaPlantillaForm(forms.ModelForm):
    class Meta:
        model = PuntoAgendaPlantilla
        fields = ["plantilla", "seccion", "numeral", "titulo", "tipo_punto", "orden", "activo"]
        widgets = {
            "plantilla": forms.Select(attrs={"class": "form-control"}),
            "seccion": forms.TextInput(attrs={"class": "form-control"}),
            "numeral": forms.TextInput(attrs={"class": "form-control"}),
            "titulo": forms.TextInput(attrs={"class": "form-control"}),
            "tipo_punto": forms.Select(attrs={"class": "form-control"}),
            "orden": forms.NumberInput(attrs={"class": "form-control"}),
        }


class AreaInformeCatalogoForm(forms.ModelForm):
    class Meta:
        model = AreaInformeCatalogo
        fields = ["nombre", "descripcion", "activa"]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "descripcion": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }


class TextoBaseActaForm(forms.ModelForm):
    class Meta:
        model = TextoBaseActa
        fields = ["nombre", "contenido", "activo"]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "contenido": forms.Textarea(attrs={"class": "form-control", "rows": 5}),
        }
