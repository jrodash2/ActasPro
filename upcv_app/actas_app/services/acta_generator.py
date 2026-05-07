from django.utils.formats import date_format


def _lineas(lista, prefijo="- "):
    if not lista:
        return "- Sin registros."
    return "\n".join(f"{prefijo}{item}" for item in lista)


def _quetzales(valor):
    return f"Q {valor or 0:,.2f}"


def _formatear_informe(informe):
    if informe.tipo_informe == "financiero":
        resumen_financiero = (
            f"{informe.area}. {informe.expositor} informa que el saldo inicial fue de {_quetzales(informe.saldo_inicial)}, "
            f"los ingresos fueron de {_quetzales(informe.ingresos)}, los egresos fueron de {_quetzales(informe.egresos)}, "
            f"dejando un saldo final de {_quetzales(informe.saldo_final)}."
        )
        if informe.resumen:
            resumen_financiero += f" {informe.resumen}"
        return resumen_financiero
    return f"{informe.area}. {informe.expositor}: {informe.resumen}"


def _formatear_pendientes(sesion):
    seguimientos = list(sesion.seguimientos.select_related("asunto_pendiente").order_by("fecha"))
    lineas = [
        f"{seguimiento.asunto_pendiente.titulo}. {seguimiento.detalle} Estado: {seguimiento.get_estado_nuevo_display()}."
        for seguimiento in seguimientos
    ]
    pendientes_con_seguimiento = {seguimiento.asunto_pendiente_id for seguimiento in seguimientos}
    for pendiente in sesion.pendientes_vinculados.filter(activo=True).order_by("titulo"):
        if pendiente.pk in pendientes_con_seguimiento:
            continue
        lineas.append(f"{pendiente.titulo}. {pendiente.descripcion} Estado: {pendiente.get_estado_display()}.")
    return lineas


def generar_borrador_acta(sesion):
    asistencias = sesion.asistencias.select_related("miembro").order_by("miembro__apellidos", "miembro__nombres")
    asistentes = [
        f"{a.miembro.nombre_completo} ({a.miembro.cargo})"
        for a in asistencias
        if a.asistencia == "presente"
    ]
    ausentes = [
        f"{a.miembro.nombre_completo} ({a.miembro.cargo})"
        for a in asistencias
        if a.asistencia == "ausente"
    ]
    excusados = [
        f"{a.miembro.nombre_completo} ({a.miembro.cargo})"
        for a in asistencias
        if a.asistencia == "excusado"
    ]
    presentes_texto = ", ".join(asistentes) if asistentes else "sin presentes registrados"
    ausencias_texto = ""
    if ausentes or excusados:
        ausencias_texto = (
            "\nSe deja constancia de la ausencia de:\n"
            f"Ausentes: {', '.join(ausentes) if ausentes else 'sin ausentes registrados'}.\n"
            f"Excusados: {', '.join(excusados) if excusados else 'sin excusados registrados'}."
        )
    informes = [_formatear_informe(i) for i in sesion.informes.all().order_by("area")]
    correspondencias = [f"{c.remitente} - {c.asunto}. Decisión: {c.decision or 'Pendiente.'}" for c in sesion.correspondencias.all()]
    pendientes = _formatear_pendientes(sesion)
    nuevos = [f"{n.titulo}: {n.decision or 'Sin decisión registrada.'}" for n in sesion.asuntos_nuevos.all()]
    acuerdos = [f"Acuerdo {a.numero}/{a.anio}: {a.texto}" for a in sesion.acuerdos.all()]

    fecha_literal = date_format(sesion.fecha, "l, j \\d\\e F \\d\\e Y")

    return f"""IGLESIA PRESBITERIANA — CONSISTORIO LOCAL

ACTA NÚMERO {sesion.numero}/{sesion.anio}

En {sesion.lugar}, siendo las {sesion.hora_inicio or 'hora pendiente'} del día {fecha_literal}, se reunió el consistorio en sesión {sesion.tipo_sesion.nombre.lower()}. Estando presentes los siguientes hermanos: {presentes_texto}. Se verificó quórum con {sesion.quorum_alcanzado} presentes de {sesion.quorum_requerido} requeridos.{ausencias_texto}

PRIMERO. APERTURA
Se dio apertura formal de la sesión por el moderador {sesion.moderador.nombre_completo}. Secretario actuante: {sesion.secretario.nombre_completo}.
Asistentes presentes:
{_lineas(asistentes)}

SEGUNDO. DISCUSIÓN Y APROBACIÓN DE AGENDA
Se revisó la agenda previamente preparada y fue aprobada por unanimidad, con las observaciones registradas en los puntos de agenda.

TERCERO. LECTURA Y APROBACIÓN DEL ACTA ANTERIOR
Se dio lectura al acta anterior y se dejó constancia de su aprobación o enmiendas según discusión plenaria.

CUARTO. INFORMES
{_lineas(informes)}

QUINTO. CORRESPONDENCIA
{_lineas(correspondencias)}

SEXTO. ASUNTOS PENDIENTES
{_lineas(pendientes)}

SÉPTIMO. ASUNTOS NUEVOS
{_lineas(nuevos)}

OCTAVO. ACUERDOS CONSISTORIALES
{_lineas(acuerdos)}

NOVENO. CIERRE
No habiendo más asuntos que tratar, se dio por finalizada la sesión a las {sesion.hora_fin or 'hora pendiente'}, dejando constancia para los efectos correspondientes.

Firmamos para constancia:

_________________________
Moderador

_________________________
Secretario
"""
