from django.contrib import messages
from django.contrib.auth.decorators import login_required
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
    AsistenciaSesionFormset,
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
from .services.docx_export import build_acta_docx_bytes, get_acta_export_content


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
    sesiones = SesionConsistorial.objects.select_related("tipo_sesion").order_by("-anio", "-numero")
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
    context = {
        "sesion": sesion,
        "informes": sesion.informes.all(),
        "correspondencias": sesion.correspondencias.all(),
        "asuntos_nuevos": sesion.asuntos_nuevos.all(),
        "acuerdos": sesion.acuerdos.all(),
        "pendientes": sesion.pendientes_vinculados.all(),
        "acta": getattr(sesion, "acta", None),
    }
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
    sesion = get_object_or_404(SesionConsistorial, pk=pk)
    if not sesion.asistencias.exists():
        for punto in sesion.puntos_agenda.all():
            pass
    if request.method == "POST":
        formset = AsistenciaSesionFormset(request.POST, instance=sesion)
        if formset.is_valid():
            formset.save()
            sesion.recalcular_quorum()
            registrar_bitacora(request.user, str(sesion), "registro de asistencia", "Se actualizó asistencia y quórum")
            messages.success(request, "Asistencia actualizada y quórum recalculado.")
            return redirect("actas_app:sesion_detail", pk=sesion.pk)
    else:
        if not sesion.asistencias.exists():
            for miembro in sesion.moderador.__class__.objects.filter(activo=True):
                AsistenciaSesion.objects.get_or_create(sesion=sesion, miembro=miembro)
        formset = AsistenciaSesionFormset(instance=sesion)
    return render(request, "actas_app/sesion_asistencia.html", {"sesion": sesion, "formset": formset})


@login_required
@grupo_requerido("Administrador", "Almacen")
def informe_create(request, sesion_id):
    sesion = get_object_or_404(SesionConsistorial, pk=sesion_id)
    if request.method == "POST":
        form = InformeSesionForm(request.POST)
        if form.is_valid():
            informe = form.save(commit=False)
            informe.sesion = sesion
            informe.save()
            registrar_bitacora(request.user, str(sesion), "registro de informe", informe.area)
            messages.success(request, "Informe agregado.")
            return redirect("actas_app:sesion_detail", pk=sesion.pk)
    else:
        form = InformeSesionForm()
    return render(request, "actas_app/simple_form.html", {"title": "Registrar informe", "form": form, "sesion": sesion})


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
        form = ActaSesionForm(request.POST, instance=acta)
        if form.is_valid():
            acta = form.save(commit=False)
            accion = request.POST.get("accion", "guardar")

            if accion == "revision":
                acta.estado = ActaSesion.Estado.EN_REVISION
                acta.revisado_por = request.user
            elif accion == "aprobar":
                acta.estado = ActaSesion.Estado.APROBADA
                if not (acta.contenido_final or "").strip():
                    messages.error(request, "Para aprobar el acta debes completar el contenido final.")
                    return render(request, "actas_app/acta_edit.html", {"sesion": sesion, "acta": acta, "form": form})
                acta.aprobado_por = request.user
                acta.fecha_aprobacion = timezone.now()
                sesion.estado = SesionConsistorial.Estado.APROBADA
                sesion.aprobada_por = request.user
                sesion.fecha_aprobacion = timezone.now()
                sesion.save(update_fields=["estado", "aprobada_por", "fecha_aprobacion", "actualizado_en"])
            else:
                acta.estado = ActaSesion.Estado.BORRADOR

            acta.version += 1
            acta.save()
            registrar_bitacora(request.user, str(acta), "edición de acta", f"Estado: {acta.estado}")
            messages.success(request, "Acta actualizada correctamente.")
            return redirect("actas_app:acta_edit", sesion_id=sesion.pk)
        messages.error(request, f"No se pudo guardar el acta. {form.errors.as_text()}")
    else:
        form = ActaSesionForm(instance=acta)

    return render(request, "actas_app/acta_edit.html", {"sesion": sesion, "acta": acta, "form": form})


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
def acta_export_word(request, acta_id):
    acta = get_object_or_404(ActaSesion.objects.select_related("sesion"), pk=acta_id)
    sesion = acta.sesion

    if not get_acta_export_content(acta):
        messages.error(request, "El acta no tiene contenido final ni borrador para exportar a Word.")
        return redirect("actas_app:acta_edit", sesion_id=sesion.pk)

    try:
        doc_bytes = build_acta_docx_bytes(acta)
    except ModuleNotFoundError:
        messages.error(request, "No está instalada la librería python-docx en el servidor.")
        return redirect("actas_app:acta_edit", sesion_id=sesion.pk)
    except ValueError as error:
        messages.error(request, str(error))
        return redirect("actas_app:acta_edit", sesion_id=sesion.pk)

    filename = f"Acta_{acta.numero_acta}-{acta.anio}.docx"
    response = HttpResponse(
        doc_bytes,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["Content-Length"] = str(len(doc_bytes))
    response["Cache-Control"] = "no-store"
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
