from django.urls import path

from . import views

app_name = "actas_app"

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("sesiones/", views.sesion_list, name="sesion_list"),
    path("sesiones/nueva/", views.sesion_create, name="sesion_create"),
    path("sesiones/<int:pk>/", views.sesion_detail, name="sesion_detail"),
    path("sesiones/<int:pk>/agenda/", views.sesion_agenda, name="sesion_agenda"),
    path("sesiones/<int:pk>/asistencia/", views.sesion_asistencia, name="sesion_asistencia"),
    path("sesiones/<int:sesion_id>/informes/nuevo/", views.informe_create, name="informe_create"),
    path("sesiones/<int:sesion_id>/correspondencia/nuevo/", views.correspondencia_create, name="correspondencia_create"),
    path("sesiones/<int:sesion_id>/asuntos-nuevos/nuevo/", views.asunto_nuevo_create, name="asunto_nuevo_create"),
    path("sesiones/<int:sesion_id>/acta/", views.acta_edit, name="acta_edit"),
    path("sesiones/<int:sesion_id>/acta/generar/", views.acta_generar, name="acta_generar"),
    path("pendientes/", views.pendiente_list, name="pendiente_list"),
    path("pendientes/nuevo/", views.pendiente_create, name="pendiente_create"),
    path("pendientes/<int:pk>/", views.pendiente_detail, name="pendiente_detail"),
    path("acuerdos/", views.acuerdo_list, name="acuerdo_list"),
    path("acuerdos/nuevo/", views.acuerdo_create, name="acuerdo_create"),
    path("actas/", views.acta_list, name="acta_list"),
    path("configuracion/", views.configuracion_base, name="configuracion_base"),
    path("configuracion/tipos-sesion/", views.tipo_sesion_list, name="tipo_sesion_list"),
    path("configuracion/tipos-sesion/nuevo/", views.tipo_sesion_create, name="tipo_sesion_create"),
    path("configuracion/tipos-sesion/<int:pk>/editar/", views.tipo_sesion_edit, name="tipo_sesion_edit"),
    path("configuracion/miembros/", views.miembro_list, name="miembro_list"),
    path("configuracion/miembros/nuevo/", views.miembro_create, name="miembro_create"),
    path("configuracion/miembros/<int:pk>/editar/", views.miembro_edit, name="miembro_edit"),
    path("configuracion/plantillas/", views.plantilla_list, name="plantilla_list"),
    path("configuracion/plantillas/nueva/", views.plantilla_create, name="plantilla_create"),
    path("configuracion/plantillas/<int:pk>/editar/", views.plantilla_edit, name="plantilla_edit"),
    path("configuracion/puntos-plantilla/", views.punto_plantilla_list, name="punto_plantilla_list"),
    path("configuracion/puntos-plantilla/nuevo/", views.punto_plantilla_create, name="punto_plantilla_create"),
    path("configuracion/puntos-plantilla/<int:pk>/editar/", views.punto_plantilla_edit, name="punto_plantilla_edit"),
    path("configuracion/textos-base/", views.texto_base_list, name="texto_base_list"),
    path("configuracion/textos-base/nuevo/", views.texto_base_create, name="texto_base_create"),
    path("configuracion/textos-base/<int:pk>/editar/", views.texto_base_edit, name="texto_base_edit"),
    path("configuracion/areas-informe/", views.area_informe_list, name="area_informe_list"),
    path("configuracion/areas-informe/nueva/", views.area_informe_create, name="area_informe_create"),
    path("configuracion/areas-informe/<int:pk>/editar/", views.area_informe_edit, name="area_informe_edit"),
]
