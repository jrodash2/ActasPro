from django.utils.formats import date_format


def _lineas(lista, prefijo="- "):
    if not lista:
        return "- Sin registros."
    return "\n".join(f"{prefijo}{item}" for item in lista)


def generar_borrador_acta(sesion):
    asistentes = [
        f"{a.miembro.nombre_completo} ({a.miembro.cargo})"
        for a in sesion.asistencias.select_related("miembro").filter(asistencia="presente")
    ]
    informes = [f"{i.area}: {i.resumen}" for i in sesion.informes.all()]
    correspondencias = [f"{c.remitente} - {c.asunto}. Decisión: {c.decision or 'Pendiente.'}" for c in sesion.correspondencias.all()]
    pendientes = [f"{p.titulo} ({p.get_estado_display()})" for p in sesion.pendientes_vinculados.filter(activo=True)]
    nuevos = [f"{n.titulo}: {n.decision or 'Sin decisión registrada.'}" for n in sesion.asuntos_nuevos.all()]
    acuerdos = [f"Acuerdo {a.numero}/{a.anio}: {a.texto}" for a in sesion.acuerdos.all()]

    fecha_literal = date_format(sesion.fecha, "l, j \\d\\e F \\d\\e Y")

    return f"""IGLESIA PRESBITERIANA — CONSISTORIO LOCAL

ACTA NÚMERO {sesion.numero}/{sesion.anio}

En {sesion.lugar}, siendo las {sesion.hora_inicio or 'hora pendiente'} del día {fecha_literal}, se reunió el consistorio en sesión {sesion.tipo_sesion.nombre.lower()}. Se verificó quórum con {sesion.quorum_alcanzado} presentes de {sesion.quorum_requerido} requeridos.

PRIMERO. APERTURA
Se dio apertura formal de la sesión por el moderador {sesion.moderador.nombre_completo}. Secretario actuante: {sesion.secretario.nombre_completo}.
Asistentes:
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
