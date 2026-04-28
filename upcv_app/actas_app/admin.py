from django.contrib import admin

from .models import (
    ActaSesion,
    AcuerdoConsistorial,
    AreaInformeCatalogo,
    AgendaPlantilla,
    AsistenciaSesion,
    AsuntoNuevoSesion,
    AsuntoPendiente,
    BitacoraSesion,
    CorrespondenciaSesion,
    InformeSesion,
    MiembroConsistorio,
    PuntoAgendaPlantilla,
    PuntoAgendaSesion,
    SeguimientoAsuntoPendiente,
    SesionConsistorial,
    TextoBaseActa,
    TipoSesion,
)


class PuntoAgendaPlantillaInline(admin.TabularInline):
    model = PuntoAgendaPlantilla
    extra = 0


class PuntoAgendaSesionInline(admin.TabularInline):
    model = PuntoAgendaSesion
    extra = 0


@admin.register(TipoSesion)
class TipoSesionAdmin(admin.ModelAdmin):
    list_display = ("nombre", "activa", "creado_en")
    list_filter = ("activa",)
    search_fields = ("nombre", "descripcion")
    ordering = ("nombre",)


@admin.register(MiembroConsistorio)
class MiembroConsistorioAdmin(admin.ModelAdmin):
    list_display = ("nombre_completo", "cargo", "tipo_miembro", "activo")
    list_filter = ("tipo_miembro", "activo")
    search_fields = ("nombres", "apellidos", "cargo")
    ordering = ("apellidos",)


@admin.register(AgendaPlantilla)
class AgendaPlantillaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "activa", "actualizado_en")
    list_filter = ("activa",)
    search_fields = ("nombre", "descripcion")
    inlines = [PuntoAgendaPlantillaInline]


@admin.register(SesionConsistorial)
class SesionConsistorialAdmin(admin.ModelAdmin):
    list_display = ("numero", "anio", "fecha", "tipo_sesion", "estado", "quorum_alcanzado", "quorum_requerido")
    list_filter = ("estado", "tipo_sesion", "anio")
    search_fields = ("numero", "lugar")
    ordering = ("-anio", "-numero")
    inlines = [PuntoAgendaSesionInline]


@admin.register(AsistenciaSesion)
class AsistenciaSesionAdmin(admin.ModelAdmin):
    list_display = ("sesion", "miembro", "asistencia")
    list_filter = ("asistencia",)
    search_fields = ("sesion__numero", "miembro__nombres", "miembro__apellidos")


@admin.register(InformeSesion)
class InformeSesionAdmin(admin.ModelAdmin):
    list_display = ("sesion", "area", "tipo_informe", "expositor")
    list_filter = ("tipo_informe",)
    search_fields = ("area", "expositor", "sesion__numero")


@admin.register(CorrespondenciaSesion)
class CorrespondenciaSesionAdmin(admin.ModelAdmin):
    list_display = ("sesion", "remitente", "asunto", "genera_acuerdo", "genera_pendiente")
    list_filter = ("genera_acuerdo", "genera_pendiente")
    search_fields = ("asunto", "remitente")


@admin.register(AsuntoPendiente)
class AsuntoPendienteAdmin(admin.ModelAdmin):
    list_display = ("titulo", "responsable", "estado", "prioridad", "activo")
    list_filter = ("estado", "prioridad", "activo")
    search_fields = ("titulo", "descripcion")


@admin.register(SeguimientoAsuntoPendiente)
class SeguimientoAsuntoPendienteAdmin(admin.ModelAdmin):
    list_display = ("asunto_pendiente", "estado_anterior", "estado_nuevo", "usuario", "fecha")
    list_filter = ("estado_anterior", "estado_nuevo")
    search_fields = ("asunto_pendiente__titulo", "detalle")


@admin.register(AsuntoNuevoSesion)
class AsuntoNuevoSesionAdmin(admin.ModelAdmin):
    list_display = ("sesion", "titulo", "presentado_por", "pasa_a_pendiente", "genera_acuerdo")
    list_filter = ("pasa_a_pendiente", "genera_acuerdo")
    search_fields = ("titulo", "presentado_por")


@admin.register(AcuerdoConsistorial)
class AcuerdoConsistorialAdmin(admin.ModelAdmin):
    list_display = ("numero", "anio", "sesion", "estado", "origen_tipo", "fecha")
    list_filter = ("anio", "estado", "origen_tipo")
    search_fields = ("texto", "sesion__numero")
    ordering = ("-anio", "-numero")


@admin.register(ActaSesion)
class ActaSesionAdmin(admin.ModelAdmin):
    list_display = ("numero_acta", "anio", "sesion", "estado", "version")
    list_filter = ("estado", "anio")
    search_fields = ("numero_acta", "sesion__numero")
    ordering = ("-anio", "-numero_acta")


@admin.register(BitacoraSesion)
class BitacoraSesionAdmin(admin.ModelAdmin):
    list_display = ("referencia", "accion", "usuario", "fecha")
    list_filter = ("accion",)
    search_fields = ("referencia", "detalle")
    ordering = ("-fecha",)


@admin.register(AreaInformeCatalogo)
class AreaInformeCatalogoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "activa", "actualizado_en")
    list_filter = ("activa",)
    search_fields = ("nombre", "descripcion")


@admin.register(TextoBaseActa)
class TextoBaseActaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "activo", "actualizado_en")
    list_filter = ("activo",)
    search_fields = ("nombre", "contenido")
