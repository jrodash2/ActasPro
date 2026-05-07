from datetime import date
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from .models import ActaSesion, AsistenciaSesion, InformeSesion, AsuntoPendiente, SeguimientoAsuntoPendiente, MiembroConsistorio, PuntoAgendaSesion, SesionConsistorial, TextoBaseActa, TipoSesion
from .services.acta_generator import generar_borrador_acta


class ActaWordDownloadTests(TestCase):
    def setUp(self):
        self.group, _ = Group.objects.get_or_create(name="Almacen")
        self.user = User.objects.create_user(username="tester", password="123456")
        self.user.groups.add(self.group)
        self.client.login(username="tester", password="123456")

        self.tipo, _ = TipoSesion.objects.get_or_create(nombre="Ordinaria")
        self.moderador = MiembroConsistorio.objects.create(
            nombres="Juan", apellidos="Perez", cargo="Moderador", tipo_miembro=MiembroConsistorio.TipoMiembro.ANCIANO
        )
        self.secretario = MiembroConsistorio.objects.create(
            nombres="Ana", apellidos="Lopez", cargo="Secretario", tipo_miembro=MiembroConsistorio.TipoMiembro.DIACONO
        )
        self.sesion = SesionConsistorial.objects.create(
            numero=1,
            anio=2026,
            tipo_sesion=self.tipo,
            fecha="2026-04-20",
            lugar="Templo Central",
            moderador=self.moderador,
            secretario=self.secretario,
            quorum_requerido=1,
            creada_por=self.user,
        )

    def test_url_resolves_and_downloads_docx_using_contenido_final(self):
        acta = ActaSesion.objects.create(
            sesion=self.sesion,
            numero_acta=1,
            anio=2026,
            contenido_borrador="Borrador",
            contenido_final="Contenido final acta",
            redactado_por=self.user,
        )
        url = reverse("actas_app:acta_word_download", args=[self.sesion.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        self.assertIn("attachment; filename=", response["Content-Disposition"])
        self.assertIn(f"acta-{acta.numero_acta}-{acta.anio}.docx", response["Content-Disposition"])
        self.assertGreater(len(response.content), 0)

    def test_fallback_uses_contenido_borrador(self):
        ActaSesion.objects.create(
            sesion=self.sesion,
            numero_acta=2,
            anio=2026,
            contenido_borrador="Solo borrador para exportar",
            contenido_final="",
            redactado_por=self.user,
        )
        url = reverse("actas_app:acta_word_download", args=[self.sesion.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertGreater(len(response.content), 0)

    def test_word_download_regenerates_borrador_when_no_final_content(self):
        acta = ActaSesion.objects.create(
            sesion=self.sesion,
            numero_acta=3,
            anio=2026,
            contenido_borrador="",
            contenido_final="",
            redactado_por=self.user,
        )
        url = reverse("actas_app:acta_word_download", args=[self.sesion.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        acta.refresh_from_db()
        self.assertIn("SEXTO. ASUNTOS PENDIENTES", acta.contenido_borrador)
        self.assertGreater(len(response.content), 0)


class ActaEstadoFlowTests(TestCase):
    def setUp(self):
        self.admin_group, _ = Group.objects.get_or_create(name="Administrador")
        self.almacen_group, _ = Group.objects.get_or_create(name="Almacen")
        self.user = User.objects.create_user(username="admin_actas", password="123456")
        self.user.groups.add(self.admin_group)
        self.client.login(username="admin_actas", password="123456")

        self.tipo, _ = TipoSesion.objects.get_or_create(nombre="Extraordinaria")
        self.moderador = MiembroConsistorio.objects.create(
            nombres="Luis", apellidos="Gomez", cargo="Moderador", tipo_miembro=MiembroConsistorio.TipoMiembro.ANCIANO
        )
        self.secretario = MiembroConsistorio.objects.create(
            nombres="Maria", apellidos="Rojas", cargo="Secretaria", tipo_miembro=MiembroConsistorio.TipoMiembro.DIACONO
        )
        self.sesion = SesionConsistorial.objects.create(
            numero=10,
            anio=2026,
            tipo_sesion=self.tipo,
            fecha="2026-05-01",
            lugar="Sala consistorial",
            moderador=self.moderador,
            secretario=self.secretario,
            quorum_requerido=1,
            creada_por=self.user,
        )
        self.acta = ActaSesion.objects.create(
            sesion=self.sesion,
            numero_acta=10,
            anio=2026,
            contenido_borrador="Borrador narrativo",
            contenido_final="PRIMERO. Se abre la sesión. SEGUNDO. Se aprueba la agenda.",
            estado=ActaSesion.Estado.EN_REVISION,
            redactado_por=self.user,
            revisado_por=self.user,
        )
        PuntoAgendaSesion.objects.create(
            sesion=self.sesion,
            seccion="I",
            numeral="I",
            titulo="Apertura",
            tipo_punto="apertura",
            orden=1,
        )
        AsistenciaSesion.objects.create(
            sesion=self.sesion,
            miembro=self.moderador,
            asistencia=AsistenciaSesion.Asistencia.PRESENTE,
        )

    def test_aprobar_acta_guarda_estado_correcto(self):
        response = self.client.post(
            reverse("actas_app:acta_cambiar_estado", args=[self.sesion.pk]),
            {"accion": "aprobar"},
            follow=True,
        )

        self.assertRedirects(response, reverse("actas_app:sesion_detail", args=[self.sesion.pk]))
        self.acta.refresh_from_db()
        self.sesion.refresh_from_db()
        self.assertEqual(self.acta.estado, ActaSesion.Estado.APROBADA)
        self.assertEqual(self.sesion.estado, SesionConsistorial.Estado.APROBADA)
        self.assertEqual(self.acta.aprobado_por, self.user)
        self.assertTrue(any("aprobada y guardada" in str(message).lower() for message in response.context["messages"]))

    def test_no_aprueba_si_faltan_requisitos(self):
        self.acta.contenido_final = ""
        self.acta.save(update_fields=["contenido_final"])
        response = self.client.post(
            reverse("actas_app:acta_cambiar_estado", args=[self.sesion.pk]),
            {"accion": "aprobar"},
            follow=True,
        )

        self.acta.refresh_from_db()
        self.assertEqual(self.acta.estado, ActaSesion.Estado.EN_REVISION)
        self.assertTrue(any("contenido del acta final" in str(message).lower() for message in response.context["messages"]))

    def test_usuario_sin_permiso_no_aprueba(self):
        self.client.logout()
        usuario_almacen = User.objects.create_user(username="solo_almacen", password="123456")
        usuario_almacen.groups.add(self.almacen_group)
        self.client.login(username="solo_almacen", password="123456")

        response = self.client.post(
            reverse("actas_app:acta_cambiar_estado", args=[self.sesion.pk]),
            {"accion": "aprobar"},
            follow=True,
        )

        self.acta.refresh_from_db()
        self.assertEqual(self.acta.estado, ActaSesion.Estado.EN_REVISION)
        self.assertTrue(any("no tienes permiso" in str(message).lower() for message in response.context["messages"]))


class AsistenciaSesionFlowTests(TestCase):
    def setUp(self):
        self.group, _ = Group.objects.get_or_create(name="Almacen")
        self.user = User.objects.create_user(username="secretario", password="123456")
        self.user.groups.add(self.group)
        self.client.login(username="secretario", password="123456")

        self.tipo, _ = TipoSesion.objects.get_or_create(nombre="Ordinaria")
        self.moderador = MiembroConsistorio.objects.create(
            nombres="Carlos", apellidos="Arias", cargo="Moderador", tipo_miembro=MiembroConsistorio.TipoMiembro.ANCIANO
        )
        self.secretario = MiembroConsistorio.objects.create(
            nombres="Beatriz", apellidos="Diaz", cargo="Secretaria", tipo_miembro=MiembroConsistorio.TipoMiembro.DIACONO
        )
        self.inactivo = MiembroConsistorio.objects.create(
            nombres="Inactivo", apellidos="Prueba", cargo="Visitante", activo=False
        )
        self.sesion = SesionConsistorial.objects.create(
            numero=20,
            anio=2026,
            tipo_sesion=self.tipo,
            fecha=date(2026, 5, 2),
            lugar="Sala principal",
            moderador=self.moderador,
            secretario=self.secretario,
            quorum_requerido=1,
            creada_por=self.user,
        )

    def test_guarda_y_actualiza_asistencia_sin_duplicar(self):
        url = reverse("actas_app:sesion_asistencia", args=[self.sesion.pk])
        response = self.client.post(
            url,
            {
                f"asistencia_{self.moderador.pk}": AsistenciaSesion.Asistencia.PRESENTE,
                f"observaciones_{self.moderador.pk}": "Llegó a tiempo",
                f"asistencia_{self.secretario.pk}": AsistenciaSesion.Asistencia.EXCUSADO,
                f"observaciones_{self.secretario.pk}": "Presentó excusa",
            },
            follow=True,
        )

        self.assertRedirects(response, reverse("actas_app:sesion_detail", args=[self.sesion.pk]))
        self.assertEqual(AsistenciaSesion.objects.filter(sesion=self.sesion).count(), 2)
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.quorum_alcanzado, 1)
        self.assertTrue(any("asistencia guardada" in str(message).lower() for message in response.context["messages"]))

        response = self.client.post(
            url,
            {
                f"asistencia_{self.moderador.pk}": AsistenciaSesion.Asistencia.AUSENTE,
                f"observaciones_{self.moderador.pk}": "No asistió",
                f"asistencia_{self.secretario.pk}": AsistenciaSesion.Asistencia.PRESENTE,
                f"observaciones_{self.secretario.pk}": "",
            },
            follow=True,
        )

        self.assertEqual(AsistenciaSesion.objects.filter(sesion=self.sesion).count(), 2)
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.quorum_alcanzado, 1)
        self.assertEqual(
            AsistenciaSesion.objects.get(sesion=self.sesion, miembro=self.moderador).asistencia,
            AsistenciaSesion.Asistencia.AUSENTE,
        )

    def test_rechaza_miembros_sin_marcar_o_inactivos(self):
        url = reverse("actas_app:sesion_asistencia", args=[self.sesion.pk])
        response = self.client.post(
            url,
            {f"asistencia_{self.moderador.pk}": AsistenciaSesion.Asistencia.PRESENTE},
            follow=True,
        )
        self.assertEqual(AsistenciaSesion.objects.filter(sesion=self.sesion).count(), 0)
        self.assertTrue(any("miembros sin marcar" in str(message).lower() for message in response.context["messages"]))

        response = self.client.post(
            url,
            {
                f"asistencia_{self.moderador.pk}": AsistenciaSesion.Asistencia.PRESENTE,
                f"asistencia_{self.secretario.pk}": AsistenciaSesion.Asistencia.AUSENTE,
                f"asistencia_{self.inactivo.pk}": AsistenciaSesion.Asistencia.PRESENTE,
            },
            follow=True,
        )
        self.assertEqual(AsistenciaSesion.objects.filter(sesion=self.sesion).count(), 0)
        self.assertTrue(any("inválidos o inactivos" in str(message).lower() for message in response.context["messages"]))

    def test_bloquea_asistencia_si_acta_aprobada(self):
        ActaSesion.objects.create(
            sesion=self.sesion,
            numero_acta=20,
            anio=2026,
            contenido_final="Acta final",
            estado=ActaSesion.Estado.APROBADA,
            redactado_por=self.user,
        )
        response = self.client.post(
            reverse("actas_app:sesion_asistencia", args=[self.sesion.pk]),
            {
                f"asistencia_{self.moderador.pk}": AsistenciaSesion.Asistencia.PRESENTE,
                f"asistencia_{self.secretario.pk}": AsistenciaSesion.Asistencia.PRESENTE,
            },
            follow=True,
        )
        self.assertEqual(AsistenciaSesion.objects.filter(sesion=self.sesion).count(), 0)
        self.assertTrue(any("ya está aprobada" in str(message).lower() for message in response.context["messages"]))

    def test_generador_acta_refleja_presentes_ausentes_y_excusados(self):
        AsistenciaSesion.objects.create(
            sesion=self.sesion,
            miembro=self.moderador,
            asistencia=AsistenciaSesion.Asistencia.PRESENTE,
        )
        AsistenciaSesion.objects.create(
            sesion=self.sesion,
            miembro=self.secretario,
            asistencia=AsistenciaSesion.Asistencia.EXCUSADO,
        )

        contenido = generar_borrador_acta(self.sesion)

        self.assertIn("Estando presentes los siguientes hermanos", contenido)
        self.assertIn(self.moderador.nombre_completo, contenido)
        self.assertIn("Excusados:", contenido)
        self.assertIn(self.secretario.nombre_completo, contenido)


class InformeSesionFlowTests(TestCase):
    def setUp(self):
        self.group, _ = Group.objects.get_or_create(name="Almacen")
        self.user = User.objects.create_user(username="informes", password="123456")
        self.user.groups.add(self.group)
        self.client.login(username="informes", password="123456")
        self.tipo, _ = TipoSesion.objects.get_or_create(nombre="Ordinaria")
        self.moderador = MiembroConsistorio.objects.create(nombres="Mario", apellidos="Luna", cargo="Moderador")
        self.secretario = MiembroConsistorio.objects.create(nombres="Laura", apellidos="Mendez", cargo="Secretaria")
        self.sesion = SesionConsistorial.objects.create(
            numero=30,
            anio=2026,
            tipo_sesion=self.tipo,
            fecha=date(2026, 5, 3),
            lugar="Salón",
            moderador=self.moderador,
            secretario=self.secretario,
            creada_por=self.user,
        )

    def test_informe_financiero_calcula_saldo_final_y_vincula_sesion(self):
        response = self.client.post(
            reverse("actas_app:informe_create", args=[self.sesion.pk]),
            {
                "area": "Tesorería",
                "expositor": "Tesorera",
                "resumen": "Detalle adicional.",
                "saldo_inicial": "1000.00",
                "ingresos": "250.00",
                "egresos": "100.00",
                "saldo_final": "0.00",
                "fondo_especial": "0.00",
                "observaciones": "",
            },
            follow=True,
        )

        self.assertRedirects(response, reverse("actas_app:sesion_informes", args=[self.sesion.pk]))
        informe = InformeSesion.objects.get(sesion=self.sesion, area="Tesorería")
        self.assertEqual(informe.tipo_informe, InformeSesion.TipoInforme.FINANCIERO)
        self.assertEqual(informe.saldo_final, Decimal("1150.00"))
        self.assertTrue(any("informe guardado" in str(message).lower() for message in response.context["messages"]))

    def test_no_permite_duplicar_area_fija_pero_permite_otros(self):
        InformeSesion.objects.create(sesion=self.sesion, area="Pastor", expositor="Pastor", resumen="Informe")
        response = self.client.post(
            reverse("actas_app:informe_create", args=[self.sesion.pk]),
            {"area": "Pastor", "expositor": "Otro", "resumen": "Duplicado"},
            follow=True,
        )
        self.assertEqual(InformeSesion.objects.filter(sesion=self.sesion, area="Pastor").count(), 1)
        self.assertContains(response, "Ya existe un informe de Pastor")

        response = self.client.post(
            reverse("actas_app:informe_create", args=[self.sesion.pk]),
            {"area": "Otros", "area_otro": "Informe especial", "expositor": "Invitado", "resumen": "Contenido"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(InformeSesion.objects.filter(sesion=self.sesion, area="Informe especial").exists())

    def test_bloquea_edicion_y_eliminacion_si_acta_aprobada(self):
        informe = InformeSesion.objects.create(sesion=self.sesion, area="Pastor", expositor="Pastor", resumen="Informe")
        ActaSesion.objects.create(
            sesion=self.sesion,
            numero_acta=30,
            anio=2026,
            contenido_final="Acta final",
            estado=ActaSesion.Estado.APROBADA,
            redactado_por=self.user,
        )
        response = self.client.post(
            reverse("actas_app:informe_edit", args=[informe.pk]),
            {"area": "Pastor", "expositor": "Pastor", "resumen": "Editado"},
            follow=True,
        )
        informe.refresh_from_db()
        self.assertEqual(informe.resumen, "Informe")
        self.assertTrue(any("ya está aprobada" in str(message).lower() for message in response.context["messages"]))

        self.client.post(reverse("actas_app:informe_delete", args=[informe.pk]), follow=True)
        self.assertTrue(InformeSesion.objects.filter(pk=informe.pk).exists())

    def test_generador_acta_muestra_resumen_financiero_de_sesion(self):
        InformeSesion.objects.create(
            sesion=self.sesion,
            area="Tesorería",
            tipo_informe=InformeSesion.TipoInforme.FINANCIERO,
            expositor="Tesorera",
            resumen="Detalle adicional.",
            saldo_inicial=Decimal("95668.04"),
            ingresos=Decimal("6283.46"),
            egresos=Decimal("5790.00"),
        )
        contenido = generar_borrador_acta(self.sesion)
        self.assertIn("Tesorería. Tesorera informa", contenido)
        self.assertIn("Q 96,161.50", contenido)
        self.assertIn("Detalle adicional.", contenido)


class PendienteSeguimientoFlowTests(TestCase):
    def setUp(self):
        self.group, _ = Group.objects.get_or_create(name="Almacen")
        self.user = User.objects.create_user(username="pendientes", password="123456")
        self.user.groups.add(self.group)
        self.client.login(username="pendientes", password="123456")
        self.tipo, _ = TipoSesion.objects.get_or_create(nombre="Ordinaria")
        self.responsable = MiembroConsistorio.objects.create(nombres="Pedro", apellidos="Lopez", cargo="Responsable")
        self.sesion_origen = SesionConsistorial.objects.create(
            numero=40,
            anio=2026,
            tipo_sesion=self.tipo,
            fecha=date(2026, 5, 4),
            lugar="Salón",
            moderador=self.responsable,
            secretario=self.responsable,
            creada_por=self.user,
        )
        self.sesion_actual = SesionConsistorial.objects.create(
            numero=41,
            anio=2026,
            tipo_sesion=self.tipo,
            fecha=date(2026, 5, 11),
            lugar="Salón",
            moderador=self.responsable,
            secretario=self.responsable,
            creada_por=self.user,
        )
        self.pendiente = AsuntoPendiente.objects.create(
            titulo="Remodelación casa pastoral",
            descripcion="Pendiente solicitar cotizaciones",
            responsable=self.responsable,
            estado=AsuntoPendiente.Estado.ABIERTO,
        )
        self.pendiente.sesiones.add(self.sesion_origen, self.sesion_actual)

    def test_seguimiento_actualiza_estado_y_queda_vinculado_a_sesion(self):
        response = self.client.post(
            f"{reverse('actas_app:pendiente_detail', args=[self.pendiente.pk])}?sesion={self.sesion_actual.pk}",
            {
                "sesion": self.sesion_actual.pk,
                "detalle": "Se solicitó cotización de mano de obra.",
                "estado_nuevo": AsuntoPendiente.Estado.EN_PROCESO,
            },
            follow=True,
        )

        self.assertRedirects(response, reverse("actas_app:sesion_pendientes", args=[self.sesion_actual.pk]))
        self.pendiente.refresh_from_db()
        self.assertEqual(self.pendiente.estado, AsuntoPendiente.Estado.EN_PROCESO)
        seguimiento = SeguimientoAsuntoPendiente.objects.get(asunto_pendiente=self.pendiente)
        self.assertEqual(seguimiento.sesion, self.sesion_actual)
        self.assertEqual(seguimiento.estado_anterior, AsuntoPendiente.Estado.ABIERTO)
        self.assertEqual(seguimiento.estado_nuevo, AsuntoPendiente.Estado.EN_PROCESO)
        self.assertTrue(any("seguimiento guardado" in str(message).lower() for message in response.context["messages"]))

    def test_no_guarda_seguimiento_vacio(self):
        response = self.client.post(
            reverse("actas_app:pendiente_detail", args=[self.pendiente.pk]),
            {"sesion": self.sesion_actual.pk, "detalle": "   ", "estado_nuevo": AsuntoPendiente.Estado.RESUELTO},
            follow=True,
        )
        self.pendiente.refresh_from_db()
        self.assertEqual(self.pendiente.estado, AsuntoPendiente.Estado.ABIERTO)
        self.assertEqual(SeguimientoAsuntoPendiente.objects.count(), 0)
        self.assertContains(response, "El seguimiento no puede estar vacío")

    def test_bloquea_seguimiento_si_acta_aprobada(self):
        ActaSesion.objects.create(
            sesion=self.sesion_actual,
            numero_acta=41,
            anio=2026,
            contenido_final="Acta aprobada",
            estado=ActaSesion.Estado.APROBADA,
            redactado_por=self.user,
        )
        response = self.client.post(
            f"{reverse('actas_app:pendiente_detail', args=[self.pendiente.pk])}?sesion={self.sesion_actual.pk}",
            {"sesion": self.sesion_actual.pk, "detalle": "Seguimiento", "estado_nuevo": AsuntoPendiente.Estado.RESUELTO},
            follow=True,
        )
        self.assertEqual(SeguimientoAsuntoPendiente.objects.count(), 0)
        self.assertTrue(any("ya está aprobada" in str(message).lower() for message in response.context["messages"]))

    def test_generador_acta_incluye_seguimiento_de_sesion_actual(self):
        SeguimientoAsuntoPendiente.objects.create(
            asunto_pendiente=self.pendiente,
            sesion=self.sesion_actual,
            detalle="Se informa que ya se solicitó cotización de mano de obra.",
            estado_anterior=AsuntoPendiente.Estado.ABIERTO,
            estado_nuevo=AsuntoPendiente.Estado.EN_PROCESO,
            usuario=self.user,
        )
        self.pendiente.estado = AsuntoPendiente.Estado.EN_PROCESO
        self.pendiente.save(update_fields=["estado"])

        contenido = generar_borrador_acta(self.sesion_actual)

        self.assertIn("6.1 Remodelación casa pastoral", contenido)
        self.assertIn("Se informa que ya se solicitó cotización de mano de obra", contenido)
        self.assertIn("quedando el punto en proceso", contenido)
        self.assertNotIn("Estado: En proceso", contenido)

    def test_generador_acta_usa_seguimiento_de_sesion_actual_sin_duplicar_pendiente(self):
        seguimiento_anterior = SeguimientoAsuntoPendiente.objects.create(
            asunto_pendiente=self.pendiente,
            sesion=self.sesion_origen,
            detalle="Se presentó el asunto en una sesión anterior.",
            estado_anterior=AsuntoPendiente.Estado.ABIERTO,
            estado_nuevo=AsuntoPendiente.Estado.ABIERTO,
            usuario=self.user,
        )
        seguimiento_actual = SeguimientoAsuntoPendiente.objects.create(
            asunto_pendiente=self.pendiente,
            sesion=self.sesion_actual,
            detalle="Se informa que ya fueron instaladas las puertas solicitadas.",
            estado_anterior=AsuntoPendiente.Estado.ABIERTO,
            estado_nuevo=AsuntoPendiente.Estado.RESUELTO,
            usuario=self.user,
        )
        self.pendiente.estado = AsuntoPendiente.Estado.RESUELTO
        self.pendiente.save(update_fields=["estado"])

        contenido = generar_borrador_acta(self.sesion_actual)

        self.assertIn("6.1 Remodelación casa pastoral", contenido)
        self.assertIn(seguimiento_actual.detalle.rstrip("."), contenido)
        self.assertIn("por lo que el punto queda resuelto", contenido)
        self.assertNotIn(seguimiento_anterior.detalle.rstrip("."), contenido)
        self.assertEqual(contenido.count("Remodelación casa pastoral"), 1)

    def test_generador_acta_aplica_plantilla_base_para_pendientes(self):
        TextoBaseActa.objects.create(
            nombre="Pendiente narrativo",
            seccion=TextoBaseActa.Seccion.PENDIENTES,
            contenido="{numero} {titulo}. {seguimiento}, quedando finalmente {estado}.",
        )
        SeguimientoAsuntoPendiente.objects.create(
            asunto_pendiente=self.pendiente,
            sesion=self.sesion_actual,
            detalle="Se informa que la reparación fue revisada",
            estado_anterior=AsuntoPendiente.Estado.ABIERTO,
            estado_nuevo=AsuntoPendiente.Estado.RESUELTO,
            usuario=self.user,
        )
        self.pendiente.estado = AsuntoPendiente.Estado.RESUELTO
        self.pendiente.save(update_fields=["estado"])

        contenido = generar_borrador_acta(self.sesion_actual)

        self.assertIn("6.1 Remodelación casa pastoral. Se informa que la reparación fue revisada, quedando finalmente resuelto.", contenido)

    def test_generador_acta_aplica_plantilla_base_de_apertura_con_variables(self):
        TextoBaseActa.objects.create(
            nombre="Apertura personalizada",
            seccion=TextoBaseActa.Seccion.APERTURA,
            contenido="En {lugar}, preside {moderador} y secretaria {secretario} con {presentes} presentes.",
        )

        contenido = generar_borrador_acta(self.sesion_actual)

        self.assertIn("En Salón, preside Pedro Lopez y secretaria Pedro Lopez con sin presentes registrados presentes.", contenido)
