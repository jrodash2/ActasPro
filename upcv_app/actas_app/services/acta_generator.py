import re

from django.utils.formats import date_format

from ..models import TextoBaseActa


VARIABLES_TEXTO_BASE = [
    "fecha",
    "hora_inicio",
    "hora_fin",
    "hora_finalizacion",
    "moderador",
    "secretario",
    "presentes",
    "ausentes",
    "excusados",
    "quorum_alcanzado",
    "quorum_requerido",
    "tipo_sesion",
    "lugar",
    "numero_sesion",
    "anio",
    "informes",
    "correspondencia",
    "asuntos_pendientes",
    "asuntos_nuevos",
    "acuerdos",
    "numero",
    "titulo",
    "seguimiento",
    "estado",
    "cierre_estado",
    "lectura_biblica",
    "oracion_inicial",
    "proxima_sesion",
]


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


def _textos_base_activos():
    textos = {}
    for texto in TextoBaseActa.objects.filter(activo=True).order_by("seccion", "-actualizado_en", "nombre"):
        textos.setdefault(texto.seccion, texto.contenido)
    return textos


def _render_texto_base(plantilla, variables):
    def reemplazar(match):
        clave = match.group(1)
        return str(variables.get(clave, "") or "")

    return re.sub(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", reemplazar, plantilla or "").strip()



def previsualizar_texto_base(contenido):
    variables = {clave: f"[{clave}]" for clave in VARIABLES_TEXTO_BASE}
    variables.update(
        {
            "fecha": "jueves, 7 de mayo de 2026",
            "hora_inicio": "19:00",
            "hora_fin": "21:00",
            "hora_finalizacion": "21:00",
            "moderador": "Juan Pérez",
            "secretario": "Ana López",
            "presentes": "Juan Pérez, Ana López",
            "tipo_sesion": "ordinaria",
            "lugar": "Templo Central",
            "numero": "6.1",
            "titulo": "Puertas",
            "seguimiento": "Se informa que ya fueron instaladas",
            "estado": "resuelto",
            "cierre_estado": "por lo que el punto queda resuelto.",
        }
    )
    return _render_texto_base(contenido, variables)


def _plantilla(textos_base, seccion, predeterminada, variables):
    return _render_texto_base(textos_base.get(seccion, predeterminada), variables)


def _formatear_pendiente_narrativo(indice, pendiente, seguimientos=None, plantilla=None):
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

    variables = {
        "numero": f"6.{indice}",
        "titulo": titulo,
        "seguimiento": detalles,
        "estado": _texto_estado_pendiente(estado_resultante),
        "cierre_estado": _cierre_estado_pendiente(estado_resultante),
    }
    plantilla = plantilla or "{numero} {titulo}. {seguimiento}, {cierre_estado}"
    return _render_texto_base(plantilla, variables)


def _formatear_pendientes(sesion, plantilla_pendiente=None):
    seguimientos = list(sesion.seguimientos.select_related("asunto_pendiente").order_by("fecha", "pk"))
    seguimientos_por_pendiente = {}
    for seguimiento in seguimientos:
        seguimientos_por_pendiente.setdefault(seguimiento.asunto_pendiente_id, []).append(seguimiento)

    pendientes_ordenados = []
    pendientes_incluidos = set()
    for pendiente in sesion.pendientes_vinculados.filter(activo=True).order_by("titulo", "pk"):
        pendientes_ordenados.append(pendiente)
        pendientes_incluidos.add(pendiente.pk)

    for seguimiento in seguimientos:
        pendiente = seguimiento.asunto_pendiente
        if pendiente.pk in pendientes_incluidos:
            continue
        pendientes_ordenados.append(pendiente)
        pendientes_incluidos.add(pendiente.pk)

    return [
        _formatear_pendiente_narrativo(
            indice,
            pendiente,
            seguimientos_por_pendiente.get(pendiente.pk),
            plantilla=plantilla_pendiente,
        )
        for indice, pendiente in enumerate(pendientes_ordenados, start=1)
    ]


def generar_borrador_acta(sesion):
    textos_base = _textos_base_activos()
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
    plantilla_pendiente = textos_base.get("pendientes") if "{titulo}" in textos_base.get("pendientes", "") else None
    pendientes = _formatear_pendientes(sesion, plantilla_pendiente=plantilla_pendiente)
    nuevos = [f"{n.titulo}: {n.decision or 'Sin decisión registrada.'}" for n in sesion.asuntos_nuevos.all()]
    acuerdos = [f"Acuerdo {a.numero}/{a.anio}: {a.texto}" for a in sesion.acuerdos.all()]

    fecha_literal = date_format(sesion.fecha, "l, j \\d\\e F \\d\\e Y")
    variables = {
        "fecha": fecha_literal,
        "hora_inicio": sesion.hora_inicio or "hora pendiente",
        "hora_fin": sesion.hora_fin or "hora pendiente",
        "hora_finalizacion": sesion.hora_fin or "hora pendiente",
        "moderador": sesion.moderador.nombre_completo,
        "secretario": sesion.secretario.nombre_completo,
        "presentes": presentes_texto,
        "ausentes": ", ".join(ausentes),
        "excusados": ", ".join(excusados),
        "quorum_alcanzado": sesion.quorum_alcanzado,
        "quorum_requerido": sesion.quorum_requerido,
        "tipo_sesion": sesion.tipo_sesion.nombre.lower(),
        "lugar": sesion.lugar,
        "numero_sesion": sesion.numero,
        "anio": sesion.anio,
        "informes": _lineas(informes),
        "correspondencia": _lineas(correspondencias),
        "asuntos_pendientes": _lineas(pendientes, prefijo=""),
        "asuntos_nuevos": _lineas(nuevos),
        "acuerdos": _lineas(acuerdos),
        "lectura_biblica": "",
        "oracion_inicial": "",
        "proxima_sesion": "",
    }

    apertura = _plantilla(
        textos_base,
        "apertura",
        "En {lugar}, siendo las {hora_inicio} del día {fecha}, se reunió el consistorio en sesión {tipo_sesion}. Estando presentes los siguientes hermanos: {presentes}. Se verificó quórum con {quorum_alcanzado} presentes de {quorum_requerido} requeridos.",
        variables,
    )
    agenda = _plantilla(
        textos_base,
        "agenda",
        "Se revisó la agenda previamente preparada y fue aprobada por unanimidad, con las observaciones registradas en los puntos de agenda.",
        variables,
    )
    acta_anterior = _plantilla(
        textos_base,
        "acta_anterior",
        "Se dio lectura al acta anterior y se dejó constancia de su aprobación o enmiendas según discusión plenaria.",
        variables,
    )
    informes_texto = _plantilla(textos_base, "informes", "{informes}", variables)
    correspondencia_texto = _plantilla(textos_base, "correspondencia", "{correspondencia}", variables)
    pendientes_texto = variables["asuntos_pendientes"]
    if textos_base.get("pendientes") and not plantilla_pendiente:
        pendientes_texto = _plantilla(textos_base, "pendientes", "{asuntos_pendientes}", variables)
    nuevos_texto = _plantilla(textos_base, "asuntos_nuevos", "{asuntos_nuevos}", variables)
    cierre = _plantilla(
        textos_base,
        "cierre",
        "No habiendo más asuntos que tratar, se dio por finalizada la sesión a las {hora_finalizacion}, dejando constancia para los efectos correspondientes.",
        variables,
    )

    return f"""IGLESIA PRESBITERIANA — CONSISTORIO LOCAL

ACTA NÚMERO {sesion.numero}/{sesion.anio}

{apertura}{ausencias_texto}

PRIMERO. APERTURA
Se dio apertura formal de la sesión por el moderador {sesion.moderador.nombre_completo}. Secretario actuante: {sesion.secretario.nombre_completo}.
Asistentes presentes:
{_lineas(asistentes)}

SEGUNDO. DISCUSIÓN Y APROBACIÓN DE AGENDA
{agenda}

TERCERO. LECTURA Y APROBACIÓN DEL ACTA ANTERIOR
{acta_anterior}

CUARTO. INFORMES
{informes_texto}

QUINTO. CORRESPONDENCIA
{correspondencia_texto}

SEXTO. ASUNTOS PENDIENTES
{pendientes_texto}

SÉPTIMO. ASUNTOS NUEVOS
{nuevos_texto}

OCTAVO. ACUERDOS CONSISTORIALES
{_lineas(acuerdos)}

NOVENO. CIERRE
{cierre}

Firmamos para constancia:

_________________________
Moderador

_________________________
Secretario
"""
