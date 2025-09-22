from django.db import models
from django.contrib.auth.models import User
import json

class QueryFile(models.Model):
    """Represents a file that contains multiple query templates"""
    file_name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='query_files')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['file_name']

    def __str__(self):
        return self.file_name

    def get_query_count(self):
        return self.query_templates.count()

class QueryTemplate(models.Model):
    """Individual query templates within a file"""
    query_file = models.ForeignKey(QueryFile, on_delete=models.CASCADE, related_name='query_templates')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    configuration = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ['query_file', 'name']
        ordering = ['name']

    def __str__(self):
        return f"{self.query_file.file_name} - {self.name}"

    def get_full_name(self):
        return f"{self.query_file.file_name}/{self.name}"

class ScheduledQueryTask(models.Model):
    """Links query templates to scheduled tasks"""
    task_name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)
    query_templates = models.ManyToManyField(QueryTemplate, related_name='scheduled_tasks')
    
    # Scheduling options
    cron_expression = models.CharField(max_length=100, help_text="Cron expression (e.g., '0 9 * * *' for daily at 9 AM)")
    
    # Email settings
    email_recipients = models.TextField(help_text="Comma-separated email addresses")
    email_subject = models.CharField(max_length=255, default="Scheduled Query Results")
    
    # Task settings
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_run = models.DateTimeField(null=True, blank=True)
    
    # Output format
    OUTPUT_FORMATS = [
        ('json', 'JSON'),
        ('csv', 'CSV'),
        ('html', 'HTML Table'),
    ]
    output_format = models.CharField(max_length=10, choices=OUTPUT_FORMATS, default='html')

    class Meta:
        ordering = ['task_name']

    def __str__(self):
        return self.task_name

    def get_query_templates_list(self):
        return list(self.query_templates.values_list('id', flat=True))

class QueryExecutionLog(models.Model):
    """Log of query executions"""
    scheduled_task = models.ForeignKey(ScheduledQueryTask, on_delete=models.CASCADE, related_name='execution_logs', null=True, blank=True)
    query_template = models.ForeignKey(QueryTemplate, on_delete=models.CASCADE, related_name='execution_logs')
    executed_at = models.DateTimeField(auto_now_add=True)
    execution_time = models.FloatField(help_text="Execution time in seconds")
    row_count = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=[
        ('success', 'Success'),
        ('error', 'Error'),
        ('timeout', 'Timeout'),
    ], default='success')
    error_message = models.TextField(blank=True, null=True)
    result_data = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ['-executed_at']

    def __str__(self):
        return f"{self.query_template.get_full_name()} - {self.executed_at}"