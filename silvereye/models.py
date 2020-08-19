from cove.input.models import SuppliedData
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class Publisher(models.Model):
    publisher_id = models.CharField(max_length=1024, null=True)
    publisher_name = models.CharField(max_length=1024, null=True)
    contact_name = models.CharField(max_length=1024, null=True, blank=True, default="")
    contact_email = models.CharField(max_length=1024, null=True, blank=True, default="")
    contact_telephone = models.CharField(max_length=1024, null=True, blank=True, default="")

    class Meta:
        app_label = 'silvereye'
        db_table = 'silvereye_publisher_metadata'


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
        db_table = 'silvereye_publisher_metrics'


class FileSubmission(models.Model):
    supplied_data = models.OneToOneField(SuppliedData, on_delete=models.CASCADE)
    publisher = models.ForeignKey(Publisher, on_delete=models.CASCADE, null=False)

    @receiver(post_save, sender=SuppliedData)
    def create_file_submission(sender, instance, created, **kwargs):
        if created:
            FileSubmission.objects.create(supplied_data=instance)

    @receiver(post_save, sender=SuppliedData)
    def save_file_submission(sender, instance, **kwargs):
        instance.filesubmission.save()
