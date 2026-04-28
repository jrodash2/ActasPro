from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from almacen_app.utils import grupo_requerido

from .forms import (
    ActaSesionForm,
    AcuerdoConsistorialForm,
    AgendaSesionFormset,
    AsistenciaSesionFormset,
    AsuntoNuevoSesionForm,
    AsuntoPendienteForm,
    CorrespondenciaSesionForm,
    InformeSesionForm,
    SeguimientoAsuntoPendienteForm,
    SesionConsistorialForm,
)
from .models import (
    ActaSesion,
    AcuerdoConsistorial,
    AsistenciaSesion,
    AsuntoNuevoSesion,
    AsuntoPendiente,
    BitacoraSesion,
    CorrespondenciaSesion,
    InformeSesion,
    PuntoAgendaSesion,
    PuntoAgendaPlantilla,
    SeguimientoAsuntoPendiente,
    SesionConsistorial,
)
from .services.acta_generator import generar_borrador_acta


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
            if acta.estado == ActaSesion.Estado.EN_REVISION:
                acta.revisado_por = request.user
            if acta.estado == ActaSesion.Estado.APROBADA:
                acta.aprobado_por = request.user
                acta.fecha_aprobacion = timezone.now()
                sesion.estado = SesionConsistorial.Estado.APROBADA
                sesion.aprobada_por = request.user
                sesion.fecha_aprobacion = timezone.now()
                sesion.save(update_fields=["estado", "aprobada_por", "fecha_aprobacion", "actualizado_en"])
            acta.version += 1
            acta.save()
            registrar_bitacora(request.user, str(acta), "edición de acta", f"Estado: {acta.estado}")
            messages.success(request, "Acta actualizada.")
            return redirect("actas_app:sesion_detail", pk=sesion.pk)
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
