from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from almacen_app.utils import grupo_requerido

from .forms import (
    ActaSesionForm,
    AcuerdoConsistorialForm,
    AgendaPlantillaForm,
    AgendaSesionFormset,
    AreaInformeCatalogoForm,
    AsuntoNuevoSesionForm,
    AsuntoPendienteForm,
    CorrespondenciaSesionForm,
    InformeSesionForm,
    MiembroConsistorioForm,
    PuntoAgendaPlantillaForm,
    SeguimientoAsuntoPendienteForm,
    SesionConsistorialForm,
    TextoBaseActaForm,
    TipoSesionForm,
)
from .models import (
    ActaSesion,
    AcuerdoConsistorial,
    AgendaPlantilla,
    AsistenciaSesion,
    AsuntoNuevoSesion,
    AsuntoPendiente,
    BitacoraSesion,
    CorrespondenciaSesion,
    InformeSesion,
    MiembroConsistorio,
    PuntoAgendaSesion,
    PuntoAgendaPlantilla,
    SeguimientoAsuntoPendiente,
    SesionConsistorial,
    TextoBaseActa,
    TipoSesion,
    AreaInformeCatalogo,
)
from .services.acta_generator import generar_borrador_acta
from .services.docx_export import build_acta_docx



def usuario_puede_aprobar_actas(usuario):
    return usuario.is_superuser or usuario.groups.filter(name="Administrador").exists()


def pendientes_para_aprobar_acta(sesion, acta=None):
    pendientes = []
    if not acta or not acta.numero_acta:
        pendientes.append("número de acta")
    if not sesion.fecha:
        pendientes.append("fecha de sesión")
    if not sesion.tipo_sesion_id:
        pendientes.append("tipo de sesión")
    if not sesion.asistencias.filter(asistencia=AsistenciaSesion.Asistencia.PRESENTE).exists():
        pendientes.append("asistentes o miembros presentes")
    if not sesion.puntos_agenda.filter(activo=True).exists():
        pendientes.append("agenda o puntos tratados")
    if not acta or not (acta.contenido_final or "").strip():
        pendientes.append("contenido del acta final")
    return pendientes


def badge_estado_acta(estado):
    return {
        ActaSesion.Estado.BORRADOR: "badge-light-secondary",
        ActaSesion.Estado.EN_REVISION: "badge-light-warning",
        ActaSesion.Estado.APROBADA: "badge-light-success",
    }.get(estado, "badge-light-dark")


def progreso_estado_acta(acta):
    flujo = [
        (ActaSesion.Estado.BORRADOR, "Borrador"),
        (ActaSesion.Estado.EN_REVISION, "En revisión"),
        (ActaSesion.Estado.APROBADA, "Aprobada"),
        ("cerrada", "Cerrada"),
    ]
    estado_actual = acta.estado if acta else ActaSesion.Estado.BORRADOR
    indice_actual = next((i for i, (valor, _) in enumerate(flujo) if valor == estado_actual), 0)
    return [
        {"valor": valor, "etiqueta": etiqueta, "activo": valor == estado_actual, "completado": i <= indice_actual}
        for i, (valor, etiqueta) in enumerate(flujo)
    ]


def contexto_flujo_acta(sesion, acta=None, usuario=None):
    estado = acta.estado if acta else ActaSesion.Estado.BORRADOR
    pendientes = pendientes_para_aprobar_acta(sesion, acta)
    acciones = {
        ActaSesion.Estado.BORRADOR: "Enviar a revisión",
        ActaSesion.Estado.EN_REVISION: "Aprobar acta",
        ActaSesion.Estado.APROBADA: "Descargar el acta y cerrar si aplica",
    }
    return {
        "pendientes_aprobacion": pendientes,
        "estado_badge_class": badge_estado_acta(estado),
        "flujo_estados": progreso_estado_acta(acta),
        "accion_sugerida": acciones.get(estado, "Revisar estado del acta"),
        "puede_aprobar_acta": usuario_puede_aprobar_actas(usuario) if usuario else False,
    }



AREAS_INFORME_ESPERADAS = [
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
]


def formato_quetzales(valor):
    return f"Q {valor or 0:,.2f}"


def acta_esta_aprobada(sesion):
    acta = getattr(sesion, "acta", None)
    return bool(acta and acta.estado == ActaSesion.Estado.APROBADA)


def obtener_resumen_informes(sesion):
    informes = list(sesion.informes.all().order_by("area"))
    informes_por_area = {informe.area: informe for informe in informes}
    esperados = []
    for area in AREAS_INFORME_ESPERADAS:
        informe = informes_por_area.get(area)
        esperados.append({
            "area": area,
            "informe": informe,
            "registrado": informe is not None,
            "saldo_final": formato_quetzales(informe.saldo_final) if informe and informe.tipo_informe == InformeSesion.TipoInforme.FINANCIERO else "",
        })
    return {
        "esperados": esperados,
        "registrados": len(informes),
        "pendientes": sum(1 for item in esperados if not item["registrado"]),
        "financieros": [informe for informe in informes if informe.tipo_informe == InformeSesion.TipoInforme.FINANCIERO],
    }

def obtener_resumen_asistencia(sesion, total_miembros=None):
    asistencias = sesion.asistencias.select_related("miembro")
    total = total_miembros if total_miembros is not None else MiembroConsistorio.objects.filter(activo=True).count()
    presentes = asistencias.filter(asistencia=AsistenciaSesion.Asistencia.PRESENTE).count()
    ausentes = asistencias.filter(asistencia=AsistenciaSesion.Asistencia.AUSENTE).count()
    excusados = asistencias.filter(asistencia=AsistenciaSesion.Asistencia.EXCUSADO).count()
    return {
        "total_miembros": total,
        "presentes": presentes,
        "ausentes": ausentes,
        "excusados": excusados,
        "quorum_requerido": sesion.quorum_requerido,
        "quorum_alcanzado": presentes,
        "cumple_quorum": presentes >= sesion.quorum_requerido,
    }


def obtener_asistencia_agrupada(sesion):
    asistencias = sesion.asistencias.select_related("miembro").order_by("miembro__apellidos", "miembro__nombres")
    return {
        "presentes": asistencias.filter(asistencia=AsistenciaSesion.Asistencia.PRESENTE),
        "ausentes": asistencias.filter(asistencia=AsistenciaSesion.Asistencia.AUSENTE),
        "excusados": asistencias.filter(asistencia=AsistenciaSesion.Asistencia.EXCUSADO),
    }


def construir_filas_asistencia(sesion, miembros_activos):
    asistencias = {asistencia.miembro_id: asistencia for asistencia in sesion.asistencias.select_related("miembro")}
    return [
        {
            "miembro": miembro,
            "asistencia": asistencias.get(miembro.pk).asistencia if miembro.pk in asistencias else "",
            "observaciones": asistencias.get(miembro.pk).observaciones if miembro.pk in asistencias else "",
        }
        for miembro in miembros_activos
    ]

def registrar_bitacora(usuario, referencia, accion, detalle=""):
    BitacoraSesion.objects.create(usuario=usuario, referencia=referencia, accion=accion, detalle=detalle)


@login_required
@grupo_requerido("Administrador", "Almacen")
def dashboard(request):
    anio = timezone.now().year
    sesiones = SesionConsistorial.objects.filter(anio=anio)
    context = {
        "total_sesiones": sesiones.count(),
        "sesiones_borrador": sesiones.filter(estado=SesionConsistorial.Estado.BORRADOR).count(),
        "sesiones_aprobadas": sesiones.filter(estado=SesionConsistorial.Estado.APROBADA).count(),
        "actas_revision": ActaSesion.objects.filter(anio=anio, estado=ActaSesion.Estado.EN_REVISION).count(),
        "acuerdos_abiertos": AcuerdoConsistorial.objects.filter(anio=anio, estado=AcuerdoConsistorial.Estado.ABIERTO).count(),
        "pendientes_abiertos": AsuntoPendiente.objects.filter(estado=AsuntoPendiente.Estado.ABIERTO, activo=True).count(),
        "ultimas_sesiones": SesionConsistorial.objects.order_by("-fecha")[:5],
        "ultimos_acuerdos": AcuerdoConsistorial.objects.order_by("-fecha")[:5],
    }
    return render(request, "actas_app/dashboard.html", context)


@login_required
@grupo_requerido("Administrador", "Almacen")
def sesion_list(request):
    sesiones = SesionConsistorial.objects.select_related("tipo_sesion", "acta").order_by("-anio", "-numero")
    return render(request, "actas_app/sesion_list.html", {"sesiones": sesiones})


@login_required
@grupo_requerido("Administrador", "Almacen")
def sesion_create(request):
    if request.method == "POST":
        form = SesionConsistorialForm(request.POST)
        if form.is_valid():
            sesion = form.save(commit=False)
            sesion.anio = sesion.fecha.year
            sesion.numero = SesionConsistorial.siguiente_numero(sesion.anio)
            sesion.creada_por = request.user
            sesion.save()

            plantilla = form.cleaned_data.get("plantilla_agenda")
            if plantilla:
                puntos = PuntoAgendaPlantilla.objects.filter(plantilla=plantilla, activo=True).order_by("orden")
                PuntoAgendaSesion.objects.bulk_create([
                    PuntoAgendaSesion(
                        sesion=sesion,
                        seccion=p.seccion,
                        numeral=p.numeral,
                        titulo=p.titulo,
                        tipo_punto=p.tipo_punto,
                        orden=p.orden,
                        activo=p.activo,
                    )
                    for p in puntos
                ])

            if form.cleaned_data.get("copiar_pendientes_abiertos"):
                pendientes = AsuntoPendiente.objects.filter(activo=True).exclude(estado=AsuntoPendiente.Estado.RESUELTO)
                for pendiente in pendientes:
                    pendiente.sesiones.add(sesion)

            registrar_bitacora(request.user, str(sesion), "creación de sesión", "Se creó sesión consistorial.")
            messages.success(request, "Sesión creada correctamente.")
            return redirect("actas_app:sesion_detail", pk=sesion.pk)
    else:
        form = SesionConsistorialForm()

    return render(request, "actas_app/sesion_form.html", {"form": form})


@login_required
@grupo_requerido("Administrador", "Almacen")
def sesion_edit(request, pk):
    sesion = get_object_or_404(SesionConsistorial, pk=pk)
    form = SesionConsistorialForm(request.POST or None, instance=sesion)
    if request.method == "POST":
        if form.is_valid():
            sesion = form.save()
            registrar_bitacora(request.user, str(sesion), "edición de sesión", "Datos generales actualizados.")
            messages.success(request, "Sesión actualizada correctamente.")
            return redirect("actas_app:sesion_detail", pk=sesion.pk)
        messages.error(request, "Corrige los errores del formulario para guardar la sesión.")
    return render(request, "actas_app/sesion_form.html", {"form": form, "sesion": sesion, "is_edit": True})


@login_required
@grupo_requerido("Administrador", "Almacen")
def sesion_detail(request, pk):
    sesion = get_object_or_404(SesionConsistorial.objects.select_related("tipo_sesion", "moderador", "secretario"), pk=pk)
    acta = getattr(sesion, "acta", None)
    context = {
        "sesion": sesion,
        "informes": sesion.informes.all(),
        "correspondencias": sesion.correspondencias.all(),
        "asuntos_nuevos": sesion.asuntos_nuevos.all(),
        "acuerdos": sesion.acuerdos.all(),
        "pendientes": sesion.pendientes_vinculados.all(),
        "acta": acta,
        "resumen_asistencia": obtener_resumen_asistencia(sesion),
        "asistencia_agrupada": obtener_asistencia_agrupada(sesion),
        "resumen_informes": obtener_resumen_informes(sesion),
    }
    context.update(contexto_flujo_acta(sesion, acta, request.user))
    return render(request, "actas_app/sesion_detail.html", context)


@login_required
@grupo_requerido("Administrador", "Almacen")
def sesion_agenda(request, pk):
    sesion = get_object_or_404(SesionConsistorial, pk=pk)
    if request.method == "POST":
        formset = AgendaSesionFormset(request.POST, instance=sesion)
        if formset.is_valid():
            formset.save()
            registrar_bitacora(request.user, str(sesion), "edición de agenda", "Agenda actualizada")
            messages.success(request, "Agenda actualizada correctamente.")
            return redirect("actas_app:sesion_detail", pk=sesion.pk)
    else:
        formset = AgendaSesionFormset(instance=sesion)
    return render(request, "actas_app/sesion_agenda.html", {"sesion": sesion, "formset": formset})


@login_required
@grupo_requerido("Administrador", "Almacen")
def sesion_asistencia(request, pk):
    sesion = get_object_or_404(
        SesionConsistorial.objects.select_related("tipo_sesion"),
        pk=pk,
    )
    acta = getattr(sesion, "acta", None)
    miembros_activos = list(MiembroConsistorio.objects.filter(activo=True).order_by("apellidos", "nombres"))
    estados_validos = {choice[0] for choice in AsistenciaSesion.Asistencia.choices}

    if acta and acta.estado == ActaSesion.Estado.APROBADA and request.method == "POST":
        messages.error(request, "El acta ya está aprobada. La asistencia no puede modificarse.")
        return redirect("actas_app:sesion_detail", pk=sesion.pk)

    if request.method == "POST":
        if not miembros_activos:
            messages.error(
                request,
                "No hay miembros activos configurados para tomar asistencia. Configure primero los miembros del consistorio.",
            )
            return redirect("actas_app:sesion_asistencia", pk=sesion.pk)

        if request.POST.get("accion") == "limpiar":
            AsistenciaSesion.objects.filter(sesion=sesion, miembro__in=miembros_activos).delete()
            sesion.recalcular_quorum()
            registrar_bitacora(request.user, str(sesion), "limpieza de asistencia", "Se limpió la asistencia registrada")
            messages.warning(request, "Asistencia limpiada. Marca cada miembro antes de continuar.")
            return redirect("actas_app:sesion_asistencia", pk=sesion.pk)

        ids_validos = {miembro.pk for miembro in miembros_activos}
        ids_enviados = set()
        for key in request.POST:
            if key.startswith("asistencia_"):
                try:
                    ids_enviados.add(int(key.removeprefix("asistencia_")))
                except ValueError:
                    messages.error(request, "La asistencia contiene un identificador de miembro inválido.")
                    return redirect("actas_app:sesion_asistencia", pk=sesion.pk)
        if not ids_enviados.issubset(ids_validos):
            messages.error(request, "La asistencia contiene IDs de miembros inválidos o inactivos.")
            return redirect("actas_app:sesion_asistencia", pk=sesion.pk)

        faltantes = []
        asistencias_recibidas = {}
        for miembro in miembros_activos:
            valor = request.POST.get(f"asistencia_{miembro.pk}")
            if not valor:
                faltantes.append(miembro.nombre_completo)
                continue
            if valor not in estados_validos:
                messages.error(request, f"Valor de asistencia inválido para {miembro.nombre_completo}.")
                return redirect("actas_app:sesion_asistencia", pk=sesion.pk)
            asistencias_recibidas[miembro.pk] = valor

        if faltantes:
            messages.warning(request, "Hay miembros sin marcar. Complete la asistencia antes de continuar.")
            return redirect("actas_app:sesion_asistencia", pk=sesion.pk)

        for miembro in miembros_activos:
            AsistenciaSesion.objects.update_or_create(
                sesion=sesion,
                miembro=miembro,
                defaults={
                    "asistencia": asistencias_recibidas[miembro.pk],
                    "observaciones": request.POST.get(f"observaciones_{miembro.pk}", "").strip()[:255],
                },
            )

        sesion.recalcular_quorum()
        registrar_bitacora(request.user, str(sesion), "registro de asistencia", "Se actualizó asistencia y quórum")
        messages.success(request, "Asistencia guardada correctamente.")
        return redirect("actas_app:sesion_detail", pk=sesion.pk)

    if not miembros_activos:
        messages.warning(
            request,
            "No hay miembros activos configurados para tomar asistencia. Configure primero los miembros del consistorio.",
        )

    context = {
        "sesion": sesion,
        "acta": acta,
        "filas_asistencia": construir_filas_asistencia(sesion, miembros_activos),
        "resumen_asistencia": obtener_resumen_asistencia(sesion, len(miembros_activos)),
        "opciones_asistencia": AsistenciaSesion.Asistencia,
        "asistencia_bloqueada": bool(acta and acta.estado == ActaSesion.Estado.APROBADA),
    }
    context.update(contexto_flujo_acta(sesion, acta, request.user))
    return render(request, "actas_app/sesion_asistencia.html", context)


@login_required
@grupo_requerido("Administrador", "Almacen")
def sesion_informes(request, sesion_id):
    sesion = get_object_or_404(SesionConsistorial.objects.select_related("tipo_sesion"), pk=sesion_id)
    acta = getattr(sesion, "acta", None)
    informes = sesion.informes.all().order_by("area")
    context = {
        "sesion": sesion,
        "acta": acta,
        "informes": informes,
        "resumen_informes": obtener_resumen_informes(sesion),
        "bloqueado": acta_esta_aprobada(sesion),
    }
    context.update(contexto_flujo_acta(sesion, acta, request.user))
    return render(request, "actas_app/sesion_informes.html", context)


@login_required
@grupo_requerido("Administrador", "Almacen")
def informe_create(request, sesion_id):
    sesion = get_object_or_404(SesionConsistorial, pk=sesion_id)
    if acta_esta_aprobada(sesion):
        messages.error(request, "El acta ya está aprobada. No se pueden registrar informes.")
        return redirect("actas_app:sesion_informes", sesion_id=sesion.pk)

    if request.method == "POST":
        form = InformeSesionForm(request.POST, sesion=sesion)
        if form.is_valid():
            informe = form.save(commit=False)
            informe.sesion = sesion
            informe.save()
            registrar_bitacora(request.user, str(sesion), "registro de informe", informe.area)
            messages.success(request, "Informe guardado correctamente.")
            return redirect("actas_app:sesion_informes", sesion_id=sesion.pk)
        messages.error(request, "No se pudo guardar el informe. Revisa los campos marcados.")
    else:
        form = InformeSesionForm(sesion=sesion)
    return render(request, "actas_app/informe_form.html", {"title": "Registrar informe", "form": form, "sesion": sesion})


@login_required
@grupo_requerido("Administrador", "Almacen")
def informe_edit(request, pk):
    informe = get_object_or_404(InformeSesion.objects.select_related("sesion"), pk=pk)
    sesion = informe.sesion
    if acta_esta_aprobada(sesion):
        messages.error(request, "El acta ya está aprobada. No se pueden editar informes.")
        return redirect("actas_app:sesion_informes", sesion_id=sesion.pk)

    form = InformeSesionForm(request.POST or None, instance=informe, sesion=sesion)
    if request.method == "POST":
        if form.is_valid():
            form.save()
            registrar_bitacora(request.user, str(sesion), "edición de informe", informe.area)
            messages.success(request, "Informe actualizado correctamente.")
            return redirect("actas_app:sesion_informes", sesion_id=sesion.pk)
        messages.error(request, "No se pudo actualizar el informe. Revisa los campos marcados.")
    return render(request, "actas_app/informe_form.html", {"title": "Editar informe", "form": form, "sesion": sesion, "informe": informe})


@login_required
@grupo_requerido("Administrador", "Almacen")
def informe_delete(request, pk):
    informe = get_object_or_404(InformeSesion.objects.select_related("sesion"), pk=pk)
    sesion = informe.sesion
    if request.method != "POST":
        messages.error(request, "La eliminación de informes debe realizarse desde la vista de informes de la sesión.")
        return redirect("actas_app:sesion_informes", sesion_id=sesion.pk)
    if acta_esta_aprobada(sesion):
        messages.error(request, "El acta ya está aprobada. No se pueden eliminar informes.")
        return redirect("actas_app:sesion_informes", sesion_id=sesion.pk)
    area = informe.area
    informe.delete()
    registrar_bitacora(request.user, str(sesion), "eliminación de informe", area)
    messages.success(request, "Informe eliminado correctamente.")
    return redirect("actas_app:sesion_informes", sesion_id=sesion.pk)


@login_required
@grupo_requerido("Administrador", "Almacen")
def correspondencia_create(request, sesion_id):
    sesion = get_object_or_404(SesionConsistorial, pk=sesion_id)
    if request.method == "POST":
        form = CorrespondenciaSesionForm(request.POST, request.FILES)
        if form.is_valid():
            item = form.save(commit=False)
            item.sesion = sesion
            item.save()

            if item.genera_pendiente:
                pendiente = AsuntoPendiente.objects.create(
                    titulo=f"Correspondencia: {item.asunto}",
                    descripcion=item.descripcion,
                    responsable=sesion.secretario,
                )
                pendiente.sesiones.add(sesion)

            if item.genera_acuerdo:
                AcuerdoConsistorial.objects.create(
                    numero=AcuerdoConsistorial.siguiente_numero(sesion.anio),
                    anio=sesion.anio,
                    sesion=sesion,
                    origen_tipo=AcuerdoConsistorial.Origen.CORRESPONDENCIA,
                    texto=item.decision or f"Dar seguimiento a {item.asunto}",
                    responsable=sesion.secretario,
                )

            registrar_bitacora(request.user, str(sesion), "registro de correspondencia", item.asunto)
            messages.success(request, "Correspondencia registrada.")
            return redirect("actas_app:sesion_detail", pk=sesion.pk)
    else:
        form = CorrespondenciaSesionForm()
    return render(request, "actas_app/simple_form.html", {"title": "Registrar correspondencia", "form": form, "sesion": sesion})


@login_required
@grupo_requerido("Administrador", "Almacen")
def pendiente_list(request):
    estado = request.GET.get("estado")
    pendientes = AsuntoPendiente.objects.all()
    if estado:
        pendientes = pendientes.filter(estado=estado)
    return render(request, "actas_app/pendiente_list.html", {"pendientes": pendientes, "estado": estado})


@login_required
@grupo_requerido("Administrador", "Almacen")
def pendiente_create(request):
    if request.method == "POST":
        form = AsuntoPendienteForm(request.POST)
        if form.is_valid():
            pendiente = form.save()
            registrar_bitacora(request.user, pendiente.titulo, "creación de pendiente", pendiente.descripcion[:120])
            messages.success(request, "Pendiente creado correctamente.")
            return redirect("actas_app:pendiente_detail", pk=pendiente.pk)
    else:
        form = AsuntoPendienteForm()
    return render(request, "actas_app/simple_form.html", {"title": "Crear asunto pendiente", "form": form})


@login_required
@grupo_requerido("Administrador", "Almacen")
def pendiente_detail(request, pk):
    pendiente = get_object_or_404(AsuntoPendiente, pk=pk)
    if request.method == "POST":
        form = SeguimientoAsuntoPendienteForm(request.POST)
        if form.is_valid():
            seguimiento = form.save(commit=False)
            seguimiento.asunto_pendiente = pendiente
            seguimiento.estado_anterior = pendiente.estado
            seguimiento.usuario = request.user
            seguimiento.save()
            pendiente.estado = seguimiento.estado_nuevo
            pendiente.save(update_fields=["estado", "actualizado_en"])
            registrar_bitacora(request.user, pendiente.titulo, "actualización de pendiente", seguimiento.detalle)
            messages.success(request, "Seguimiento registrado.")
            return redirect("actas_app:pendiente_detail", pk=pk)
    else:
        form = SeguimientoAsuntoPendienteForm(initial={"estado_nuevo": pendiente.estado})

    return render(
        request,
        "actas_app/pendiente_detail.html",
        {"pendiente": pendiente, "form": form, "seguimientos": pendiente.seguimientos.all()},
    )


@login_required
@grupo_requerido("Administrador", "Almacen")
def pendiente_edit(request, pk):
    pendiente = get_object_or_404(AsuntoPendiente, pk=pk)
    form = AsuntoPendienteForm(request.POST or None, instance=pendiente)
    if request.method == "POST":
        if form.is_valid():
            form.save()
            registrar_bitacora(request.user, pendiente.titulo, "edición de pendiente", "Registro general actualizado.")
            messages.success(request, "Pendiente actualizado correctamente.")
            return redirect("actas_app:pendiente_detail", pk=pk)
        messages.error(request, "No se pudo actualizar el pendiente. Revisa los errores.")
    return render(request, "actas_app/simple_form.html", {"title": "Editar asunto pendiente", "form": form})


@login_required
@grupo_requerido("Administrador", "Almacen")
def asunto_nuevo_create(request, sesion_id):
    sesion = get_object_or_404(SesionConsistorial, pk=sesion_id)
    if request.method == "POST":
        form = AsuntoNuevoSesionForm(request.POST)
        if form.is_valid():
            asunto = form.save(commit=False)
            asunto.sesion = sesion
            asunto.save()

            if asunto.pasa_a_pendiente:
                pendiente = AsuntoPendiente.objects.create(
                    titulo=asunto.titulo,
                    descripcion=asunto.descripcion,
                    responsable=sesion.secretario,
                )
                pendiente.sesiones.add(sesion)

            if asunto.genera_acuerdo:
                AcuerdoConsistorial.objects.create(
                    numero=AcuerdoConsistorial.siguiente_numero(sesion.anio),
                    anio=sesion.anio,
                    sesion=sesion,
                    origen_tipo=AcuerdoConsistorial.Origen.ASUNTO_NUEVO,
                    texto=asunto.decision or asunto.descripcion,
                    responsable=sesion.secretario,
                )
            messages.success(request, "Asunto nuevo registrado.")
            return redirect("actas_app:sesion_detail", pk=sesion.pk)
    else:
        form = AsuntoNuevoSesionForm()
    return render(request, "actas_app/simple_form.html", {"title": "Registrar asunto nuevo", "form": form, "sesion": sesion})


@login_required
@grupo_requerido("Administrador", "Almacen")
def acuerdo_list(request):
    acuerdos = AcuerdoConsistorial.objects.select_related("sesion", "responsable").order_by("-anio", "-numero")
    return render(request, "actas_app/acuerdo_list.html", {"acuerdos": acuerdos})


@login_required
@grupo_requerido("Administrador", "Almacen")
def acuerdo_create(request):
    if request.method == "POST":
        form = AcuerdoConsistorialForm(request.POST)
        if form.is_valid():
            acuerdo = form.save(commit=False)
            acuerdo.anio = acuerdo.fecha.year
            acuerdo.numero = AcuerdoConsistorial.siguiente_numero(acuerdo.anio)
            acuerdo.save()
            registrar_bitacora(request.user, str(acuerdo), "creación de acuerdo", acuerdo.texto[:120])
            messages.success(request, "Acuerdo creado.")
            return redirect("actas_app:acuerdo_list")
    else:
        form = AcuerdoConsistorialForm()
    return render(request, "actas_app/simple_form.html", {"title": "Crear acuerdo", "form": form})


@login_required
@grupo_requerido("Administrador", "Almacen")
def acuerdo_edit(request, pk):
    acuerdo = get_object_or_404(AcuerdoConsistorial, pk=pk)
    form = AcuerdoConsistorialForm(request.POST or None, instance=acuerdo)
    if request.method == "POST":
        if form.is_valid():
            form.save()
            registrar_bitacora(request.user, str(acuerdo), "edición de acuerdo", "Acuerdo actualizado.")
            messages.success(request, "Acuerdo actualizado correctamente.")
            return redirect("actas_app:acuerdo_list")
        messages.error(request, "No se pudo actualizar el acuerdo. Revisa los errores.")
    return render(request, "actas_app/simple_form.html", {"title": "Editar acuerdo", "form": form})


@login_required
@grupo_requerido("Administrador", "Almacen")
def acta_list(request):
    actas = ActaSesion.objects.select_related("sesion").order_by("-anio", "-numero_acta")
    return render(request, "actas_app/acta_list.html", {"actas": actas})


@login_required
@grupo_requerido("Administrador", "Almacen")
def acta_edit(request, sesion_id):
    sesion = get_object_or_404(SesionConsistorial, pk=sesion_id)
    acta, created = ActaSesion.objects.get_or_create(
        sesion=sesion,
        defaults={
            "numero_acta": ActaSesion.siguiente_numero(sesion.anio),
            "anio": sesion.anio,
            "redactado_por": request.user,
            "contenido_borrador": "",
        },
    )
    if created:
        registrar_bitacora(request.user, str(sesion), "creación de acta", "Acta inicial creada")

    if request.method == "POST":
        if acta.estado == ActaSesion.Estado.APROBADA:
            messages.error(request, "El acta ya está aprobada y la edición directa está bloqueada para proteger su contenido.")
            return redirect("actas_app:sesion_detail", pk=sesion.pk)

        form = ActaSesionForm(request.POST, instance=acta)
        if form.is_valid():
            acta = form.save(commit=False)
            estado_solicitado = acta.estado
            estado_origen = ActaSesion.objects.filter(pk=acta.pk).values_list("estado", flat=True).first()
            if estado_solicitado == ActaSesion.Estado.APROBADA:
                acta.estado = estado_origen
                acta.version += 1
                acta.save()
                acta.estado = ActaSesion.Estado.APROBADA
                return aprobar_acta(request, sesion, acta, estado_origen=estado_origen)
            if acta.estado == ActaSesion.Estado.EN_REVISION:
                acta.revisado_por = request.user
                sesion.estado = SesionConsistorial.Estado.EN_REVISION
                sesion.revisada_por = request.user
                sesion.save(update_fields=["estado", "revisada_por", "actualizado_en"])
            acta.version += 1
            acta.save()
            registrar_bitacora(request.user, str(acta), "edición de acta", f"Estado guardado: {acta.estado}")
            messages.success(request, f"Acta guardada correctamente en estado {acta.get_estado_display()}.")
            return redirect("actas_app:sesion_detail", pk=sesion.pk)
        messages.error(request, f"No se pudo guardar el acta. {form.errors.as_text()}")
    else:
        form = ActaSesionForm(instance=acta)

    context = {"sesion": sesion, "acta": acta, "form": form}
    context.update(contexto_flujo_acta(sesion, acta, request.user))
    return render(request, "actas_app/acta_edit.html", context)


@login_required
@grupo_requerido("Administrador", "Almacen")
def acta_cambiar_estado(request, sesion_id):
    sesion = get_object_or_404(SesionConsistorial, pk=sesion_id)
    acta, _ = ActaSesion.objects.get_or_create(
        sesion=sesion,
        defaults={
            "numero_acta": ActaSesion.siguiente_numero(sesion.anio),
            "anio": sesion.anio,
            "redactado_por": request.user,
            "contenido_borrador": "",
        },
    )
    if request.method != "POST":
        messages.error(request, "El cambio de estado debe realizarse desde los botones de acción del acta.")
        return redirect("actas_app:sesion_detail", pk=sesion.pk)

    accion = request.POST.get("accion")
    if accion == "enviar_revision":
        if acta.estado != ActaSesion.Estado.BORRADOR:
            messages.error(request, "Solo las actas en borrador pueden enviarse a revisión.")
            return redirect("actas_app:sesion_detail", pk=sesion.pk)
        acta.estado = ActaSesion.Estado.EN_REVISION
        acta.revisado_por = request.user
        acta.save(update_fields=["estado", "revisado_por", "actualizado_en"])
        sesion.estado = SesionConsistorial.Estado.EN_REVISION
        sesion.revisada_por = request.user
        sesion.save(update_fields=["estado", "revisada_por", "actualizado_en"])
        registrar_bitacora(request.user, str(acta), "cambio de estado", "Acta enviada a revisión")
        messages.success(request, "Acta enviada a revisión correctamente.")
        return redirect("actas_app:sesion_detail", pk=sesion.pk)

    if accion == "aprobar":
        return aprobar_acta(request, sesion, acta)

    messages.error(request, "Acción de estado no reconocida para el acta.")
    return redirect("actas_app:sesion_detail", pk=sesion.pk)


def aprobar_acta(request, sesion, acta, estado_origen=None):
    if not usuario_puede_aprobar_actas(request.user):
        messages.error(request, "No tienes permiso para aprobar actas. Solicita la aprobación a un usuario Administrador.")
        return redirect("actas_app:sesion_detail", pk=sesion.pk)

    estado_actual = estado_origen or acta.estado
    if estado_actual != ActaSesion.Estado.EN_REVISION:
        messages.error(request, "Solo se pueden aprobar actas que estén en estado En revisión.")
        return redirect("actas_app:sesion_detail", pk=sesion.pk)

    pendientes = pendientes_para_aprobar_acta(sesion, acta)
    if pendientes:
        messages.error(request, "No se puede aprobar el acta. Falta: " + ", ".join(pendientes) + ".")
        return redirect("actas_app:sesion_detail", pk=sesion.pk)

    ahora = timezone.now()
    acta.estado = ActaSesion.Estado.APROBADA
    acta.aprobado_por = request.user
    acta.fecha_aprobacion = ahora
    # Guardado explícito del valor correcto: acta.estado = "aprobada" y acta.save().
    try:
        acta.save(update_fields=["estado", "aprobado_por", "fecha_aprobacion", "actualizado_en"])
    except ValidationError as exc:
        messages.error(request, f"No se pudo aprobar el acta: {exc}")
        return redirect("actas_app:sesion_detail", pk=sesion.pk)

    sesion.estado = SesionConsistorial.Estado.APROBADA
    sesion.aprobada_por = request.user
    sesion.fecha_aprobacion = ahora
    sesion.save(update_fields=["estado", "aprobada_por", "fecha_aprobacion", "actualizado_en"])
    registrar_bitacora(request.user, str(acta), "cambio de estado", "Acta aprobada")
    messages.success(request, "Acta aprobada y guardada correctamente.")
    return redirect("actas_app:sesion_detail", pk=sesion.pk)


@login_required
@grupo_requerido("Administrador", "Almacen")
def acta_generar(request, sesion_id):
    sesion = get_object_or_404(SesionConsistorial, pk=sesion_id)
    acta, _ = ActaSesion.objects.get_or_create(
        sesion=sesion,
        defaults={
            "numero_acta": ActaSesion.siguiente_numero(sesion.anio),
            "anio": sesion.anio,
            "redactado_por": request.user,
        },
    )
    acta.contenido_borrador = generar_borrador_acta(sesion)
    acta.save(update_fields=["contenido_borrador", "actualizado_en"])
    registrar_bitacora(request.user, str(sesion), "generación de acta", "Borrador generado automáticamente")
    messages.success(request, "Borrador de acta generado.")
    return redirect("actas_app:acta_edit", sesion_id=sesion.pk)


@login_required
@grupo_requerido("Administrador", "Almacen")
def acta_word_download(request, sesion_id):
    sesion = get_object_or_404(
        SesionConsistorial.objects.select_related("acta", "moderador", "secretario", "tipo_sesion"),
        pk=sesion_id,
    )
    acta = getattr(sesion, "acta", None)
    if not acta:
        messages.error(request, "La sesión aún no tiene un acta creada.")
        return redirect("actas_app:acta_edit", sesion_id=sesion.pk)

    contenido = (acta.contenido_final or acta.contenido_borrador or "").strip()
    if not contenido:
        messages.error(request, "El acta no tiene contenido para exportar.")
        return redirect("actas_app:acta_edit", sesion_id=sesion.pk)

    document_stream, filename = build_acta_docx(acta)
    registrar_bitacora(request.user, str(acta), "descarga de acta", "Exportación Word generada")

    response = HttpResponse(
        document_stream.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}.docx"'
    return response


@login_required
@grupo_requerido("Administrador", "Almacen")
def configuracion_base(request):
    context = {
        "tipos_sesion": TipoSesion.objects.all(),
        "miembros": MiembroConsistorio.objects.filter(activo=True).order_by("apellidos", "nombres"),
        "plantillas": AgendaPlantilla.objects.filter(activa=True).prefetch_related("puntos"),
        "puntos_plantilla": PuntoAgendaPlantilla.objects.select_related("plantilla").count(),
        "textos_base": TextoBaseActa.objects.filter(activo=True).count(),
        "areas_informe": AreaInformeCatalogo.objects.filter(activa=True).count(),
    }
    return render(request, "actas_app/configuracion_base.html", context)


@login_required
@grupo_requerido("Administrador", "Almacen")
def tipo_sesion_list(request):
    return render(request, "actas_app/catalog_list.html", {
        "title": "Tipos de sesión",
        "items": TipoSesion.objects.all(),
        "new_url": "actas_app:tipo_sesion_create",
        "edit_url": "actas_app:tipo_sesion_edit",
    })


@login_required
@grupo_requerido("Administrador", "Almacen")
def tipo_sesion_create(request):
    form = TipoSesionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Tipo de sesión creado.")
        return redirect("actas_app:tipo_sesion_list")
    return render(request, "actas_app/simple_form.html", {"title": "Nuevo tipo de sesión", "form": form})


@login_required
@grupo_requerido("Administrador", "Almacen")
def tipo_sesion_edit(request, pk):
    item = get_object_or_404(TipoSesion, pk=pk)
    form = TipoSesionForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Tipo de sesión actualizado.")
        return redirect("actas_app:tipo_sesion_list")
    return render(request, "actas_app/simple_form.html", {"title": "Editar tipo de sesión", "form": form})


@login_required
@grupo_requerido("Administrador", "Almacen")
def miembro_list(request):
    return render(request, "actas_app/catalog_list.html", {
        "title": "Miembros del consistorio",
        "items": MiembroConsistorio.objects.order_by("apellidos", "nombres"),
        "new_url": "actas_app:miembro_create",
        "edit_url": "actas_app:miembro_edit",
    })


@login_required
@grupo_requerido("Administrador", "Almacen")
def miembro_create(request):
    form = MiembroConsistorioForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Miembro creado.")
        return redirect("actas_app:miembro_list")
    return render(request, "actas_app/simple_form.html", {"title": "Nuevo miembro", "form": form})


@login_required
@grupo_requerido("Administrador", "Almacen")
def miembro_edit(request, pk):
    item = get_object_or_404(MiembroConsistorio, pk=pk)
    form = MiembroConsistorioForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Miembro actualizado.")
        return redirect("actas_app:miembro_list")
    return render(request, "actas_app/simple_form.html", {"title": "Editar miembro", "form": form})


@login_required
@grupo_requerido("Administrador", "Almacen")
def plantilla_list(request):
    return render(request, "actas_app/catalog_list.html", {
        "title": "Plantillas de agenda",
        "items": AgendaPlantilla.objects.all(),
        "new_url": "actas_app:plantilla_create",
        "edit_url": "actas_app:plantilla_edit",
    })


@login_required
@grupo_requerido("Administrador", "Almacen")
def plantilla_create(request):
    form = AgendaPlantillaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Plantilla creada.")
        return redirect("actas_app:plantilla_list")
    return render(request, "actas_app/simple_form.html", {"title": "Nueva plantilla", "form": form})


@login_required
@grupo_requerido("Administrador", "Almacen")
def plantilla_edit(request, pk):
    item = get_object_or_404(AgendaPlantilla, pk=pk)
    form = AgendaPlantillaForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Plantilla actualizada.")
        return redirect("actas_app:plantilla_list")
    return render(request, "actas_app/simple_form.html", {"title": "Editar plantilla", "form": form})


@login_required
@grupo_requerido("Administrador", "Almacen")
def punto_plantilla_list(request):
    items = PuntoAgendaPlantilla.objects.select_related("plantilla").order_by("plantilla__nombre", "orden")
    return render(request, "actas_app/catalog_list.html", {
        "title": "Puntos de agenda plantilla",
        "items": items,
        "new_url": "actas_app:punto_plantilla_create",
        "edit_url": "actas_app:punto_plantilla_edit",
    })


@login_required
@grupo_requerido("Administrador", "Almacen")
def punto_plantilla_create(request):
    form = PuntoAgendaPlantillaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Punto de plantilla creado.")
        return redirect("actas_app:punto_plantilla_list")
    return render(request, "actas_app/simple_form.html", {"title": "Nuevo punto de plantilla", "form": form})


@login_required
@grupo_requerido("Administrador", "Almacen")
def punto_plantilla_edit(request, pk):
    item = get_object_or_404(PuntoAgendaPlantilla, pk=pk)
    form = PuntoAgendaPlantillaForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Punto de plantilla actualizado.")
        return redirect("actas_app:punto_plantilla_list")
    return render(request, "actas_app/simple_form.html", {"title": "Editar punto de plantilla", "form": form})


@login_required
@grupo_requerido("Administrador", "Almacen")
def texto_base_list(request):
    return render(request, "actas_app/catalog_list.html", {
        "title": "Textos base de acta",
        "items": TextoBaseActa.objects.all(),
        "new_url": "actas_app:texto_base_create",
        "edit_url": "actas_app:texto_base_edit",
    })


@login_required
@grupo_requerido("Administrador", "Almacen")
def texto_base_create(request):
    form = TextoBaseActaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Texto base creado.")
        return redirect("actas_app:texto_base_list")
    return render(request, "actas_app/simple_form.html", {"title": "Nuevo texto base", "form": form})


@login_required
@grupo_requerido("Administrador", "Almacen")
def texto_base_edit(request, pk):
    item = get_object_or_404(TextoBaseActa, pk=pk)
    form = TextoBaseActaForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Texto base actualizado.")
        return redirect("actas_app:texto_base_list")
    return render(request, "actas_app/simple_form.html", {"title": "Editar texto base", "form": form})


@login_required
@grupo_requerido("Administrador", "Almacen")
def area_informe_list(request):
    return render(request, "actas_app/catalog_list.html", {
        "title": "Áreas de informe",
        "items": AreaInformeCatalogo.objects.all(),
        "new_url": "actas_app:area_informe_create",
        "edit_url": "actas_app:area_informe_edit",
    })


@login_required
@grupo_requerido("Administrador", "Almacen")
def area_informe_create(request):
    form = AreaInformeCatalogoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Área de informe creada.")
        return redirect("actas_app:area_informe_list")
    return render(request, "actas_app/simple_form.html", {"title": "Nueva área de informe", "form": form})


@login_required
@grupo_requerido("Administrador", "Almacen")
def area_informe_edit(request, pk):
    item = get_object_or_404(AreaInformeCatalogo, pk=pk)
    form = AreaInformeCatalogoForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Área de informe actualizada.")
        return redirect("actas_app:area_informe_list")
    return render(request, "actas_app/simple_form.html", {"title": "Editar área de informe", "form": form})
