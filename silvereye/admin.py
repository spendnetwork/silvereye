from django.contrib import admin

from silvereye.models import Publisher, PublisherMetrics


class PublisherAdmin(admin.ModelAdmin):
    list_display = (
        'publisher_id',
        'publisher_name',
        'contact_name',
        'contact_email',
        'contact_telephone',
    )
    list_editable = (
        # 'publisher_id',
        'publisher_name',
        'contact_name',
        'contact_email',
        'contact_telephone',
    )


admin.site.register(Publisher, PublisherAdmin)


class PublisherMetricsAdmin(admin.ModelAdmin):
    list_display = [field.name for field in PublisherMetrics._meta.get_fields()]
    readonly_fields = [field.name for field in PublisherMetrics._meta.get_fields()]

admin.site.register(PublisherMetrics, PublisherMetricsAdmin)
