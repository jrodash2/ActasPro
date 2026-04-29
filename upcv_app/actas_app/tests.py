from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from .models import ActaSesion, MiembroConsistorio, SesionConsistorial, TipoSesion


class ActaWordDownloadTests(TestCase):
    def setUp(self):
        self.group, _ = Group.objects.get_or_create(name="Almacen")
        self.user = User.objects.create_user(username="tester", password="123456")
        self.user.groups.add(self.group)
        self.client.login(username="tester", password="123456")

        self.tipo = TipoSesion.objects.create(nombre="Ordinaria")
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
