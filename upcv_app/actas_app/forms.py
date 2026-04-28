from django import forms
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
    class Meta:
        model = InformeSesion
        exclude = ["sesion", "creado_en", "actualizado_en"]
        widgets = {
            "area": forms.TextInput(attrs={"class": "form-control"}),
            "tipo_informe": forms.Select(attrs={"class": "form-control"}),
            "expositor": forms.TextInput(attrs={"class": "form-control"}),
            "resumen": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "saldo_inicial": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "ingresos": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "egresos": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "saldo_final": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "fondo_especial": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "observaciones": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }


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
