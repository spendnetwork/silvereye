from django.contrib import admin

from silvereye.models import Publisher, PublisherMetrics, SuppliedData, FileSubmission


class PublisherAdmin(admin.ModelAdmin):
    list_display = (
        'publisher_id',
        'publisher_name',
        'publisher_scheme',
        'uri',
        'ocid_prefix',
        'contact_name',
        'contact_email',
        'contact_telephone',
    )
    list_editable = (
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

class SuppliedDataAdmin(admin.ModelAdmin):
    list_display = ['id',
                    'source_url',
                    'original_file',
                    'current_app',
                    'created',
                    'modified',
                    'rendered',
                    'schema_version',
                    'data_schema_version',
                    'form_name']

    readonly_fields =  ['id',
                        'source_url',
                        'original_file',
                        'current_app',
                        'created',
                        'modified',
                        'rendered',
                        'schema_version',
                        'data_schema_version',
                        'form_name']

admin.site.register(SuppliedData, SuppliedDataAdmin)

class FileSubmissionAdmin(admin.ModelAdmin):
    list_display = ['supplied_data',
                    'publisher']
    readonly_fields =  ['supplied_data',
                        'publisher']

admin.site.register(FileSubmission, FileSubmissionAdmin)
