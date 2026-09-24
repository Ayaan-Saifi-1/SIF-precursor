from django.urls import path
from core import views
urlpatterns=[
 path("api/health/",views.health),
 path("api/samples/",views.samples),
 path("api/reports/",views.reports),
 path("api/reports/import/",views.import_reports),
 path("api/reports/<str:report_id>/",views.report_detail),
 path("api/analyze/",views.analyze_report),
 path("api/analyses/<str:report_id>/",views.analysis_detail),
 path("api/dashboard/summary/",views.summary),
 path("api/dashboard/charts/",views.dashboard_charts),
 path("api/dashboard/site-density/",views.site_density),
 path("api/dashboard/activity-density/",views.activity_density),
 path("api/dashboard/emerging-patterns/",views.patterns),
 path("api/patterns/",views.patterns),
 path("api/patterns/<str:pattern_id>/reports/",views.pattern_reports),
 path("api/patterns/<str:pattern_id>/",views.pattern_detail),
 path("api/reviews/",views.reviews),
 path("api/reviews/<int:review_id>/decision/",views.review_decision),
 path("api/reviews/<int:review_id>/",views.review_detail),
]
