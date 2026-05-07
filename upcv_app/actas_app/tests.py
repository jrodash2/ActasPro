from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from .models import ActaSesion, AsistenciaSesion, MiembroConsistorio, PuntoAgendaSesion, SesionConsistorial, TipoSesion


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
