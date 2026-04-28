from django.db import migrations


def seed_data(apps, schema_editor):
    TipoSesion = apps.get_model("actas_app", "TipoSesion")
    AgendaPlantilla = apps.get_model("actas_app", "AgendaPlantilla")
    PuntoAgendaPlantilla = apps.get_model("actas_app", "PuntoAgendaPlantilla")

    ordinaria, _ = TipoSesion.objects.get_or_create(nombre="Ordinaria", defaults={"descripcion": "Sesión ordinaria", "activa": True})
    TipoSesion.objects.get_or_create(nombre="Extraordinaria", defaults={"descripcion": "Sesión extraordinaria", "activa": True})

    plantilla, _ = AgendaPlantilla.objects.get_or_create(
        nombre="Agenda ordinaria base",
        defaults={"descripcion": "Plantilla base para sesión ordinaria", "activa": True},
    )

    puntos = [
        ("I", "I", "Apertura", "apertura", 1),
        ("II", "II", "Discusión y aprobación de agenda", "agenda", 2),
        ("III", "III", "Lectura y aprobación del acta anterior", "acta_anterior", 3),
        ("IV", "IV", "Informes", "informe", 4),
        ("V", "V", "Correspondencia", "correspondencia", 5),
        ("VI", "VI", "Asuntos pendientes", "pendiente", 6),
        ("VII", "VII", "Asuntos nuevos", "nuevo", 7),
        ("VIII", "VIII", "Cierre de sesión", "cierre", 8),
    ]

    for seccion, numeral, titulo, tipo, orden in puntos:
        PuntoAgendaPlantilla.objects.get_or_create(
            plantilla=plantilla,
            seccion=seccion,
            numeral=numeral,
            titulo=titulo,
            tipo_punto=tipo,
            orden=orden,
            defaults={"activo": True},
        )


def reverse_seed(apps, schema_editor):
    TipoSesion = apps.get_model("actas_app", "TipoSesion")
    AgendaPlantilla = apps.get_model("actas_app", "AgendaPlantilla")
    TipoSesion.objects.filter(nombre__in=["Ordinaria", "Extraordinaria"]).delete()
    AgendaPlantilla.objects.filter(nombre="Agenda ordinaria base").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("actas_app", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_data, reverse_seed),
    ]
