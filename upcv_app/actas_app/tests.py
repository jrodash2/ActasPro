from datetime import date

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from .models import ActaSesion, AsistenciaSesion, MiembroConsistorio, PuntoAgendaSesion, SesionConsistorial, TipoSesion
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

    def test_redirects_with_message_when_no_content(self):
        ActaSesion.objects.create(
            sesion=self.sesion,
            numero_acta=3,
            anio=2026,
            contenido_borrador="",
            contenido_final="",
            redactado_por=self.user,
        )
        url = reverse("actas_app:acta_word_download", args=[self.sesion.pk])
        response = self.client.get(url, follow=True)

        self.assertRedirects(response, reverse("actas_app:acta_edit", kwargs={"sesion_id": self.sesion.pk}))
        messages = list(response.context["messages"])
        self.assertTrue(any("no tiene contenido para exportar" in str(message).lower() for message in messages))


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
