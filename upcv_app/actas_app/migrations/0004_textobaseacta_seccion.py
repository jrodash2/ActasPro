from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("actas_app", "0003_areainformecatalogo_textobaseacta"),
    ]

    operations = [
        migrations.AddField(
            model_name="textobaseacta",
            name="seccion",
            field=models.CharField(
                choices=[
                    ("apertura", "Apertura"),
                    ("agenda", "Agenda"),
                    ("acta_anterior", "Acta anterior"),
                    ("informes", "Informes"),
                    ("correspondencia", "Correspondencia"),
                    ("pendientes", "Asuntos pendientes"),
                    ("asuntos_nuevos", "Asuntos nuevos"),
                    ("cierre", "Cierre"),
                ],
                default="apertura",
                max_length=30,
            ),
        ),
        migrations.AlterModelOptions(
            name="textobaseacta",
            options={
                "ordering": ["seccion", "nombre"],
                "verbose_name": "Plantilla de redacción del acta",
                "verbose_name_plural": "Plantillas de redacción del acta",
            },
        ),
    ]
