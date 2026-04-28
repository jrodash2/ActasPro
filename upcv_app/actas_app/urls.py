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
]
