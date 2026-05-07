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


def _normalizar_oracion(texto):
    return (texto or "").strip().rstrip(".")


def _texto_estado_pendiente(estado):
    textos_estado = {
        "abierto": "abierto",
        "en_proceso": "en proceso",
        "pospuesto": "pospuesto",
        "resuelto": "resuelto",
    }
    return textos_estado.get(estado, str(estado or "pendiente").replace("_", " ").lower())


def _cierre_estado_pendiente(estado):
    estado_texto = _texto_estado_pendiente(estado)
    if estado == "resuelto":
        return f"por lo que el punto queda {estado_texto}."
    return f"quedando el punto {estado_texto}."


def _formatear_pendiente_narrativo(indice, pendiente, seguimientos=None):
    seguimientos = seguimientos or []
    titulo = _normalizar_oracion(pendiente.titulo)
    if seguimientos:
        detalles = " ".join(
            _normalizar_oracion(seguimiento.detalle)
            for seguimiento in seguimientos
            if _normalizar_oracion(seguimiento.detalle)
        )
        detalles = detalles or "Se deja constancia del seguimiento tratado"
        estado_resultante = seguimientos[-1].estado_nuevo
    else:
        detalles = _normalizar_oracion(pendiente.descripcion) or "Se deja constancia del asunto pendiente"
        estado_resultante = pendiente.estado
    return f"6.{indice} {titulo}. {detalles}, {_cierre_estado_pendiente(estado_resultante)}"


def _formatear_pendientes(sesion):
    seguimientos = list(sesion.seguimientos.select_related("asunto_pendiente").order_by("fecha", "pk"))
    seguimientos_por_pendiente = {}
    pendientes_ordenados = []

    for seguimiento in seguimientos:
        pendiente = seguimiento.asunto_pendiente
        if pendiente.pk not in seguimientos_por_pendiente:
            seguimientos_por_pendiente[pendiente.pk] = []
            pendientes_ordenados.append(pendiente)
        seguimientos_por_pendiente[pendiente.pk].append(seguimiento)

    for pendiente in sesion.pendientes_vinculados.filter(activo=True).order_by("titulo", "pk"):
        if pendiente.pk in seguimientos_por_pendiente:
            continue
        pendientes_ordenados.append(pendiente)

    return [
        _formatear_pendiente_narrativo(indice, pendiente, seguimientos_por_pendiente.get(pendiente.pk))
        for indice, pendiente in enumerate(pendientes_ordenados, start=1)
    ]


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
{_lineas(pendientes, prefijo="")}

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
