from cove.input.models import SuppliedData
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class Publisher(models.Model):
    publisher_scheme = models.CharField(max_length=1024,
                                        null=True,
                                        blank=True,
                                        default="",
                                        help_text='The scheme that holds the unique identifiers used to identify publishers')
    publisher_id = models.CharField(max_length=1024,
                                    null=True,
                                    help_text='The unique ID for this publisher under the given ID scheme')
    publisher_name = models.CharField(max_length=1024,
                                      null=True,
                                      help_text='The name of the organization or department responsible for publishing this data')
    uri = models.CharField(max_length=1024,
                           null=True,
                           blank=True,
                           default="",
                           help_text='A URI to identify the publisher')
    ocid_prefix = models.CharField(max_length=11,
                                   null=True,
                                   blank=True,
                                   default="",
                                   help_text="OCID prefix registered by the publisher")
    contact_name = models.CharField(max_length=1024, null=True, blank=True, default="")
    contact_email = models.CharField(max_length=1024, null=True, blank=True, default="")
    contact_telephone = models.CharField(max_length=1024, null=True, blank=True, default="")

    class Meta:
        app_label = 'silvereye'
        db_table = 'silvereye_publisher_metadata'
        ordering = ["publisher_name"]

    def __str__(self):
        return self.publisher_name


class PublisherMetrics(models.Model):
    publisher_id = models.CharField(max_length=1024, primary_key=True)
    publisher_name = models.CharField(max_length=1024)
    count_lastmonth = models.IntegerField(null=True)
    count_last3months = models.IntegerField(null=True)
    count_last12months = models.IntegerField(null=True)
    average_lastmonth = models.IntegerField(null=True)
    average_last3months = models.IntegerField(null=True)
    average_last12months = models.IntegerField(null=True)

    class Meta:
        app_label = 'silvereye'


class PublisherMonthlyCounts(models.Model):
    publisher = models.ForeignKey(Publisher, on_delete=models.CASCADE, null=True)
    date = models.DateField(null=True)
    count_tenders = models.IntegerField(null=True)
    count_awards = models.IntegerField(null=True)
    count_spend = models.IntegerField(null=True)

    class Meta:
        unique_together = ('publisher', 'date',)


class FileSubmission(SuppliedData):
    supplied_data = models.OneToOneField(SuppliedData, on_delete=models.CASCADE, parent_link=True, primary_key=True, serialize=False)
    publisher = models.ForeignKey(Publisher, on_delete=models.CASCADE, null=True)
    notice_type = models.CharField(max_length=128, null=True)

    @receiver(post_save, sender=SuppliedData)
    def create_file_submission(sender, instance, created, **kwargs):
        if created:
            FileSubmission.objects.create(supplied_data=instance)

    def __str__(self):
        return f"{self.supplied_data.original_file}"


class FieldCoverage(models.Model):
    file_submission = models.OneToOneField(FileSubmission, on_delete=models.CASCADE, primary_key=True)
    tenders_field_coverage = models.FloatField(null=True)
    awards_field_coverage = models.FloatField(null=True)
    spend_field_coverage = models.FloatField(null=True)



class AuthorityType(models.Model):
    authority_name = models.CharField(max_length=1024)
    authority_type = models.CharField(max_length=1024)
    source = models.CharField(max_length=1024)
