from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Count, Q, Max
from django.utils import timezone


class TimeStampedModel(models.Model):
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class TipoSesion(TimeStampedModel):
    nombre = models.CharField(max_length=80, unique=True)
    descripcion = models.TextField(blank=True)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "Tipo de sesión"
        verbose_name_plural = "Tipos de sesión"

    def __str__(self):
        return self.nombre


class MiembroConsistorio(TimeStampedModel):
    class TipoMiembro(models.TextChoices):
        ANCIANO = "anciano", "Anciano"
        DIACONO = "diacono", "Diácono"
        PASTOR = "pastor", "Pastor"
        INVITADO = "invitado", "Invitado"
        OTRO = "otro", "Otro"

    nombres = models.CharField(max_length=120)
    apellidos = models.CharField(max_length=120)
    cargo = models.CharField(max_length=120)
    tipo_miembro = models.CharField(max_length=20, choices=TipoMiembro.choices, default=TipoMiembro.OTRO)
    activo = models.BooleanField(default=True)
    observaciones = models.TextField(blank=True)

    class Meta:
        ordering = ["apellidos", "nombres"]
        verbose_name = "Miembro de consistorio"
        verbose_name_plural = "Miembros de consistorio"

    @property
    def nombre_completo(self):
        return f"{self.nombres} {self.apellidos}".strip()

    def __str__(self):
        return f"{self.nombre_completo} ({self.cargo})"


class AgendaPlantilla(TimeStampedModel):
    nombre = models.CharField(max_length=120, unique=True)
    descripcion = models.TextField(blank=True)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "Plantilla de agenda"
        verbose_name_plural = "Plantillas de agenda"

    def __str__(self):
        return self.nombre


class PuntoBase(models.Model):
    class TipoPunto(models.TextChoices):
        APERTURA = "apertura", "Apertura"
        AGENDA = "agenda", "Discusión agenda"
        ACTA_ANTERIOR = "acta_anterior", "Acta anterior"
        INFORME = "informe", "Informe"
        CORRESPONDENCIA = "correspondencia", "Correspondencia"
        PENDIENTE = "pendiente", "Asunto pendiente"
        NUEVO = "nuevo", "Asunto nuevo"
        CIERRE = "cierre", "Cierre"

    seccion = models.CharField(max_length=80)
    numeral = models.CharField(max_length=20)
    titulo = models.CharField(max_length=220)
    tipo_punto = models.CharField(max_length=30, choices=TipoPunto.choices, default=TipoPunto.NUEVO)
    orden = models.PositiveIntegerField(default=1)
    activo = models.BooleanField(default=True)

    class Meta:
        abstract = True
        ordering = ["orden", "id"]


class PuntoAgendaPlantilla(PuntoBase, TimeStampedModel):
    plantilla = models.ForeignKey(AgendaPlantilla, on_delete=models.CASCADE, related_name="puntos")

    class Meta(PuntoBase.Meta):
        verbose_name = "Punto de agenda de plantilla"
        verbose_name_plural = "Puntos de agenda de plantilla"

    def __str__(self):
        return f"{self.plantilla.nombre} - {self.numeral} {self.titulo}"


class SesionConsistorial(TimeStampedModel):
    class Estado(models.TextChoices):
        BORRADOR = "borrador", "Borrador"
        EN_DESARROLLO = "en_desarrollo", "En desarrollo"
        EN_REVISION = "en_revision", "En revisión"
        APROBADA = "aprobada", "Aprobada"

    numero = models.PositiveIntegerField()
    anio = models.PositiveIntegerField(default=timezone.now().year)
    tipo_sesion = models.ForeignKey(TipoSesion, on_delete=models.PROTECT, related_name="sesiones")
    fecha = models.DateField()
    lugar = models.CharField(max_length=255)
    hora_inicio = models.TimeField(blank=True, null=True)
    hora_fin = models.TimeField(blank=True, null=True)
    moderador = models.ForeignKey(MiembroConsistorio, on_delete=models.PROTECT, related_name="sesiones_moderadas")
    secretario = models.ForeignKey(MiembroConsistorio, on_delete=models.PROTECT, related_name="sesiones_secretariadas")
    quorum_requerido = models.PositiveIntegerField(default=1)
    quorum_alcanzado = models.PositiveIntegerField(default=0)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.BORRADOR)
    observaciones_generales = models.TextField(blank=True)
    creada_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name="sesiones_creadas")
    revisada_por = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, related_name="sesiones_revisadas")
    aprobada_por = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, related_name="sesiones_aprobadas")
    fecha_aprobacion = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-anio", "-numero"]
        constraints = [
            models.UniqueConstraint(fields=["numero", "anio"], name="uniq_sesion_numero_anio"),
        ]
        verbose_name = "Sesión consistorial"
        verbose_name_plural = "Sesiones consistoriales"

    @property
    def cumple_quorum(self):
        return self.quorum_alcanzado >= self.quorum_requerido

    def recalcular_quorum(self):
        presentes = self.asistencias.filter(asistencia=AsistenciaSesion.Asistencia.PRESENTE).count()
        if self.quorum_alcanzado != presentes:
            self.quorum_alcanzado = presentes
            self.save(update_fields=["quorum_alcanzado", "actualizado_en"])
        return self.quorum_alcanzado

    @classmethod
    def siguiente_numero(cls, anio):
        ultimo = cls.objects.filter(anio=anio).aggregate(max_n=Max("numero"))["max_n"] or 0
        return ultimo + 1

    def clean(self):
        if self.hora_fin and self.hora_inicio and self.hora_fin <= self.hora_inicio:
            raise ValidationError("La hora de cierre debe ser mayor a la hora de inicio.")

    def __str__(self):
        return f"Sesión {self.numero}/{self.anio} - {self.get_estado_display()}"


class PuntoAgendaSesion(PuntoBase, TimeStampedModel):
    sesion = models.ForeignKey(SesionConsistorial, on_delete=models.CASCADE, related_name="puntos_agenda")
    contenido_resumen = models.TextField(blank=True)
    observaciones = models.TextField(blank=True)

    class Meta(PuntoBase.Meta):
        verbose_name = "Punto de agenda de sesión"
        verbose_name_plural = "Puntos de agenda de sesión"

    def __str__(self):
        return f"{self.sesion} - {self.numeral} {self.titulo}"


class AsistenciaSesion(TimeStampedModel):
    class Asistencia(models.TextChoices):
        PRESENTE = "presente", "Presente"
        AUSENTE = "ausente", "Ausente"
        EXCUSADO = "excusado", "Excusado"

    sesion = models.ForeignKey(SesionConsistorial, on_delete=models.CASCADE, related_name="asistencias")
    miembro = models.ForeignKey(MiembroConsistorio, on_delete=models.PROTECT, related_name="asistencias")
    asistencia = models.CharField(max_length=20, choices=Asistencia.choices, default=Asistencia.AUSENTE)
    observaciones = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["miembro__apellidos"]
        constraints = [
            models.UniqueConstraint(fields=["sesion", "miembro"], name="uniq_asistencia_sesion_miembro"),
        ]
        verbose_name = "Asistencia de sesión"
        verbose_name_plural = "Asistencias de sesión"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.sesion.recalcular_quorum()

    def delete(self, *args, **kwargs):
        sesion = self.sesion
        super().delete(*args, **kwargs)
        sesion.recalcular_quorum()

    def __str__(self):
        return f"{self.miembro.nombre_completo} - {self.get_asistencia_display()}"


class InformeSesion(TimeStampedModel):
    class TipoInforme(models.TextChoices):
        NARRATIVO = "narrativo", "Narrativo"
        FINANCIERO = "financiero", "Financiero"

    sesion = models.ForeignKey(SesionConsistorial, on_delete=models.CASCADE, related_name="informes")
    area = models.CharField(max_length=120)
    tipo_informe = models.CharField(max_length=15, choices=TipoInforme.choices, default=TipoInforme.NARRATIVO)
    expositor = models.CharField(max_length=120)
    resumen = models.TextField()
    saldo_inicial = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    ingresos = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    egresos = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    saldo_final = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    fondo_especial = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    observaciones = models.TextField(blank=True)

    class Meta:
        ordering = ["area"]
        verbose_name = "Informe de sesión"
        verbose_name_plural = "Informes de sesión"

    def clean(self):
        if self.tipo_informe == self.TipoInforme.FINANCIERO:
            calculado = (self.saldo_inicial + self.ingresos) - self.egresos
            if self.saldo_final != calculado:
                raise ValidationError("Saldo final debe coincidir con saldo inicial + ingresos - egresos.")

    def __str__(self):
        return f"{self.sesion} - {self.area}"


class AsuntoPendiente(TimeStampedModel):
    class Estado(models.TextChoices):
        ABIERTO = "abierto", "Abierto"
        EN_PROCESO = "en_proceso", "En proceso"
        POSPUESTO = "pospuesto", "Pospuesto"
        RESUELTO = "resuelto", "Resuelto"

    class Prioridad(models.TextChoices):
        ALTA = "alta", "Alta"
        MEDIA = "media", "Media"
        BAJA = "baja", "Baja"

    titulo = models.CharField(max_length=220)
    descripcion = models.TextField()
    responsable = models.ForeignKey(MiembroConsistorio, on_delete=models.PROTECT, related_name="pendientes")
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.ABIERTO)
    prioridad = models.CharField(max_length=10, choices=Prioridad.choices, default=Prioridad.MEDIA)
    fecha_ingreso = models.DateField(default=timezone.now)
    activo = models.BooleanField(default=True)
    sesiones = models.ManyToManyField("SesionConsistorial", blank=True, related_name="pendientes_vinculados")

    class Meta:
        ordering = ["estado", "-fecha_ingreso"]
        verbose_name = "Asunto pendiente"
        verbose_name_plural = "Asuntos pendientes"

    def __str__(self):
        return self.titulo


class CorrespondenciaSesion(TimeStampedModel):
    sesion = models.ForeignKey(SesionConsistorial, on_delete=models.CASCADE, related_name="correspondencias")
    remitente = models.CharField(max_length=160)
    asunto = models.CharField(max_length=220)
    descripcion = models.TextField()
    decision = models.TextField(blank=True)
    genera_acuerdo = models.BooleanField(default=False)
    genera_pendiente = models.BooleanField(default=False)
    adjunto = models.FileField(upload_to="actas/correspondencia", blank=True, null=True)

    class Meta:
        ordering = ["-creado_en"]
        verbose_name = "Correspondencia de sesión"
        verbose_name_plural = "Correspondencia de sesión"

    def __str__(self):
        return f"{self.asunto} ({self.remitente})"


class AsuntoNuevoSesion(TimeStampedModel):
    sesion = models.ForeignKey(SesionConsistorial, on_delete=models.CASCADE, related_name="asuntos_nuevos")
    titulo = models.CharField(max_length=220)
    descripcion = models.TextField()
    presentado_por = models.CharField(max_length=120)
    decision = models.TextField(blank=True)
    pasa_a_pendiente = models.BooleanField(default=False)
    genera_acuerdo = models.BooleanField(default=False)

    class Meta:
        ordering = ["-creado_en"]
        verbose_name = "Asunto nuevo"
        verbose_name_plural = "Asuntos nuevos"

    def __str__(self):
        return self.titulo


class AcuerdoConsistorial(TimeStampedModel):
    class Estado(models.TextChoices):
        ABIERTO = "abierto", "Abierto"
        EN_PROCESO = "en_proceso", "En proceso"
        CERRADO = "cerrado", "Cerrado"

    class Origen(models.TextChoices):
        MANUAL = "manual", "Manual"
        CORRESPONDENCIA = "correspondencia", "Correspondencia"
        ASUNTO_NUEVO = "asunto_nuevo", "Asunto nuevo"

    numero = models.PositiveIntegerField()
    anio = models.PositiveIntegerField(default=timezone.now().year)
    sesion = models.ForeignKey(SesionConsistorial, on_delete=models.CASCADE, related_name="acuerdos")
    origen_tipo = models.CharField(max_length=20, choices=Origen.choices, default=Origen.MANUAL)
    texto = models.TextField()
    responsable = models.ForeignKey(MiembroConsistorio, on_delete=models.PROTECT, related_name="acuerdos")
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.ABIERTO)
    fecha = models.DateField(default=timezone.now)
    observaciones = models.TextField(blank=True)

    class Meta:
        ordering = ["-anio", "-numero"]
        constraints = [
            models.UniqueConstraint(fields=["numero", "anio"], name="uniq_acuerdo_numero_anio"),
        ]
        verbose_name = "Acuerdo consistorial"
        verbose_name_plural = "Acuerdos consistoriales"

    @classmethod
    def siguiente_numero(cls, anio):
        ultimo = cls.objects.filter(anio=anio).aggregate(max_n=Max("numero"))["max_n"] or 0
        return ultimo + 1

    def __str__(self):
        return f"Acuerdo {self.numero}/{self.anio}"


class ActaSesion(TimeStampedModel):
    class Estado(models.TextChoices):
        BORRADOR = "borrador", "Borrador"
        EN_REVISION = "en_revision", "En revisión"
        APROBADA = "aprobada", "Aprobada"

    sesion = models.OneToOneField(SesionConsistorial, on_delete=models.CASCADE, related_name="acta")
    numero_acta = models.PositiveIntegerField()
    anio = models.PositiveIntegerField(default=timezone.now().year)
    contenido_borrador = models.TextField(blank=True)
    contenido_final = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.BORRADOR)
    redactado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name="actas_redactadas")
    revisado_por = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, related_name="actas_revisadas")
    aprobado_por = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, related_name="actas_aprobadas")
    fecha_redaccion = models.DateTimeField(auto_now_add=True)
    fecha_aprobacion = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-anio", "-numero_acta"]
        constraints = [
            models.UniqueConstraint(fields=["numero_acta", "anio"], name="uniq_acta_numero_anio"),
        ]
        verbose_name = "Acta de sesión"
        verbose_name_plural = "Actas de sesión"

    @classmethod
    def siguiente_numero(cls, anio):
        ultimo = cls.objects.filter(anio=anio).aggregate(max_n=Max("numero_acta"))["max_n"] or 0
        return ultimo + 1

    def save(self, *args, **kwargs):
        if self.estado == self.Estado.APROBADA and not self.fecha_aprobacion:
            self.fecha_aprobacion = timezone.now()
        if self.pk:
            anterior = ActaSesion.objects.filter(pk=self.pk).first()
            if anterior and anterior.estado == self.Estado.APROBADA and self.estado == self.Estado.APROBADA:
                raise ValidationError("El acta aprobada no puede modificarse libremente.")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Acta {self.numero_acta}/{self.anio}"


class SeguimientoAsuntoPendiente(TimeStampedModel):
    asunto_pendiente = models.ForeignKey(AsuntoPendiente, on_delete=models.CASCADE, related_name="seguimientos")
    sesion = models.ForeignKey(SesionConsistorial, on_delete=models.SET_NULL, blank=True, null=True, related_name="seguimientos")
    detalle = models.TextField()
    estado_anterior = models.CharField(max_length=20, choices=AsuntoPendiente.Estado.choices)
    estado_nuevo = models.CharField(max_length=20, choices=AsuntoPendiente.Estado.choices)
    fecha = models.DateTimeField(default=timezone.now)
    usuario = models.ForeignKey(User, on_delete=models.PROTECT, related_name="seguimientos_pendientes")

    class Meta:
        ordering = ["-fecha"]
        verbose_name = "Seguimiento de asunto pendiente"
        verbose_name_plural = "Seguimientos de asuntos pendientes"

    def __str__(self):
        return f"{self.asunto_pendiente} - {self.estado_anterior}→{self.estado_nuevo}"


class BitacoraSesion(TimeStampedModel):
    referencia = models.CharField(max_length=120)
    usuario = models.ForeignKey(User, on_delete=models.PROTECT, related_name="bitacora_actas")
    accion = models.CharField(max_length=120)
    detalle = models.TextField(blank=True)
    fecha = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-fecha"]
        verbose_name = "Bitácora de sesión"
        verbose_name_plural = "Bitácoras de sesión"

    def __str__(self):
        return f"{self.referencia}: {self.accion}"


class AreaInformeCatalogo(TimeStampedModel):
    nombre = models.CharField(max_length=120, unique=True)
    descripcion = models.TextField(blank=True)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "Área de informe"
        verbose_name_plural = "Áreas de informe"

    def __str__(self):
        return self.nombre


class TextoBaseActa(TimeStampedModel):
    nombre = models.CharField(max_length=120, unique=True)
    contenido = models.TextField()
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "Texto base de acta"
        verbose_name_plural = "Textos base de acta"

    def __str__(self):
        return self.nombre
